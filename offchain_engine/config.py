"""
Adaptive Distributed Governance (ADG) - Master Configuration Module
Implements the revised parametric calibration matrix from Table 6 and constitutional invariants.
"""

from dataclasses import dataclass, field
import numpy as np


@dataclass(frozen=True)
class GovernanceWeights:
    """
    Convex simplex weights for State Vector S(t) = [R, W, F, C, 1 - DE]^T.
    Strictly normalized to sum 1.0 (Matching Table 6).
    """
    w_r: float = 0.25  # Risk / anomaly weight
    w_w: float = 0.20  # Capacity-adjusted workload weight
    w_f: float = 0.20  # Unresponsive / faulty node rate weight
    w_c: float = 0.15  # Coordination gossip cost weight
    w_d: float = 0.20  # Entropy deficit (1 - DE) weight

    def __post_init__(self):
        total = self.w_r + self.w_w + self.w_f + self.w_c + self.w_d
        if not np.isclose(total, 1.0, atol=1e-5):
            object.__setattr__(self, "w_r", self.w_r / total)
            object.__setattr__(self, "w_w", self.w_w / total)
            object.__setattr__(self, "w_f", self.w_f / total)
            object.__setattr__(self, "w_c", self.w_c / total)
            object.__setattr__(self, "w_d", self.w_d / total)


@dataclass(frozen=True)
class GSFWeights:
    """
    Multi-factor scoring weights for Dynamic Governance Score (GSF) (Equation 8).
    Includes energy/resource headroom (beta_e) resolving Issue 18.
    """
    beta_q: float = 0.30  # Reliability uptime weight (Q_i)
    beta_r: float = 0.20  # Reputation / Stake weight (r_i)
    beta_c: float = 0.20  # Compute capacity weight (c_i)
    beta_e: float = 0.15  # Energy / Resource headroom weight (e_i)
    beta_p: float = 0.15  # Historical participation consistency (p_i)
    beta_w: float = 0.40  # Queue load penalty weight (w_i)
    beta_l: float = 0.60  # Latency penalty weight (l_i)
    xi: float = 0.05      # Anti-monopoly coordinator tenure decay rate per epoch

    def __post_init__(self):
        numerator_sum = self.beta_q + self.beta_r + self.beta_c + self.beta_e + self.beta_p
        assert np.isclose(numerator_sum, 1.0, atol=1e-5), (
            f"Numerator weights must sum to 1.0, got {numerator_sum}"
        )


@dataclass(frozen=True)
class SystemThresholds:
    """
    Constitutional thresholds for regime hysteresis, anti-capture invariant, and BFT bounds.
    Implements 4-threshold anti-chattering hysteresis (Equation 7).
    """
    theta_low_down: float = 0.30   # Descending trigger: Mode 1 -> Mode 0
    theta_low_up: float = 0.35     # Ascending trigger: Mode 0 -> Mode 1
    theta_high_down: float = 0.65  # Descending trigger: Mode 2 -> Mode 1
    theta_high_up: float = 0.70    # Ascending trigger: Mode 1 -> Mode 2

    de_min: float = 0.60           # Constitutional lower bound on Normalized Entropy DE(a)
    rho_max: float = 0.32          # Strict upper bound on aggregate authority of top-f nodes (< 1/3)
    
    theta_act: float = 0.20        # Minimum GSF score for committee eligibility
    theta_succ: float = 0.30       # Coordinator degradation threshold triggering succession
    tau_lead_max: int = 100        # Max consecutive epochs allowed for a single coordinator
    byzantine_bound: float = 0.333 # Classical BFT limit f < N/3
    m_min: int = 16                # Fault-tolerant lower bound on committee size (m >= 3f_m + 1)


@dataclass(frozen=True)
class ActuationParams:
    """
    Biological signaling parameters (IPM suppression & Shoving stimulus) (Equations 10-12).
    """
    sigma_0: float = 0.80        # Maximum IPM chemical suppression intensity
    eta: float = 3.00            # IPM exponential sensitivity gain
    delta_decay: float = 0.10    # Natural pheromone dissipation per epoch (Table 6)
    bw_min: float = 0.20         # Constitutional bandwidth floor (Equation 11)
    q_thresh: float = 0.80       # Minimum reliability to receive physical shoving stimulus


@dataclass(frozen=True)
class LyapunovParams:
    """
    Lyapunov stability and authority relaxation parameters (Theorem 1 & Equations 19-29).
    """
    kappa_a: float = 0.15        # Authority relaxation rate towards uniform decentralization
    lambda_de: float = 1.00      # Energy scale factor for entropy deficit
    lambda_a: float = 0.50       # Energy scale factor for authority concentration deviation
    convergence_c: float = 0.08  # Exponential dissipation constant (V(t) <= V(0) * exp(-2ct))


@dataclass
class ADGSystemConfig:
    """
    Master configuration container orchestrating the ADG execution pipeline.
    """
    governance_weights: GovernanceWeights = field(default_factory=GovernanceWeights)
    gsf_weights: GSFWeights = field(default_factory=GSFWeights)
    thresholds: SystemThresholds = field(default_factory=SystemThresholds)
    actuation: ActuationParams = field(default_factory=ActuationParams)
    lyapunov: LyapunovParams = field(default_factory=LyapunovParams)
    random_seed: int = 42
    default_node_count: int = 128

    def get_max_byzantine_nodes(self, n: int) -> int:
        """Returns maximum Byzantine nodes f = floor((n - 1) / 3)."""
        return max(0, (n - 1) // 3)