"""
Actuation Signals Module (ADG Biological Control Actuators - Formally Corrected)
Implements:
1. Global Pheromone-Inspired Attenuation \sigma_{IPM}(t) & Bandwidth Throttling (Equations 10 & 11).
2. Targeted Mechanical Stimulus Impulse Vector u_{stim,i}(t) (Equation 12).
"""

import numpy as np
from typing import Optional
from offchain_engine.config import ADGSystemConfig


class ActuationSignalEngine:
    def __init__(self, config: ADGSystemConfig):
        self.cfg = config

    def compute_ipm_suppression(
        self,
        governance_pressure: float,
        elapsed_beacon_epochs: int = 0
    ) -> float:
        """
        Computes Global Chemical Attenuation Signal \sigma_{IPM}(t) (Equation 10):
            \sigma_{IPM}(t) = \sigma_0 * (1 - exp(-\eta * G_p(t))) * exp(-\delta * \Delta t)
        
        Args:
            governance_pressure: Instantaneous G_p(t) in [0, 1].
            elapsed_beacon_epochs: Elapsed epochs since last coordinator beacon emission.

        Returns:
            sigma_ipm: Attenuation factor in [0.0, \sigma_0].
        """
        ap = self.cfg.actuation
        gp_clamped = float(np.clip(governance_pressure, 0.0, 1.0))

        # Base non-linear pressure sensitivity: \sigma_0 * (1 - exp(-\eta * G_p))
        base_suppression = ap.sigma_0 * (1.0 - np.exp(-ap.eta * gp_clamped))

        # Temporal decay factor: exp(-\delta * \Delta t)
        if elapsed_beacon_epochs > 0:
            time_decay = np.exp(-ap.delta_decay * float(elapsed_beacon_epochs))
        else:
            time_decay = 1.0

        sigma_ipm = float(base_suppression * time_decay)
        return float(np.clip(sigma_ipm, 0.0, ap.sigma_0))

    def compute_allowed_bandwidth(
        self,
        sigma_ipm: float,
        bw_max: float = 1.0
    ) -> float:
        """
        Computes bounded network gossip bandwidth allocation (Equation 11):
            BW_allowed = BW_min + (BW_max - BW_min) * (1 - \sigma_{IPM})
        
        Guarantees that bandwidth never falls below the constitutional floor BW_min (0.20).
        """
        ap = self.cfg.actuation
        bw_min = ap.bw_min
        dynamic_range = max(0.0, bw_max - bw_min)
        
        suppression_ratio = sigma_ipm / ap.sigma_0 if ap.sigma_0 > 0 else 0.0
        allowed_bw = bw_min + dynamic_range * (1.0 - suppression_ratio)
        return float(np.clip(allowed_bw, bw_min, bw_max))

    def compute_shoving_stimulus(
        self,
        node_loads: np.ndarray,
        node_latencies: np.ndarray,
        node_reliabilities: np.ndarray
    ) -> np.ndarray:
        """
        Computes Targeted Mechanical Stimulus Impulses u_{stim,i}(t) (Equation 12):
            u_{stim,i}(t) = ReLU( (w_mean - w_i) / (w_mean + eps) ) * I(l_i <= l_med) * I(Q_i >= Q_thresh)

        Args:
            node_loads: (N,) array of instantaneous queue loads w_i in [0, 1].
            node_latencies: (N,) array of relative latencies l_i.
            node_reliabilities: (N,) array of reliability uptime scores Q_i in [0, 1].

        Returns:
            stimulus_vector: (N,) array of stimulus impulses in [0.0, 1.0].
        """
        ap = self.cfg.actuation
        mean_load = float(np.mean(node_loads))
        median_latency = float(np.median(node_latencies))

        if mean_load <= 1e-9:
            return np.zeros_like(node_loads, dtype=np.float64)

        # 1. Deficit operator with numerical stabilization: ReLU((w_mean - w_i) / (w_mean + eps))
        load_deficit = np.maximum(0.0, (mean_load - node_loads) / (mean_load + 1e-9))

        # 2. Latency filter: Node must be at or below peer median latency
        latency_filter = (node_latencies <= median_latency).astype(np.float64)

        # 3. Reliability filter: Node must satisfy constitutional threshold Q_thresh (0.80)
        reliability_filter = (node_reliabilities >= ap.q_thresh).astype(np.float64)

        stimulus_vector = load_deficit * latency_filter * reliability_filter
        return np.clip(stimulus_vector, 0.0, 1.0)

    def compute_effective_workload_absorption(
        self,
        stimulus_vector: np.ndarray,
        compute_capacities: np.ndarray
    ) -> float:
        """
        Computes aggregate absorbed workload demand from stimulated idle workers (Equation 24):
            W_absorbed = sum_{i=1}^N u_{stim,i}(t) * c_i(t)
        """
        return float(np.sum(stimulus_vector * compute_capacities))