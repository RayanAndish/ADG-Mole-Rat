"""
State Monitor Module (ADG Macroscopic Telemetry Aggregator - Formally Corrected)
Constructs the global state vector S(t) = [R(t), W(t), F(t), C(t), DE(t)]^T in R^5
according to Algorithm 1 (Lines 1-8) and Section 3.2.3.
Resolves Issue 19 (Risk vs Reputation mismatch) and Issue 20 (Workload operationalization).
"""

import numpy as np
from typing import Optional


class StateMonitor:
    def __init__(self, node_count: int, q_threshold: float = 0.80):
        self.node_count = node_count
        self.q_threshold = q_threshold

    def compute_global_state(
        self,
        node_telemetry_matrix: np.ndarray,
        current_entropy: float,
        coordination_cost: float,
        external_risk_signal: Optional[float] = None
    ) -> np.ndarray:
        """
        Constructs the normalized macroscopic system state vector S(t) in R^5 (Equation 3):
            S(t) = [R(t), W(t), F(t), C(t), DE(t)]^T

        Args:
            node_telemetry_matrix: Array of shape (N, 7) representing:
                Index 0: Q_i - Reliability uptime in [0, 1]
                Index 1: r_i - Cryptographic reputation / stake in [0, 1]
                Index 2: c_i - Compute / bandwidth capacity in R+
                Index 3: w_i - Processing queue load in [0, 1]
                Index 4: e_i - Remaining resource / energy budget in [0, 1]
                Index 5: l_i - Network round-trip latency relative to peer median in R+
                Index 6: p_i - Historical governance participation consistency in [0, 1]
            current_entropy: Instantaneous Decentralization Entropy DE(t) in [0, 1].
            coordination_cost: Normalized message gossip overhead C(t) in [0, 1].
            external_risk_signal: Optional external risk telemetry (e.g., mempool exploits) in [0, 1].

        Returns:
            np.ndarray of shape (5,) normalized in [0, 1].
        """
        reliabilities = node_telemetry_matrix[:, 0]
        compute_caps = node_telemetry_matrix[:, 2]
        queue_loads = node_telemetry_matrix[:, 3]
        latencies = node_telemetry_matrix[:, 5]

        # 1. Fault Rate F(t): Fraction of unresponsive or substandard nodes (Algorithm 1, Line 6)
        fault_mask = (reliabilities < self.q_threshold)
        fault_rate = float(np.mean(fault_mask))

        # 2. Workload Demand W(t): Capacity-weighted network load utilization (Equation 3 & Algorithm 1, Line 8)
        total_capacity = float(np.sum(compute_caps))
        if total_capacity > 1e-9:
            effective_workload = float(np.sum(queue_loads * compute_caps) / total_capacity)
        else:
            effective_workload = float(np.mean(queue_loads))

        # 3. Anomaly & Risk Index R(t): Intrinsic telemetry risk combined with external stress
        # Evaluates uptime degradation + severe latency outliers (Resolves Issue 19)
        intrinsic_risk = float(np.mean(1.0 - reliabilities) + 0.5 * np.mean(latencies > 2.0))
        intrinsic_risk = np.clip(intrinsic_risk, 0.0, 1.0)

        if external_risk_signal is not None:
            # Combine 60% external threat injection with 40% intrinsic telemetry risk
            combined_risk = 0.60 * external_risk_signal + 0.40 * intrinsic_risk
        else:
            combined_risk = intrinsic_risk

        # 4. Clamping all metrics strictly into constitutional bounds [0.0, 1.0]
        r_clamped = float(np.clip(combined_risk, 0.0, 1.0))
        w_clamped = float(np.clip(effective_workload, 0.0, 1.0))
        f_clamped = float(np.clip(fault_rate, 0.0, 1.0))
        c_clamped = float(np.clip(coordination_cost, 0.0, 1.0))
        de_clamped = float(np.clip(current_entropy, 0.0, 1.0))

        state_vector = np.array([r_clamped, w_clamped, f_clamped, c_clamped, de_clamped], dtype=np.float64)
        return state_vector