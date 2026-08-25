"""
Actuation Signals Module
Translates biological IPM odour suppression and targeted shoving into distributed network controls.
"""

import numpy as np
from offchain_engine.config import ADGSystemConfig


class ActuationSignalEngine:
    def __init__(self, config: ADGSystemConfig):
        self.cfg = config

    def compute_ipm_suppression(self, governance_pressure: float) -> float:
        """
        Chemical Attenuation: \sigma_{IPM}(t) = \sigma_0 * (1 - exp(-\eta * G_p))
        Suppresses non-essential transaction mutations during crises.
        """
        ap = self.cfg.actuation
        raw_suppression = ap.sigma_0 * (1.0 - np.exp(-ap.eta * governance_pressure))
        return float(np.clip(raw_suppression, 0.0, ap.sigma_0))

    def compute_shoving_stimulus(
        self,
        node_loads: np.ndarray,
        node_latencies: np.ndarray,
        node_reliabilities: np.ndarray
    ) -> np.ndarray:
        """
        Physical Shoving Stimulus:
        u_{stim,i}(t) = ReLU((w_mean - w_i) / w_mean) * I(l_i <= l_median) * I(Q_i >= Q_thresh)
        """
        ap = self.cfg.actuation
        mean_load = np.mean(node_loads)
        median_latency = np.median(node_latencies)

        if mean_load <= 1e-12:
            return np.zeros_like(node_loads)

        load_deficit = np.maximum(0.0, (mean_load - node_loads) / mean_load)
        latency_filter = (node_latencies <= median_latency).astype(np.float64)
        reliability_filter = (node_reliabilities >= ap.q_thresh).astype(np.float64)

        stimulus_vector = load_deficit * latency_filter * reliability_filter
        return stimulus_vector