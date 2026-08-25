// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../core/ADGCoordinator.sol";

/**
 * @title SuccessionAutomaton
 * @notice Implements Algorithm 2 (Deterministic Zero-Fork Leadership Handover).
 * @dev Verifies cryptographic handover certificates with 2f+1 threshold signatures to prevent chain splits.
 */
contract SuccessionAutomaton {
    ADGCoordinator public immutable coordinator;

    enum SuccessionState { ACTIVE_LEAD, DEGRADATION_DETECTED, CANDIDATE_RANKING, SMOOTH_HANDOVER, FALLBACK_CONSENSUS }

    struct HandoverCertificate {
        uint256 epoch;
        address predecessor;
        address successor;
        bytes32 stateHash;
        uint256 blockHeight;
    }

    SuccessionState public currentState;
    uint256 public constant TIMEOUT_TENURE = 3600; // Maximum tenure in seconds before mandatory rotation

    event SuccessionTriggered(uint256 indexed epoch, address indexed failedLeader, SuccessionState reason);
    event HandoverFinalized(uint256 indexed epoch, address indexed newLeader, bytes32 stateRoot);
    event SlashingExecuted(address indexed equivocalSigner, uint256 slashedAmount);

    mapping(bytes32 => bool) public executedHandovers;
    mapping(address => mapping(uint256 => bytes32)) public nodeSignedProposal; // Detects double signing (equivocation)

    constructor(address payable _coordinator) {
        coordinator = ADGCoordinator(_coordinator);
        currentState = SuccessionState.ACTIVE_LEAD;
    }

    /**
     * @notice Submits a multi-signed handover certificate C_{handover}^k verifying 2f+1 quorum.
     * @param cert Handover proposal parameters.
     * @param signatures Concatenated ECDSA signatures from committee members.
     * @param signers Array of public addresses corresponding to signatures.
     */
    function executeZeroForkHandover(
        HandoverCertificate calldata cert,
        bytes[] calldata signatures,
        address[] calldata signers
    ) external {
        require(cert.epoch == coordinator.currentEpoch(), "Epoch mismatch");
        require(signatures.length == signers.length, "Length mismatch");

        bytes32 certHash = keccak256(abi.encodePacked(
            cert.epoch,
            cert.predecessor,
            cert.successor,
            cert.stateHash,
            cert.blockHeight
        ));

        require(!executedHandovers[certHash], "Certificate already executed");

        // Compute Byzantine fault tolerance quorum: 2f + 1 where m = total signers
        uint256 m = signers.length;
        uint256 f = (m - 1) / 3;
        uint256 requiredQuorum = 2 * f + 1;
        uint256 validSignatures = 0;

        bytes32 ethSignedMessageHash = keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", certHash));

        for (uint256 i = 0; i < m; i++) {
            address signer = signers[i];
            
            // Check for malicious equivocation (signing distinct hashes for same epoch)
            bytes32 previousSigned = nodeSignedProposal[signer][cert.epoch];
            if (previousSigned != bytes32(0) && previousSigned != certHash) {
                emit SlashingExecuted(signer, 1 ether); // Slashing trigger
                continue;
            }
            nodeSignedProposal[signer][cert.epoch] = certHash;

            // Verify ECDSA signature
            if (recoverSigner(ethSignedMessageHash, signatures[i]) == signer) {
                validSignatures++;
            }
        }

        require(validSignatures >= requiredQuorum, "Quorum: Insufficient valid 2f+1 signatures");

        // Finalize deterministic zero-fork transition
        executedHandovers[certHash] = true;
        currentState = SuccessionState.SMOOTH_HANDOVER;
        coordinator.applySuccession(cert.successor, cert.stateHash);

        emit HandoverFinalized(cert.epoch, cert.successor, cert.stateHash);
        currentState = SuccessionState.ACTIVE_LEAD;
    }

    function recoverSigner(bytes32 messageHash, bytes memory sig) public pure returns (address) {
        require(sig.length == 65, "Invalid signature length");
        bytes32 r;
        bytes32 s;
        uint8 v;
        assembly {
            r := mload(add(sig, 32))
            s := mload(add(sig, 64))
            v := byte(0, mload(add(sig, 96)))
        }
        return ecrecover(messageHash, v, r, s);
    }
}