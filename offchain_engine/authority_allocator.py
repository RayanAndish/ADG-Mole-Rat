"""
Authority Allocation Engine (Fixed & Mathematically Corrected)
Implements Analytical Convex Projection ensuring DE(t) >= DE_min and computes Gini Index.
"""

import numpy as np
from offchain_engine.config import ADGSystemConfig
from offchain_engine.governance_pressure import GovernanceMode


class AuthorityAllocator:
    def __init__(self, config: ADGSystemConfig):
        self.cfg = config

    def calculate_shannon_entropy(self, authority_vector: np.ndarray) -> float:
        """
        Evaluates Normalized Shannon Decentralization Entropy:
        DE(a) = - (1 / ln N) * sum(a_i * ln a_i)
        """
        n = len(authority_vector)
        if n <= 1:
            return 1.0

        p = np.clip(authority_vector, 1e-15, 1.0)
        p = p / np.sum(p)
        raw_entropy = -np.sum(p * np.log(p))
        normalized_de = raw_entropy / np.log(n)
        return float(np.clip(normalized_de, 0.0, 1.0))

    def calculate_gini_coefficient(self, authority_vector: np.ndarray) -> float:
        """
        Computes the Gini Coefficient of authority concentration:
        G = sum_i sum_j |a_i - a_j| / (2 * N * sum_i a_i)
        G = 0 -> Perfect Equality (Flat Decentralization), G = 1 -> Total Monopoly
        """
        a = np.sort(authority_vector)
        n = len(a)
        if n == 0 or np.sum(a) == 0:
            return 0.0
        index = np.arange(1, n + 1)
        gini = (2.0 * np.sum(index * a) - (n + 1) * np.sum(a)) / (n * np.sum(a))
        return float(np.clip(gini, 0.0, 1.0))

    def project_to_entropy_simplex(
        self,
        raw_authority: np.ndarray,
        target_de_min: float
    ) -> np.ndarray:
        """
        Analytical Convex Projection onto the DE_min-Simplex:
        a*(lambda) = (1 - lambda) * a_raw + lambda * (1/N)
        Guarantees DE(a*) >= DE_min for all iterations.
        """
        n = len(raw_authority)
        current_de = self.calculate_shannon_entropy(raw_authority)

        if current_de >= target_de_min:
            return raw_authority / np.sum(raw_authority)

        # Binary search for optimal minimal lambda in [0, 1]
        low, high = 0.0, 1.0
        best_a = np.full(n, 1.0 / n, dtype=np.float64)

        for _ in range(30):
            mid = (low + high) / 2.0
            candidate_a = (1.0 - mid) * raw_authority + mid * (1.0 / n)
            candidate_a /= np.sum(candidate_a)
            de_val = self.calculate_shannon_entropy(candidate_a)

            if de_val >= target_de_min:
                best_a = candidate_a
                high = mid  # Try to find a smaller lambda (closer to raw)
            else:
                low = mid

        return best_a

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
            return np.full(n, 1.0 / n, dtype=np.float64)

        # Dynamic Boltzmann Selectivity parameter: gamma(G_p)
        gamma = 1.50 * (1.0 + 2.0 * governance_pressure)
        
        # Shifted softmax for numerical stability with baseline smoothing
        shifted_scores = gsf_scores - np.max(gsf_scores)
        weights = np.exp(gamma * shifted_scores)
        
        # Add baseline epsilon to ensure non-zero support across all validators
        eps_floor = 1e-4 / n
        weights = weights + eps_floor
        raw_a = weights / np.sum(weights)

        # Strictly enforce the constitutional lower bound DE >= DE_min
        final_a = self.project_to_entropy_simplex(raw_a, th.de_min)
        return final_a