"""
Lyapunov Energy Tracker Module (ADG Non-Equilibrium Stability - Formally Corrected)
Implements:
1. Continuous Lyapunov Candidate Energy Function V(S(t), a(t)) (Equation 19).
2. Exponential Asymptotic Stability Verification V(t) <= V(t_0) * exp(-2ct) (Theorem 1 & Equations 28-29).
3. Post-Shock Relaxation Horizon Calculation T_epsilon (Theorem 1).
"""

import numpy as np
from typing import Dict, Any, Tuple
from offchain_engine.config import ADGSystemConfig


class LyapunovEnergyTracker:
    def __init__(self, config: ADGSystemConfig):
        self.cfg = config
        self.energy_history: list[float] = []
        self.time_history: list[int] = []
        self.peak_energy: float = 0.0
        self.peak_epoch: int = 0

    def compute_energy(
        self,
        governance_pressure: float,
        decentralization_entropy: float,
        authority_vector: np.ndarray,
        baseline_pressure: float = 0.0
    ) -> float:
        """
        Evaluates the positive-definite Lyapunov candidate function (Equation 19):
            V(S, a) = 0.5 * (G_p - G_p*)^2 + 0.5 * \lambda_de * (1 - DE)^2 
                    + 0.5 * \lambda_a * sum_{i=1}^N (a_i - 1/N)^2

        Args:
            governance_pressure: Macroscopic pressure G_p(t) in [0, 1].
            decentralization_entropy: Normalized Shannon entropy DE(t) in [0, 1].
            authority_vector: Normalized authority shares a(t) in \Delta^{N-1}.
            baseline_pressure: Nominal equilibrium pressure G_p* (default ~ 0.0).

        Returns:
            total_energy: Positive scalar energy value V(S(t), a(t)) in R+.
        """
        lp = self.cfg.lyapunov
        n = len(authority_vector)

        # Coordinate 1: Pressure potential energy
        term_gp = 0.5 * ((governance_pressure - baseline_pressure) ** 2)

        # Coordinate 2: Constitutional entropy deficit energy
        entropy_deficit = max(0.0, 1.0 - decentralization_entropy)
        term_de = 0.5 * lp.lambda_de * (entropy_deficit ** 2)

        # Coordinate 3: Authority concentration deviation from uniform decentralization
        uniform_share = 1.0 / n if n > 0 else 0.0
        term_a = 0.5 * lp.lambda_a * float(np.sum((authority_vector - uniform_share) ** 2))

        total_energy = float(term_gp + term_de + term_a)
        return total_energy

    def record_step(self, epoch: int, energy_value: float):
        """Records energy observation at consensus epoch."""
        self.time_history.append(epoch)
        self.energy_history.append(energy_value)

        if energy_value > self.peak_energy:
            self.peak_energy = energy_value
            self.peak_epoch = epoch

    def estimate_exponential_decay_rate(self) -> Tuple[float, float]:
        """
        Estimates the empirical exponential dissipation constant c (Theorem 1, Equation 29):
            V(t) <= V(t_peak) * exp(-2c * (t - t_peak))
        
        Performs linear regression on ln(V(t) / V(t_peak)) across the post-shock relaxation phase.

        Returns:
            c: Strictly positive dissipation rate constant.
            r_squared: Coefficient of determination indicating goodness of exponential fit.
        """
        if len(self.energy_history) < 3 or self.peak_epoch >= self.time_history[-1]:
            return self.cfg.lyapunov.convergence_c, 1.0

        times = np.array(self.time_history)
        energies = np.array(self.energy_history)

        # Restrict analysis to post-peak dissipation phase: t >= t_peak
        post_mask = (times >= self.peak_epoch)
        post_times = times[post_mask] - self.peak_epoch
        post_energies = np.maximum(energies[post_mask], 1e-12)

        v_peak = max(self.peak_energy, 1e-12)
        log_ratios = np.log(post_energies / v_peak)

        if len(post_times) < 2:
            return self.cfg.lyapunov.convergence_c, 1.0

        # Fit line: log_ratio = -2c * t
        # Normal equation for slope passing through origin: slope = sum(t * y) / sum(t^2)
        denominator = float(np.sum(post_times ** 2))
        if denominator <= 1e-9:
            return self.cfg.lyapunov.convergence_c, 1.0

        slope = float(np.sum(post_times * log_ratios) / denominator)
        empirical_c = max(0.0001, -slope / 2.0)

        # Compute R^2 of fit
        y_pred = slope * post_times
        ss_tot = float(np.sum((log_ratios - np.mean(log_ratios)) ** 2))
        ss_res = float(np.sum((log_ratios - y_pred) ** 2))
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-9 else 1.0

        return empirical_c, float(np.clip(r_squared, 0.0, 1.0))

    def compute_epsilon_relaxation_time(self, epsilon: float = 1e-3) -> float:
        """
        Calculates theoretical relaxation time to return to epsilon-neighborhood (Theorem 1):
            T_epsilon <= (1 / 2c) * ln( V(t_peak) / epsilon )
        """
        c, _ = self.estimate_exponential_decay_rate()
        v_peak = max(self.peak_energy, epsilon + 1e-9)

        relaxation_horizon = (1.0 / (2.0 * c)) * np.log(v_peak / epsilon)
        return float(max(0.0, relaxation_horizon))

    def get_summary_statistics(self) -> Dict[str, Any]:
        """Returns statistical moments for Lyapunov energy dissipation (Tables 7 and 8)."""
        c_rate, r2 = self.estimate_exponential_decay_rate()
        return {
            "initial_energy": self.energy_history[0] if self.energy_history else 0.0,
            "peak_energy": self.peak_energy,
            "peak_epoch": self.peak_epoch,
            "final_energy": self.energy_history[-1] if self.energy_history else 0.0,
            "dissipation_constant_c": c_rate,
            "fit_r_squared": r2,
            "t_epsilon_recovery": self.compute_epsilon_relaxation_time(epsilon=1e-3)
        }