"""
Governance Pressure Engine (ADG Closed-Loop Control - Formally Corrected)
Implements:
1. Normalized Governance Pressure G_p(t) = sum_k w_k * Phi(S_k(t)) (Equations 4-6).
2. Four-Threshold Anti-Chattering Hysteresis State Machine (Equation 7).
"""

import numpy as np
from enum import IntEnum
from offchain_engine.config import ADGSystemConfig


class GovernanceMode(IntEnum):
    MODE_0_FLAT = 0           # Full Decentralization (Flat Consensus)
    MODE_1_ADAPTIVE = 1       # Adaptive Committee Consensus
    MODE_1_COMMITTEE = 1      # Alias for Mode 1
    MODE_2_BOUNDED_LEAD = 2   # Bounded Leadership (Queen Regime)


class GovernancePressureEngine:
    def __init__(self, config: ADGSystemConfig):
        self.cfg = config
        self.current_mode = GovernanceMode.MODE_0_FLAT
        self.last_gp = 0.0

    def sigmoidal_normalization(
        self,
        x: np.ndarray,
        lambda_g: float = 6.0,
        x0: float = 0.5
    ) -> np.ndarray:
        """
        Element-wise Sigmoidal Normalization Phi(x) (Equation 6):
        Phi(x) = 1.0 / (1.0 + exp(-lambda_g * (x - x0)))
        """
        return 1.0 / (1.0 + np.exp(-lambda_g * (x - x0)))

    def compute_pressure(
        self,
        state_vector: np.ndarray,
        use_sigmoidal_mapping: bool = True
    ) -> float:
        """
        Computes Closed-Loop Governance Pressure G_p(t) (Equations 4 & 5):
        G_p(t) = sum_{k in {r, w, f, c, d}} w_k * Phi(S_k(t))
        
        Args:
            state_vector: Array of macroscopic metrics [R, W, F, C, DE].
                          Notice that DE is inverted to entropy deficit: S_d = 1.0 - DE.
            use_sigmoidal_mapping: Whether to apply non-linear sigmoid Phi(x) or convex dot product.

        Returns:
            g_pressure: Normalized governance pressure in (0.0, 1.0).
        """
        gw = self.cfg.governance_weights

        # Extract macroscopic state components
        r = float(state_vector[0])  # Anomaly / risk index
        w = float(state_vector[1])  # Throughput demand
        f = float(state_vector[2])  # Unresponsive / faulty nodes
        c = float(state_vector[3])  # Coordination gossip overhead
        de = float(state_vector[4]) # Instantaneous Decentralization Entropy

        # Formalize stressor vector S_tilde = [R, W, F, C, 1 - DE]^T (Equation 4a)
        de_deficit = max(0.0, 1.0 - de)
        stressor_vector = np.array([r, w, f, c, de_deficit], dtype=np.float64)
        weights = np.array([gw.w_r, gw.w_w, gw.w_f, gw.w_c, gw.w_d], dtype=np.float64)

        if use_sigmoidal_mapping:
            phi_s = self.sigmoidal_normalization(stressor_vector)
            raw_gp = float(np.dot(weights, phi_s))
        else:
            raw_gp = float(np.dot(weights, stressor_vector))

        self.last_gp = float(np.clip(raw_gp, 0.0, 1.0))
        return self.last_gp

    def evaluate_regime_transition(self, g_pressure: float) -> GovernanceMode:
        """
        Implements the deterministic four-threshold hysteresis state machine (Equation 7):
        - Mode 0 (Flat):
            Transitions to Mode 1 if G_p >= theta_low_up (0.35).
            Transitions directly to Mode 2 if severe shock G_p >= theta_high_up (0.70).
        - Mode 1 (Adaptive Committee):
            Recovers to Mode 0 if G_p < theta_low_down (0.30).
            Escalates to Mode 2 if G_p >= theta_high_up (0.70).
        - Mode 2 (Bounded Leadership):
            Relaxes to Mode 1 if G_p < theta_high_down (0.65).
            Recovers fully to Mode 0 if shock dissipates G_p < theta_low_down (0.30).
        """
        th = self.cfg.thresholds
        prev_mode = self.current_mode

        if prev_mode == GovernanceMode.MODE_0_FLAT:
            if g_pressure >= th.theta_high_up:
                self.current_mode = GovernanceMode.MODE_2_BOUNDED_LEAD
            elif g_pressure >= th.theta_low_up:
                self.current_mode = GovernanceMode.MODE_1_ADAPTIVE

        elif prev_mode == GovernanceMode.MODE_1_ADAPTIVE:
            if g_pressure >= th.theta_high_up:
                self.current_mode = GovernanceMode.MODE_2_BOUNDED_LEAD
            elif g_pressure < th.theta_low_down:
                self.current_mode = GovernanceMode.MODE_0_FLAT

        elif prev_mode == GovernanceMode.MODE_2_BOUNDED_LEAD:
            if g_pressure < th.theta_low_down:
                self.current_mode = GovernanceMode.MODE_0_FLAT
            elif g_pressure < th.theta_high_down:
                self.current_mode = GovernanceMode.MODE_1_ADAPTIVE

        return self.current_mode