"""
State Monitor Module
Aggregates local node telemetries X_i(t) into the global system state vector S(t).
"""

import numpy as np
from typing import Dict, Any


class StateMonitor:
    def __init__(self, node_count: int):
        self.node_count = node_count

    def compute_global_state(
        self,
        node_telemetry_matrix: np.ndarray,
        current_entropy: float,
        coordination_cost: float,
        risk_index: float
    ) -> np.ndarray:
        """
        Constructs S(t) = [R(t), W(t), F(t), C(t), DE(t)]^T in R^5.
        
        Args:
            node_telemetry_matrix: Array of shape (N, 7) representing:
                [Q_i, r_i, c_i, w_i, e_i, l_i, p_i] for each node.
            current_entropy: Normalized Shannon Decentralization Entropy DE(t) in [0, 1].
            coordination_cost: Message volume overhead metric C(t) in [0, 1].
            risk_index: External anomaly / risk index R(t) in [0, 1].
            
        Returns:
            np.ndarray of shape (5,) normalized in [0, 1].
        """
        reliabilities = node_telemetry_matrix[:, 0]
        compute_caps = node_telemetry_matrix[:, 2]
        queue_loads = node_telemetry_matrix[:, 3]

        # Fault rate: fraction of unresponsive nodes (reliability < 0.50)
        fault_rate = np.mean(reliabilities < 0.50)

        # Aggregate normalized workload demand: mean(w_i * c_i) / max(c_i)
        max_cap = np.max(compute_caps) if np.max(compute_caps) > 0 else 1.0
        normalized_workload = np.mean(queue_loads * compute_caps) / max_cap

        # Clamping to valid [0, 1] range
        r_clamped = float(np.clip(risk_index, 0.0, 1.0))
        w_clamped = float(np.clip(normalized_workload, 0.0, 1.0))
        f_clamped = float(np.clip(fault_rate, 0.0, 1.0))
        c_clamped = float(np.clip(coordination_cost, 0.0, 1.0))
        de_clamped = float(np.clip(current_entropy, 0.0, 1.0))

        state_vector = np.array([r_clamped, w_clamped, f_clamped, c_clamped, de_clamped], dtype=np.float64)
        return state_vector