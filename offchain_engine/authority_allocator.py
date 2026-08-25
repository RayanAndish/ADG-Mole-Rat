"""
Authority Allocation & Entropy Projection Engine
Implements Boltzmann authority distribution and Algorithm 3 (Constrained Projection onto DE_min Simplex).
"""

import numpy as np
from offchain_engine.config import ADGSystemConfig
from offchain_engine.governance_pressure import GovernanceMode


class AuthorityAllocator:
    def __init__(self, config: ADGSystemConfig):
        self.cfg = config

    def calculate_shannon_entropy(self, authority_vector: np.ndarray) -> float:
        """
        Evaluates Normalized Shannon Decentralization Entropy DE(a) = - (1 / ln N) * sum(a_i * ln a_i).
        """
        n = len(authority_vector)
        if n <= 1:
            return 1.0

        p = np.clip(authority_vector, 1e-15, 1.0)
        p = p / np.sum(p)
        raw_entropy = -np.sum(p * np.log(p))
        normalized_de = raw_entropy / np.log(n)
        return float(normalized_de)

    def project_to_entropy_simplex(
        self,
        raw_authority: np.ndarray,
        target_de_min: float,
        max_iter: int = 100,
        tol: float = 1e-6
    ) -> np.ndarray:
        """
        Algorithm 3: Bregman projection to strictly enforce DE(a) >= DE_min.
        """
        n = len(raw_authority)
        a_current = np.copy(raw_authority)
        a_current = a_current / np.sum(a_current)

        current_de = self.calculate_shannon_entropy(a_current)
        if current_de >= target_de_min - tol:
            return a_current

        mu_dual = 0.5
        step_size = 0.05

        for _ in range(max_iter):
            p = np.clip(a_current, 1e-15, 1.0)
            de_val = -np.sum(p * np.log(p)) / np.log(n)

            if de_val >= target_de_min - tol:
                break

            # Gradient of DE with respect to a_i
            grad_de = -(np.log(p) + 1.0) / np.log(n)

            # Subgradient update toward uniform entropy
            mu_dual = max(0.0, mu_dual + step_size * (target_de_min - de_val))
            a_current = raw_authority * np.exp(mu_dual * grad_de)
            a_current = a_current / np.sum(a_current)

        return a_current

    def allocate_authority(
        self,
        gsf_scores: np.ndarray,
        governance_pressure: float,
        current_mode: GovernanceMode
    ) -> np.ndarray:
        """
        Master authority allocation using Boltzmann distribution with dynamic temperature.
        """
        n = len(gsf_scores)
        th = self.cfg.thresholds

        if current_mode == GovernanceMode.MODE_0_FLAT:
            # Mode 0: Perfect Uniform Authority
            return np.full(n, 1.0 / n, dtype=np.float64)

        # Mode 1 & 2: Dynamic Selectivity scaling gamma(G_p) = gamma_0 * (1 + kappa * G_p)
        gamma = 1.50 * (1.0 + 2.0 * governance_pressure)
        
        # Heaviside filter: only nodes exceeding theta_act participate
        eligible_mask = gsf_scores >= th.theta_act
        if not np.any(eligible_mask):
            eligible_mask = np.ones(n, dtype=bool)

        shifted_scores = gsf_scores - np.max(gsf_scores) # Numerical stability
        exp_terms = np.exp(gamma * shifted_scores) * eligible_mask

        if np.sum(exp_terms) == 0:
            raw_a = np.full(n, 1.0 / n, dtype=np.float64)
        else:
            raw_a = exp_terms / np.sum(exp_terms)

        # Enforce Information-Theoretic Entropy Invariant DE >= DE_min
        final_a = self.project_to_entropy_simplex(raw_a, th.de_min)
        return final_a