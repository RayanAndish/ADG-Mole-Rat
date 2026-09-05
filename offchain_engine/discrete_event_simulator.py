"""
Scalable Discrete-Event Simulator Engine (ADG Master In-Silico Testbed - Formally Corrected)
High-throughput vectorized simulation framework benchmarking ADG across N = 16 to 4096 nodes
and operational horizons up to 100,000 consensus epochs (Sections 6.1 - 6.4).
"""

import numpy as np
from typing import Dict, List, Any, Optional
from offchain_engine.config import ADGSystemConfig
from offchain_engine.state_monitor import StateMonitor
from offchain_engine.governance_pressure import GovernancePressureEngine, GovernanceMode
from offchain_engine.gsf_scoring import GSFScoringEngine
from offchain_engine.authority_allocator import AuthorityAllocator
from offchain_engine.actuation_signals import ActuationSignalEngine
from offchain_engine.succession_fsm import SuccessionAutomaton
from offchain_engine.lyapunov_tracker import LyapunovEnergyTracker


class DiscreteEventSimulator:
    def __init__(
        self,
        node_count: int,
        total_epochs: int,
        config: Optional[ADGSystemConfig] = None,
        random_seed: Optional[int] = None
    ):
        self.node_count = node_count
        self.total_epochs = total_epochs
        self.cfg = config or ADGSystemConfig()
        
        # Seed initialization for reproducible Monte Carlo iterations
        seed = random_seed if random_seed is not None else self.cfg.random_seed
        np.random.seed(seed)

        # Core ADG Algorithmic Engines
        self.monitor = StateMonitor(node_count, q_threshold=self.cfg.thresholds.theta_act)
        self.pressure_engine = GovernancePressureEngine(self.cfg)
        self.scoring_engine = GSFScoringEngine(self.cfg)
        self.allocator = AuthorityAllocator(self.cfg)
        self.actuator = ActuationSignalEngine(self.cfg)
        self.succession_fsm = SuccessionAutomaton(self.cfg)
        self.lyapunov = LyapunovEnergyTracker(self.cfg)

        # Synthetic Node State Registry: [Q_i, r_i, c_i, w_i, e_i, l_i, p_i] (Equation 2)
        self.node_telemetries = np.zeros((node_count, 7), dtype=np.float64)
        self._initialize_node_population()

        # State tracking
        self.tenure_epochs = np.zeros(node_count, dtype=np.float64)
        self.byzantine_mask = np.zeros(node_count, dtype=bool)
        self.offline_mask = np.zeros(node_count, dtype=bool)

    def _initialize_node_population(self):
        """Initializes heterogeneous node profiles matching empirical distributions."""
        # Q_i (Reliability): Beta distribution centered at 0.95
        self.node_telemetries[:, 0] = np.random.beta(19, 1, self.node_count)
        # r_i (Reputation/Stake): Pareto stake distribution
        pareto_raw = np.random.pareto(2.0, self.node_count)
        self.node_telemetries[:, 1] = pareto_raw / np.max(pareto_raw)
        # c_i (Compute capacity): Uniform [0.5 to 2.0]
        self.node_telemetries[:, 2] = np.random.uniform(0.5, 2.0, self.node_count)
        # w_i (Initial queue load): Baseline [0.1 to 0.3]
        self.node_telemetries[:, 3] = np.random.uniform(0.1, 0.3, self.node_count)
        # e_i (Energy / Resource budget headroom): Initial 1.0 (Resolves Issue 18)
        self.node_telemetries[:, 4] = np.random.uniform(0.9, 1.0, self.node_count)
        # l_i (Network latency): Log-normal centered at 1.0
        self.node_telemetries[:, 5] = np.random.lognormal(0.0, 0.25, self.node_count)
        # p_i (Historical participation): Uniform [0.85 to 1.0]
        self.node_telemetries[:, 6] = np.random.uniform(0.85, 1.0, self.node_count)

    def inject_byzantine_adversaries(self, fraction: float):
        """Designates a fraction f of total nodes as adaptive Byzantine adversaries."""
        self.byzantine_mask[:] = False
        f_count = int(np.floor(self.node_count * fraction))
        if f_count > 0:
            corrupted_indices = np.random.choice(self.node_count, f_count, replace=False)
            self.byzantine_mask[corrupted_indices] = True

    def inject_validator_churn(self, drop_percentage: float):
        """Simulates validator churn by setting a fraction of nodes offline (Table 10)."""
        self.offline_mask[:] = False
        drop_count = int(np.floor(self.node_count * (drop_percentage / 100.0)))
        if drop_count > 0:
            offline_indices = np.random.choice(self.node_count, drop_count, replace=False)
            self.offline_mask[offline_indices] = True

    def run_simulation(
        self,
        shock_start_epoch: Optional[int] = None,
        shock_duration: int = 20,
        shock_risk: float = 0.90,
        shock_workload: float = 0.95
    ) -> Dict[str, Any]:
        """
        Executes discrete-event consensus epochs with calibrated non-equilibrium shock injection.
        """
        # Default shock at T/4 as specified in Section 6.1
        if shock_start_epoch is None:
            shock_start_epoch = max(5, self.total_epochs // 4)
        shock_end_epoch = shock_start_epoch + shock_duration

        # Output Telemetry Collectors
        history_gp = []
        history_de = []
        history_top_f = []
        history_gini = []
        history_modes = []
        history_energy = []
        history_tps = []
        history_latency = []
        handovers_executed = 0

        current_entropy = 1.0
        coordination_cost = 0.05
        current_authority = np.full(self.node_count, 1.0 / self.node_count, dtype=np.float64)
        f_bft = self.cfg.get_max_byzantine_nodes(self.node_count)

        for epoch in range(1, self.total_epochs + 1):
            # -------------------------------------------------------------
            # Step A: External Shock / Baseline Workload Modulation
            # -------------------------------------------------------------
            if shock_start_epoch <= epoch < shock_end_epoch:
                current_risk = shock_risk
                # Workload surge: elevate queue loads towards shock_workload (0.95)
                self.node_telemetries[:, 3] = np.minimum(1.0, self.node_telemetries[:, 3] + 0.50)
                # Transient energy drain under heavy load
                self.node_telemetries[:, 4] = np.maximum(0.2, self.node_telemetries[:, 4] - 0.03)
            else:
                current_risk = 0.05
                # Natural workload relaxation back towards nominal baseline (Equation 24)
                self.node_telemetries[:, 3] = np.maximum(0.15, self.node_telemetries[:, 3] - 0.05)
                self.node_telemetries[:, 4] = np.minimum(1.0, self.node_telemetries[:, 4] + 0.02)

            # -------------------------------------------------------------
            # Step B: Closed-Loop Telemetry & Governance Pressure (Alg 1, Lines 1-9)
            # -------------------------------------------------------------
            state_vector = self.monitor.compute_global_state(
                self.node_telemetries,
                current_entropy,
                coordination_cost,
                external_risk_signal=current_risk
            )

            gp = self.pressure_engine.compute_pressure(state_vector)
            mode = self.pressure_engine.evaluate_regime_transition(gp)

            # -------------------------------------------------------------
            # Step C: Coordinator Tenure Tracking & GSF Scoring (Eq 8 & Alg 1, Lines 10-14)
            # -------------------------------------------------------------
            # Corrected Tenure Logic: Only active coordinator accumulates tenure penalty!
            coord_id = self.succession_fsm.active_coordinator_id
            self.tenure_epochs[:] = 0.0  # Reset non-leaders
            self.tenure_epochs[coord_id] = float(self.succession_fsm.consecutive_epochs)

            gsf_scores = self.scoring_engine.calculate_gsf_scores(
                self.node_telemetries,
                self.tenure_epochs
            )

            # -------------------------------------------------------------
            # Step D: Dynamic Authority Allocation & Projection (Alg 1, Lines 15-53)
            # -------------------------------------------------------------
            current_authority = self.allocator.allocate_authority(gsf_scores, gp, mode)
            current_entropy = self.allocator.calculate_shannon_entropy(current_authority)
            top_f_share = self.allocator.calculate_top_f_share(current_authority, f_bft)
            gini = self.allocator.calculate_gini_coefficient(current_authority)

            # -------------------------------------------------------------
            # Step E: Biological Actuation (Equations 10-12 & Alg 1, Lines 55-61)
            # -------------------------------------------------------------
            sigma_ipm = self.actuator.compute_ipm_suppression(gp)
            u_stim = self.actuator.compute_shoving_stimulus(
                self.node_telemetries[:, 3],
                self.node_telemetries[:, 5],
                self.node_telemetries[:, 0]
            )

            # Actuator Effect: Stimulated workers absorb transient queue bottlenecks (Eq 24)
            workload_absorbed = self.actuator.compute_effective_workload_absorption(
                u_stim, self.node_telemetries[:, 2]
            )
            self.node_telemetries[:, 3] = np.maximum(0.10, self.node_telemetries[:, 3] - 0.25 * u_stim)

            # Update coordination cost C(t) based on active mode
            if mode == GovernanceMode.MODE_0_FLAT:
                coordination_cost = 0.05
            elif mode == GovernanceMode.MODE_1_ADAPTIVE:
                coordination_cost = 0.35
            else:
                coordination_cost = 0.75

            # -------------------------------------------------------------
            # Step F: Leader Succession Verification (Algorithm 2 & Section 3.7)
            # -------------------------------------------------------------
            triggered = self.succession_fsm.evaluate_succession_trigger(
                gsf_scores[coord_id],
                self.byzantine_mask[coord_id] or self.offline_mask[coord_id],
                epoch
            )
            if triggered:
                cert, new_lead = self.succession_fsm.execute_handover_protocol(
                    epoch,
                    gsf_scores,
                    self.byzantine_mask,
                    f"state_hash_epoch_{epoch}",
                    offline_mask=self.offline_mask
                )
                if cert is not None and cert.is_valid:
                    handovers_executed += 1

            # -------------------------------------------------------------
            # Step G: Lyapunov Stability Tracking (Equation 19 & Theorem 1)
            # -------------------------------------------------------------
            energy = self.lyapunov.compute_energy(gp, current_entropy, current_authority)
            self.lyapunov.record_step(epoch, energy)

            # -------------------------------------------------------------
            # Step H: Performance Metrics Extraction (Table 7 & Table 8)
            # -------------------------------------------------------------
            # Simulated logical throughput scaled by population capacity and throttled by sigma_IPM
            base_capacity_tps = np.sum(self.node_telemetries[:, 2]) * 800.0
            effective_tps = (1.0 - 0.31 * (sigma_ipm / self.cfg.actuation.sigma_0)) * base_capacity_tps

            # Latency smoothing: contracts as N grows (illustrating tail-latency invariance)
            base_latency = 52.0 + 15.0 * gp
            latency_jitter = np.random.normal(0.0, 1.0 / np.sqrt(max(1, self.node_count)))
            finality_latency_ms = max(10.0, base_latency + latency_jitter)

            # Record epoch telemetry
            history_gp.append(gp)
            history_de.append(current_entropy)
            history_top_f.append(top_f_share)
            history_gini.append(gini)
            history_modes.append(int(mode))
            history_energy.append(energy)
            history_tps.append(effective_tps)
            history_latency.append(finality_latency_ms)

        lyapunov_stats = self.lyapunov.get_summary_statistics()

        return {
            "epochs": np.arange(1, self.total_epochs + 1),
            "governance_pressure": np.array(history_gp),
            "decentralization_entropy": np.array(history_de),
            "top_f_coalition_share": np.array(history_top_f),
            "gini_coefficient": np.array(history_gini),
            "modes": np.array(history_modes),
            "lyapunov_energy": np.array(history_energy),
            "tps": np.array(history_tps),
            "latency_ms": np.array(history_latency),
            "handovers_executed": handovers_executed,
            "lyapunov_dissipation_c": lyapunov_stats["dissipation_constant_c"],
            "final_lyapunov_energy": lyapunov_stats["final_energy"],
            "min_preserved_de": float(np.min(history_de)),
            "max_top_f_share": float(np.max(history_top_f)),
            "governance_capture_occurred": bool(np.max(history_top_f) >= 0.50)
        }