"""
Authority Allocation Engine (ADG Master Engine - Formally Corrected)
Implements Algorithm 1 (Closed-Loop Runtime Control Engine) and
Algorithm 3 (Deterministic Constrained Simplex Projection via Bisection Shrinkage).
Guarantees both:
1. Constitutional Entropy Lower Bound: DE(a) >= DE_min
2. Top-f Byzantine Coalition Authority Invariant: sum_{j=1}^f a_(j) <= rho_max < 1/3
"""

import numpy as np
from offchain_engine.config import ADGSystemConfig
from offchain_engine.governance_pressure import GovernanceMode


class AuthorityAllocator:
    def __init__(self, config: ADGSystemConfig):
        self.cfg = config

    def calculate_shannon_entropy(self, authority_vector: np.ndarray) -> float:
        """
        Evaluates Normalized Shannon Decentralization Entropy (Equation 13):
        DE(a) = - (1 / ln N) * sum(a_i * ln(a_i + eps))
        """
        n = len(authority_vector)
        if n <= 1:
            return 1.0

        p = np.clip(authority_vector, 1e-15, 1.0)
        p = p / np.sum(p)
        raw_entropy = -np.sum(p * np.log(p))
        normalized_de = raw_entropy / np.log(n)
        return float(np.clip(normalized_de, 0.0, 1.0))

    def calculate_top_f_share(self, authority_vector: np.ndarray, f: int) -> float:
        """
        Computes the aggregate authority share accumulated by the top-f highest-weighted nodes.
        Used to enforce the constitutional anti-capture invariant (Equation 14 & Theorem 3).
        """
        n = len(authority_vector)
        if f <= 0:
            return 0.0
        if f >= n:
            return 1.0

        sorted_a = np.sort(authority_vector)
        top_f_sum = float(np.sum(sorted_a[-f:]))
        return top_f_sum

    def calculate_gini_coefficient(self, authority_vector: np.ndarray) -> float:
        """
        Computes the Gini Coefficient of authority concentration:
        G = sum_i sum_j |a_i - a_j| / (2 * N * sum_i a_i)
        G = 0 -> Perfect Equality, G = 1 -> Total Monopoly.
        """
        a = np.sort(authority_vector)
        n = len(a)
        total_sum = np.sum(a)
        if n == 0 or np.isclose(total_sum, 0.0):
            return 0.0

        index = np.arange(1, n + 1)
        gini = (2.0 * np.sum(index * a) - (n + 1) * total_sum) / (n * total_sum)
        return float(np.clip(gini, 0.0, 1.0))

    def project_to_constitutional_simplex(
        self,
        raw_authority: np.ndarray,
        target_de_min: float,
        target_rho_max: float
    ) -> np.ndarray:
        """
        Algorithm 3: Deterministic Constrained Authority Simplex Projection via Bisection Shrinkage.
        Interpolates between raw_authority and the uniform distribution u = [1/N, ..., 1/N]^T:
            a*(lambda) = (1 - lambda) * a_raw + lambda * (1/N)
        Guarantees that the feasible vector satisfies BOTH:
            1. DE(a*) >= DE_min
            2. sum_{j=1}^f a*_(j) <= rho_max < 1/3
        """
        n = len(raw_authority)
        f = self.cfg.get_max_byzantine_nodes(n)
        u = np.full(n, 1.0 / n, dtype=np.float64)

        # Baseline normalization
        p = np.maximum(raw_authority, 0.0)
        p_sum = np.sum(p)
        p = p / p_sum if p_sum > 0 else u.copy()

        # Step 1: Check if raw authority already satisfies constitutional invariants
        current_de = self.calculate_shannon_entropy(p)
        current_top_f = self.calculate_top_f_share(p, f)

        # Theoretical lower bound on top-f share on simplex is f/N (achieved by uniform u)
        # Ensure effective target_rho_max is strictly >= f/N to prevent empty feasible set
        effective_rho_max = max(target_rho_max, (f / n) + 1e-4)

        if current_de >= target_de_min and current_top_f <= effective_rho_max:
            return p

        # Step 2: Binary search for minimal shrinkage parameter lambda in [0, 1]
        low, high = 0.0, 1.0
        best_a = u.copy()

        for _ in range(50):
            mid = (low + high) / 2.0
            candidate_a = (1.0 - mid) * p + mid * u
            candidate_a /= np.sum(candidate_a)

            de_val = self.calculate_shannon_entropy(candidate_a)
            top_f_val = self.calculate_top_f_share(candidate_a, f)

            # Feasibility condition: both constitutional invariants must be satisfied
            if de_val >= target_de_min and top_f_val <= effective_rho_max:
                best_a = candidate_a
                high = mid  # Move closer to raw allocation
            else:
                low = mid   # Shrink further towards uniform distribution

            if (high - low) < 1e-6:
                break

        return best_a

    def allocate_authority(
        self,
        gsf_scores: np.ndarray,
        governance_pressure: float,
        current_mode: GovernanceMode
    ) -> np.ndarray:
        """
        Master Closed-Loop Authority Allocation (Algorithm 1, Lines 15-53).
        Modulates authority shares based on operational regime (Mode 0, 1, 2)
        and projects onto the constitutional simplex.
        """
        n = len(gsf_scores)
        th = self.cfg.thresholds

        # Mode 0: Flat Decentralization (Algorithm 1, Line 19)
        if current_mode == GovernanceMode.MODE_0_FLAT:
            return np.full(n, 1.0 / n, dtype=np.float64)

        # Dynamic Boltzmann Selectivity parameter: gamma(G_p) = gamma_0 * (1 + kappa * G_p)
        gamma = 1.50 * (1.0 + 2.0 * governance_pressure)

        # Mode 1: Adaptive Committee Selection (Algorithm 1, Lines 22-31)
        if current_mode == GovernanceMode.MODE_1_COMMITTEE:
            # Fault-tolerant committee size sizing: m(t) in [m_min, N]
            raw_m = int(np.floor(n * (1.0 - governance_pressure)))
            m = int(np.clip(raw_m, th.m_min, n))

            # Select top-m nodes ranked by GSF score
            top_m_indices = np.argsort(gsf_scores)[-m:]

            raw_a = np.zeros(n, dtype=np.float64)
            committee_scores = gsf_scores[top_m_indices]
            shifted = committee_scores - np.max(committee_scores)
            exp_scores = np.exp(gamma * shifted)

            # Assign Boltzmann distribution over committee members
            raw_a[top_m_indices] = exp_scores / np.sum(exp_scores)

        # Mode 2: Bounded Leadership / Queen Regime (Algorithm 1, Lines 32-44)
        else:
            eligible_mask = (gsf_scores >= th.theta_act)
            if not np.any(eligible_mask):
                return np.full(n, 1.0 / n, dtype=np.float64)

            raw_a = np.zeros(n, dtype=np.float64)
            shifted = gsf_scores - np.max(gsf_scores)
            exp_scores = np.exp(gamma * shifted) * eligible_mask
            raw_a = exp_scores / np.sum(exp_scores)

        # Ensure minimal non-zero exploration baseline
        eps_floor = 1e-6 / n
        raw_a = raw_a + eps_floor
        raw_a /= np.sum(raw_a)

        # Strictly enforce Constitutional Invariants: DE >= DE_min AND Top-f <= rho_max
        final_a = self.project_to_constitutional_simplex(raw_a, th.de_min, th.rho_max)
        return final_a