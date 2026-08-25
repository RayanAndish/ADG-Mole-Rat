"""
Succession Automaton Module (M_succ)
Implements Algorithm 2: Deterministic Zero-Fork Leadership Handover with Quorum Certificates.
"""

import numpy as np
from enum import Enum
from typing import Optional, Tuple, Dict
from dataclasses import dataclass
from offchain_engine.config import ADGSystemConfig


class SuccessionState(Enum):
    ACTIVE_LEAD = "ACTIVE_LEAD"
    DEGRADATION_DETECTED = "DEGRADATION_DETECTED"
    CANDIDATE_RANKING = "CANDIDATE_RANKING"
    SMOOTH_HANDOVER = "SMOOTH_HANDOVER"
    FALLBACK_CONSENSUS = "FALLBACK_CONSENSUS"


@dataclass
class HandoverCertificate:
    epoch: int
    predecessor_id: int
    successor_id: int
    state_root_hash: str
    quorum_signatures: int
    is_valid: bool


class SuccessionAutomaton:
    def __init__(self, config: ADGSystemConfig):
        self.cfg = config
        self.state = SuccessionState.ACTIVE_LEAD
        self.active_coordinator_id: int = 0
        self.consecutive_epochs: int = 0

    def evaluate_succession_trigger(
        self,
        coordinator_gsf: float,
        coordinator_crashed: bool,
        current_epoch: int
    ) -> bool:
        """
        Checks if the active coordinator has degraded, crashed, or timed out.
        """
        th = self.cfg.thresholds
        self.consecutive_epochs += 1

        if coordinator_crashed:
            self.state = SuccessionState.DEGRADATION_DETECTED
            return True

        if coordinator_gsf < th.theta_succ:
            self.state = SuccessionState.DEGRADATION_DETECTED
            return True

        if self.consecutive_epochs >= th.tau_lead_max:
            self.state = SuccessionState.DEGRADATION_DETECTED
            return True

        return False

    def execute_handover_protocol(
        self,
        epoch: int,
        gsf_scores: np.ndarray,
        byzantine_mask: np.ndarray,
        current_state_hash: str
    ) -> Tuple[Optional[HandoverCertificate], int]:
        """
        Executes Algorithm 2 handover, verifying 2f+1 signatures from non-Byzantine validators.
        """
        n = len(gsf_scores)
        f_max = int((n - 1) // 3)
        required_quorum = 2 * f_max + 1

        # State S2: Candidate Ranking (exclude active coordinator)
        scores_excluding_current = np.copy(gsf_scores)
        scores_excluding_current[self.active_coordinator_id] = -np.inf
        successor_id = int(np.argmax(scores_excluding_current))

        # Simulate Quorum Signature Aggregation
        honest_validators = np.where(~byzantine_mask)[0]
        simulated_valid_signatures = len(honest_validators)

        if simulated_valid_signatures >= required_quorum:
            cert = HandoverCertificate(
                epoch=epoch,
                predecessor_id=self.active_coordinator_id,
                successor_id=successor_id,
                state_root_hash=current_state_hash,
                quorum_signatures=simulated_valid_signatures,
                is_valid=True
            )
            self.active_coordinator_id = successor_id
            self.consecutive_epochs = 0
            self.state = SuccessionState.ACTIVE_LEAD
            return cert, successor_id
        else:
            # Fallback to Mode 0 flat consensus if quorum fails
            self.state = SuccessionState.FALLBACK_CONSENSUS
            return None, -1