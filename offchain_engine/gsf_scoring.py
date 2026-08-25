"""
Dynamic Governance Scoring Engine (GSF)
Evaluates node qualification and enforces anti-monopoly decay.
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
        Evaluates GSF for all nodes:
        GS_i = [ (beta_q*Q + beta_r*r + beta_c*c + beta_p*p) / (1 + beta_w*w + beta_l*l) ] * exp(-xi * tau)
        
        Args:
            telemetry_matrix: (N, 7) array [Q, r, c, w, e, l, p].
            tenure_epochs: (N,) array representing elapsed epochs since last lead.
            
        Returns:
            gsf_scores: (N,) array in R+.
        """
        gw = self.cfg.gsf_weights

        q = telemetry_matrix[:, 0]
        r = telemetry_matrix[:, 1]
        c = telemetry_matrix[:, 2]
        w = telemetry_matrix[:, 3]
        l = telemetry_matrix[:, 5]
        p = telemetry_matrix[:, 6]

        # Numerator: Quality terms
        numerator = gw.beta_q * q + gw.beta_r * r + gw.beta_c * c + gw.beta_p * p

        # Denominator: Penalty terms
        denominator = 1.0 + gw.beta_w * w + gw.beta_l * l

        base_score = numerator / np.maximum(denominator, 1e-12)

        # Anti-monopoly decay factor: exp(-xi * tau_i)
        decay_factor = np.exp(-gw.xi * np.maximum(tenure_epochs, 0.0))

        gsf_scores = base_score * decay_factor
        return gsf_scores