"""
Lyapunov Tracker Module
Evaluates Theorem 1 energy decay V(S(t)) and verifies asymptotic convergence to equilibrium.
"""

import numpy as np
from offchain_engine.config import ADGSystemConfig


class LyapunovEnergyTracker:
    def __init__(self, config: ADGSystemConfig):
        self.cfg = config
        self.energy_history = []
        self.time_history = []

    def compute_energy(
        self,
        governance_pressure: float,
        decentralization_entropy: float,
        authority_vector: np.ndarray
    ) -> float:
        """
        Evaluates Lyapunov candidate V(S(t)):
        V(S) = 0.5 * (G_p - 0)^2 + 0.5*lambda_de * (1 - DE)^2 + 0.5*lambda_a * sum((a_i - 1/N)^2)
        """
        lp = self.cfg.lyapunov
        n = len(authority_vector)

        term_gp = 0.5 * (governance_pressure ** 2)
        term_de = 0.5 * lp.lambda_de * ((1.0 - decentralization_entropy) ** 2)
        
        uniform_ref = 1.0 / n
        term_a = 0.5 * lp.lambda_a * np.sum((authority_vector - uniform_ref) ** 2)

        total_energy = float(term_gp + term_de + term_a)
        return total_energy

    def record_step(self, step: int, energy_value: float):
        self.time_history.append(step)
        self.energy_history.append(energy_value)

    def verify_dissipation_rate(self) -> float:
        """
        Estimates the empirical exponential decay rate c such that V(t) <= V(0) * exp(-2c * t).
        """
        if len(self.energy_history) < 2:
            return 0.0

        energies = np.array(self.energy_history)
        v0 = energies[0] if energies[0] > 0 else 1e-12
        normalized_energies = np.clip(energies / v0, 1e-15, 1.0)
        
        steps = np.array(self.time_history)
        log_decay = -np.log(normalized_energies[-1]) / (2.0 * max(1, steps[-1]))
        return float(log_decay)