"""
Succession Automaton Module (M_succ - Formally Corrected)
Implements Algorithm 2: Deterministic Zero-Fork Leadership Handover Protocol.
Enforces:
1. Deterministic Candidate Selection with Lexicographical Tie-Breaking (Equation 17).
2. Committee-Relative Quorum Verification: strictly >= 2f_m + 1 valid signatures (Equation 18).
3. Realistic Churn and Offline Fault Isolation validating Table 10 (Lemma 1 & Theorem 2).
"""

import numpy as np
from enum import Enum
from typing import Optional, Tuple, Dict, List
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
    active_committee_size: int
    quorum_signatures: int
    required_quorum: int
    handover_latency_ms: float
    is_valid: bool


class SuccessionAutomaton:
    def __init__(self, config: ADGSystemConfig):
        self.cfg = config
        self.state = SuccessionState.ACTIVE_LEAD
        self.active_coordinator_id: int = 0
        self.consecutive_epochs: int = 0
        self.base_network_delay_ms: float = 7.0  # One-way overlay latency Delta

    def evaluate_succession_trigger(
        self,
        coordinator_gsf: float,
        coordinator_crashed: bool,
        current_epoch: int
    ) -> bool:
        """
        Evaluates whether failover should be triggered (Algorithm 1, Line 64 & Section 3.7):
        1. Performance degradation: GSF < theta_succ (0.30).
        2. Heartbeat crash failure.
        3. Maximum leadership tenure exceeded: tau >= tau_lead_max (100 epochs).
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
        current_state_hash: str,
        offline_mask: Optional[np.ndarray] = None,
        active_committee_indices: Optional[np.ndarray] = None
    ) -> Tuple[Optional[HandoverCertificate], int]:
        """
        Executes Algorithm 2 handover verifying 2f_m + 1 supermajority quorum.

        Args:
            epoch: Consensus epoch index k.
            gsf_scores: (N,) array of suitability scores GS_i(t).
            byzantine_mask: (N,) boolean array (True = malicious / Byzantine).
            current_state_hash: Canonical state root hash H_k.
            offline_mask: (N,) boolean array (True = crashed / offline due to churn).
            active_committee_indices: Sub-committee V_active. If None, full set V is used.

        Returns:
            Tuple of (HandoverCertificate or None, successor_node_id).
        """
        n = len(gsf_scores)
        if offline_mask is None:
            offline_mask = np.zeros(n, dtype=bool)

        # 1. Determine active committee V_active
        if active_committee_indices is not None and len(active_committee_indices) >= 4:
            committee = np.array(active_committee_indices, dtype=int)
        else:
            committee = np.arange(n, dtype=int)

        m = len(committee)
        # BFT Committee Bound: f_m = floor((m - 1) / 3), Quorum = 2 * f_m + 1
        f_m = max(1, (m - 1) // 3)
        required_quorum = 2 * f_m + 1

        # 2. State S2: Candidate Ranking with Deterministic Tie-Breaking (Algorithm 2, Lines 10-13)
        self.state = SuccessionState.CANDIDATE_RANKING
        eligible_candidates = [idx for idx in committee if idx != self.active_coordinator_id]

        if not eligible_candidates:
            self.state = SuccessionState.FALLBACK_CONSENSUS
            return None, -1

        # Deterministic sorting key: (-GSF_score, node_id)
        candidate_ranks = sorted(
            eligible_candidates,
            key=lambda idx: (-gsf_scores[idx], idx)
        )
        successor_id = candidate_ranks[0]

        # 3. State S3: Quorum Signature Aggregation (Algorithm 2, Lines 18-34)
        # Signers must be members of V_active, strictly online, and honest
        valid_signers: List[int] = []
        for node_id in committee:
            is_byzantine = byzantine_mask[node_id]
            is_offline = offline_mask[node_id]

            # Byzantine nodes may withhold signatures; offline nodes cannot transmit
            if not is_byzantine and not is_offline:
                valid_signers.append(node_id)

        valid_signature_count = len(valid_signers)

        # 4. Measure Handover Latency: T_handover = 2*Delta + tau_rank + tau_BLS (Theorem 2)
        # tau_rank = O(m log m) ~ 0.05 ms, tau_BLS = ~ 1.0 ms
        sorting_delay_ms = 0.005 * m * np.log2(max(2, m))
        bls_aggregation_ms = 0.02 * valid_signature_count
        handover_latency = float(2.0 * self.base_network_delay_ms + sorting_delay_ms + bls_aggregation_ms)

        # 5. Quorum Decision (Algorithm 2, Line 36)
        if valid_signature_count >= required_quorum:
            cert = HandoverCertificate(
                epoch=epoch,
                predecessor_id=self.active_coordinator_id,
                successor_id=successor_id,
                state_root_hash=current_state_hash,
                active_committee_size=m,
                quorum_signatures=valid_signature_count,
                required_quorum=required_quorum,
                handover_latency_ms=round(handover_latency, 2),
                is_valid=True
            )

            # Smooth Handover State S4 (Algorithm 2, Line 41)
            self.state = SuccessionState.SMOOTH_HANDOVER
            self.active_coordinator_id = successor_id
            self.consecutive_epochs = 0
            self.state = SuccessionState.ACTIVE_LEAD
            return cert, successor_id
        else:
            # Fallback to Mode 0 flat gossip consensus to preserve safety (Algorithm 2, Line 52)
            self.state = SuccessionState.FALLBACK_CONSENSUS
            return None, -1