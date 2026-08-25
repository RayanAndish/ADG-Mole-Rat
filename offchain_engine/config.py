"""
Adaptive Distributed Governance (ADG) - Master Configuration Module
Implements parametric calibration matrix from Table 6.
"""

from dataclasses import dataclass, field
import numpy as np


@dataclass(frozen=True)
class GovernanceWeights:
    """Convex simplex weights for Global State Vector S(t). Normalized to sum 1.0."""
    w_r: float = 0.25  # Risk weight
    w_w: float = 0.20  # Workload weight
    w_f: float = 0.25  # Fault rate weight
    w_c: float = 0.15  # Coordination cost weight
    w_d: float = 0.15  # Decentralization entropy weight

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
    """Multi-factor scoring weights for Dynamic Governance Score (GSF)."""
    beta_q: float = 0.35  # Reliability weight
    beta_r: float = 0.25  # Reputation/Stake weight
    beta_c: float = 0.20  # Compute capacity weight
    beta_p: float = 0.20  # Participation weight
    beta_w: float = 0.40  # Queue load penalty weight
    beta_l: float = 0.60  # Latency penalty weight
    xi: float = 0.05      # Anti-monopoly tenure decay rate per epoch

    def __post_init__(self):
        numerator_sum = self.beta_q + self.beta_r + self.beta_c + self.beta_p
        assert np.isclose(numerator_sum, 1.0, atol=1e-5), f"Numerator weights must sum to 1.0, got {numerator_sum}"


@dataclass(frozen=True)
class SystemThresholds:
    """Constitutional thresholds for regime hysteresis and entropy bounds."""
    theta_low: float = 0.35      # Mode 0 -> Mode 1 transition trigger
    theta_high: float = 0.70     # Mode 1 -> Mode 2 transition trigger
    hysteresis_epsilon: float = 0.05  # State change stabilization buffer
    de_min: float = 0.60         # Constitutional lower bound on Decentralization Entropy (DE)
    theta_act: float = 0.20      # Minimum GSF score for committee eligibility
    theta_succ: float = 0.30     # Coordinator degradation threshold triggering succession
    tau_lead_max: int = 100      # Max consecutive epochs allowed for single coordinator
    byzantine_bound: float = 0.333 # Theoretical limit f < N/3


@dataclass(frozen=True)
class ActuationParams:
    """Biological signaling parameters (IPM suppression & Shoving stimulus)."""
    sigma_0: float = 0.80        # Maximum IPM chemical suppression intensity
    eta: float = 3.00            # IPM exponential sensitivity gain
    delta_decay: float = 0.01    # Half-life decay per unit time
    q_thresh: float = 0.80       # Minimum reliability to receive physical shoving stimulus


@dataclass(frozen=True)
class LyapunovParams:
    """Lyapunov stability and authority decay parameters."""
    kappa_a: float = 0.15        # Asymptotic authority relaxation rate
    lambda_de: float = 1.00      # Scale factor for entropy energy
    lambda_a: float = 0.50       # Scale factor for authority concentration energy
    convergence_c: float = 0.08  # Strictly positive dissipation constant


@dataclass
class ADGSystemConfig:
    """Master wrapper configuration for ADG execution."""
    governance_weights: GovernanceWeights = field(default_factory=GovernanceWeights)
    gsf_weights: GSFWeights = field(default_factory=GSFWeights)
    thresholds: SystemThresholds = field(default_factory=SystemThresholds)
    actuation: ActuationParams = field(default_factory=ActuationParams)
    lyapunov: LyapunovParams = field(default_factory=LyapunovParams)
    random_seed: int = 42
    default_node_count: int = 128