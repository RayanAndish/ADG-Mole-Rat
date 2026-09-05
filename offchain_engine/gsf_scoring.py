"""
Dynamic Governance Scoring Engine (GSF) - Formally Corrected
Evaluates multi-factor node suitability (Equation 8) incorporating 5-factor quality telemetry:
[Q_i, r_i, c_i, e_i, p_i] and enforces anti-monopoly tenure decay (xi).
"""

import numpy as np
from offchain_engine.config import ADGSystemConfig


class GSFScoringEngine:
    def __init__(self, config: ADGSystemConfig):
        self.cfg = config

    def calculate_gsf_scores(
        self,
        telemetry_matrix: np.ndarray,
        tenure_epochs: np.ndarray
    ) -> np.ndarray:
        """
        Evaluates the Dynamic Governance Score (GSF) for all participating nodes (Equation 8):
        GS_i(t) = [ (beta_q*Q + beta_r*r + beta_c*c + beta_e*e + beta_p*p) / 
                    (1 + beta_w*w + beta_l*l) ] * exp(-xi * tau_lead)

        Args:
            telemetry_matrix: (N, 7) array of local state vectors:
                Index 0: Q_i - Empirical reliability uptime in [0, 1]
                Index 1: r_i - Reputation / stake weight in [0, 1]
                Index 2: c_i - Compute/bandwidth capacity in R+
                Index 3: w_i - Processing queue load in [0, 1]
                Index 4: e_i - Energy / hardware headroom budget in [0, 1] (Resolves Issue 18)
                Index 5: l_i - Network round-trip latency relative to median in R+
                Index 6: p_i - Historical governance participation consistency in [0, 1]
            tenure_epochs: (N,) array representing consecutive epochs served as active coordinator
                           (0 for all non-coordinator validators).

        Returns:
            gsf_scores: (N,) array of suitability scores in R+.
        """
        gw = self.cfg.gsf_weights

        q = telemetry_matrix[:, 0]
        r = telemetry_matrix[:, 1]
        c = telemetry_matrix[:, 2]
        w = telemetry_matrix[:, 3]
        e = telemetry_matrix[:, 4]  # Energy / resource budget (Activated)
        l = telemetry_matrix[:, 5]
        p = telemetry_matrix[:, 6]

        # 1. Numerator: 5-Factor Convex Quality Profile (Sum of weights strictly 1.0)
        numerator = (
            gw.beta_q * q +
            gw.beta_r * r +
            gw.beta_c * c +
            gw.beta_e * e +
            gw.beta_p * p
        )

        # 2. Denominator: Load and Latency Penalties (Guaranteed >= 1.0)
        denominator = 1.0 + gw.beta_w * w + gw.beta_l * l

        base_score = numerator / np.maximum(denominator, 1e-12)

        # 3. Anti-Monopoly Coordinator Tenure Decay Factor: exp(-xi * tau_i)
        # Non-leaders (tenure = 0) receive decay_factor = 1.0 (no penalty).
        # Incumbent coordinators accumulate tenure epochs, progressively decaying authority.
        tenure = np.maximum(tenure_epochs, 0.0)
        decay_factor = np.exp(-gw.xi * tenure)

        # Apply constitutional floor of 0.10 to prevent zero division
        decay_factor = np.maximum(decay_factor, 0.10)

        gsf_scores = base_score * decay_factor
        return gsf_scores