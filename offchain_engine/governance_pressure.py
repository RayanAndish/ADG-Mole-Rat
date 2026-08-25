"""
Governance Pressure Engine
Computes non-linear G_p(t) and manages continuous hysteresis transitions between Modes 0, 1, and 2.
"""

import numpy as np
from enum import IntEnum
from offchain_engine.config import ADGSystemConfig


class GovernanceMode(IntEnum):
    MODE_0_FLAT = 0           # Full Decentralization
    MODE_1_ADAPTIVE = 1       # Committee Consensus
    MODE_2_BOUNDED_LEAD = 2   # Bounded Queen Regime


class GovernancePressureEngine:
    def __init__(self, config: ADGSystemConfig):
        self.cfg = config
        self.current_mode = GovernanceMode.MODE_0_FLAT
        self.last_gp = 0.0

    def compute_pressure(self, state_vector: np.ndarray) -> float:
        """
        Computes G_p(t) = w_r*R + w_w*W + w_f*F + w_c*C - w_d*DE.
        Applies a smooth sigmoidal non-linear mapping.
        """
        gw = self.cfg.governance_weights
        weights = np.array([gw.w_r, gw.w_w, gw.w_f, gw.w_c, -gw.w_d], dtype=np.float64)
        
        raw_pressure = np.dot(weights, state_vector)
        # Shift baseline so minimum possible value is 0
        clamped_pressure = np.clip(raw_pressure + gw.w_d, 0.0, 1.0)
        self.last_gp = float(clamped_pressure)
        return self.last_gp

    def evaluate_regime_transition(self, g_pressure: float) -> GovernanceMode:
        """
        Implements dual-threshold hysteresis automaton to prevent chattering.
        """
        th = self.cfg.thresholds
        eps = th.hysteresis_epsilon

        if self.current_mode == GovernanceMode.MODE_0_FLAT:
            if g_pressure >= th.theta_low:
                self.current_mode = GovernanceMode.MODE_1_ADAPTIVE

        elif self.current_mode == GovernanceMode.MODE_1_ADAPTIVE:
            if g_pressure < (th.theta_low - eps):
                self.current_mode = GovernanceMode.MODE_0_FLAT
            elif g_pressure >= th.theta_high:
                self.current_mode = GovernanceMode.MODE_2_BOUNDED_LEAD

        elif self.current_mode == GovernanceMode.MODE_2_BOUNDED_LEAD:
            if g_pressure < (th.theta_high - eps):
                self.current_mode = GovernanceMode.MODE_1_ADAPTIVE
            if g_pressure < (th.theta_low - eps):
                self.current_mode = GovernanceMode.MODE_0_FLAT

        return self.current_mode