"""
Scalable Discrete-Event Simulator Engine
High-throughput vectorized simulation framework benchmarking ADG across N = 16 to 4096 nodes.
"""

import numpy as np
from typing import Dict, List, Any
from offchain_engine.config import ADGSystemConfig
from offchain_engine.state_monitor import StateMonitor
from offchain_engine.governance_pressure import GovernancePressureEngine, GovernanceMode
from offchain_engine.gsf_scoring import GSFScoringEngine
from offchain_engine.authority_allocator import AuthorityAllocator
from offchain_engine.actuation_signals import ActuationSignalEngine
from offchain_engine.succession_fsm import SuccessionAutomaton
from offchain_engine.lyapunov_tracker import LyapunovEnergyTracker


class DiscreteEventSimulator:
    def __init__(self, node_count: int, total_epochs: int, config: ADGSystemConfig = None):
        self.node_count = node_count
        self.total_epochs = total_epochs
        self.cfg = config or ADGSystemConfig()
        
        # Seed initialization
        np.random.seed(self.cfg.random_seed)

        # Core Engines
        self.monitor = StateMonitor(node_count)
        self.pressure_engine = GovernancePressureEngine(self.cfg)
        self.scoring_engine = GSFScoringEngine(self.cfg)
        self.allocator = AuthorityAllocator(self.cfg)
        self.actuator = ActuationSignalEngine(self.cfg)
        self.succession_fsm = SuccessionAutomaton(self.cfg)
        self.lyapunov = LyapunovEnergyTracker(self.cfg)

        # Synthetic Node State Registry: [Q, r, c, w, e, l, p]
        self.node_telemetries = np.zeros((node_count, 7), dtype=np.float64)
        self._initialize_node_population()
        self.tenure_epochs = np.zeros(node_count, dtype=np.float64)
        self.byzantine_mask = np.zeros(node_count, dtype=bool)

    def _initialize_node_population(self):
        # Q_i: Beta distribution centered at 0.95 reliability
        self.node_telemetries[:, 0] = np.random.beta(19, 1, self.node_count)
        # r_i: Pareto stake/reputation distribution
        self.node_telemetries[:, 1] = np.random.pareto(2.0, self.node_count)
        self.node_telemetries[:, 1] /= np.max(self.node_telemetries[:, 1])
        # c_i: Compute capacity [0.5 to 2.0]
        self.node_telemetries[:, 2] = np.random.uniform(0.5, 2.0, self.node_count)
        # w_i: Baseline load [0.1 to 0.4]
        self.node_telemetries[:, 3] = np.random.uniform(0.1, 0.4, self.node_count)
        # e_i: Energy budget = 1.0
        self.node_telemetries[:, 4] = 1.0
        # l_i: Log-normal network latency centered at 1.0
        self.node_telemetries[:, 5] = np.random.lognormal(0.0, 0.3, self.node_count)
        # p_i: Participation consistency
        self.node_telemetries[:, 6] = np.random.uniform(0.8, 1.0, self.node_count)

    def inject_byzantine_adversaries(self, fraction: float):
        byzantine_count = int(self.node_count * fraction)
        corrupted_indices = np.random.choice(self.node_count, byzantine_count, replace=False)
        self.byzantine_mask[corrupted_indices] = True

    def run_simulation(
        self,
        shock_epoch: int = 50,
        shock_intensity: float = 0.95
    ) -> Dict[str, Any]:
        """
        Executes discrete-event consensus rounds with an injected stress transient.
        """
        history_gp = []
        history_de = []
        history_modes = []
        history_energy = []
        history_tps = []
        history_latency = []

        current_entropy = 1.0
        coordination_cost = 0.05
        current_authority = np.full(self.node_count, 1.0 / self.node_count)

        for epoch in range(1, self.total_epochs + 1):
            # Inject Shock Transient
            if shock_epoch <= epoch < (shock_epoch + 20):
                risk = shock_intensity
                self.node_telemetries[:, 3] = np.minimum(1.0, self.node_telemetries[:, 3] + 0.60) # Surge workload
            else:
                risk = 0.05
                # Natural workload relaxation
                self.node_telemetries[:, 3] = np.maximum(0.2, self.node_telemetries[:, 3] - 0.05)

            # 1. State Monitoring
            state_vector = self.monitor.compute_global_state(
                self.node_telemetries,
                current_entropy,
                coordination_cost,
                risk
            )

            # 2. Pressure & Mode Transitions
            gp = self.pressure_engine.compute_pressure(state_vector)
            mode = self.pressure_engine.evaluate_regime_transition(gp)

            # 3. GSF Scoring
            self.tenure_epochs += 1
            self.tenure_epochs[self.succession_fsm.active_coordinator_id] = 0
            gsf_scores = self.scoring_engine.calculate_gsf_scores(self.node_telemetries, self.tenure_epochs)

            # 4. Authority Allocation & Simplex Projection (Alg. 3)
            current_authority = self.allocator.allocate_authority(gsf_scores, gp, mode)
            current_entropy = self.allocator.calculate_shannon_entropy(current_authority)

            # 5. Actuation
            sigma_ipm = self.actuator.compute_ipm_suppression(gp)
            u_stim = self.actuator.compute_shoving_stimulus(
                self.node_telemetries[:, 3],
                self.node_telemetries[:, 5],
                self.node_telemetries[:, 0]
            )

            # Apply Stimulus: reduce queue load of stimulated nodes
            self.node_telemetries[:, 3] = np.maximum(0.1, self.node_telemetries[:, 3] - 0.3 * u_stim)

            # 6. Check Succession Handover
            coord_id = self.succession_fsm.active_coordinator_id
            triggered = self.succession_fsm.evaluate_succession_trigger(
                gsf_scores[coord_id],
                self.byzantine_mask[coord_id],
                epoch
            )
            if triggered:
                cert, new_lead = self.succession_fsm.execute_handover_protocol(
                    epoch, gsf_scores, self.byzantine_mask, f"state_hash_epoch_{epoch}"
                )

            # 7. Lyapunov Tracking
            energy = self.lyapunov.compute_energy(gp, current_entropy, current_authority)
            self.lyapunov.record_step(epoch, energy)

            # Performance Metrics
            effective_tps = (1.0 - sigma_ipm) * np.sum(self.node_telemetries[:, 2] * 1000)
            latency_ms = 50.0 * (1.0 + gp) * (2.0 - current_entropy)

            # Record telemetry
            history_gp.append(gp)
            history_de.append(current_entropy)
            history_modes.append(int(mode))
            history_energy.append(energy)
            history_tps.append(effective_tps)
            history_latency.append(latency_ms)

        return {
            "epochs": np.arange(1, self.total_epochs + 1),
            "governance_pressure": np.array(history_gp),
            "decentralization_entropy": np.array(history_de),
            "modes": np.array(history_modes),
            "lyapunov_energy": np.array(history_energy),
            "tps": np.array(history_tps),
            "latency_ms": np.array(history_latency)
        }