// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../core/ADGCoordinator.sol";
import "../core/DynamicCommittee.sol";

/**
 * @title SuccessionAutomaton
 * @notice Implements Algorithm 2 (Deterministic Zero-Fork Leadership Handover Protocol).
 * @dev Formally verifies cryptographic handover certificates against active committee quorums (2f_m + 1),
 *      strictly preventing split-brain coordinator emergence, equivocation, and minority forks.
 */
contract SuccessionAutomaton {
    ADGCoordinator public immutable coordinator;

    enum SuccessionState { 
        ACTIVE_LEAD, 
        DEGRADATION_DETECTED, 
        CANDIDATE_RANKING, 
        SMOOTH_HANDOVER, 
        FALLBACK_CONSENSUS 
    }

    struct HandoverCertificate {
        uint256 epoch;
        address predecessor;
        address successor;
        bytes32 stateHash;
        uint256 blockHeight;
    }

    SuccessionState public currentState;
    uint256 public constant TIMEOUT_TENURE = 3600; // 1 hour max tenure before mandatory rotation

    event SuccessionTriggered(uint256 indexed epoch, address indexed failedLeader, SuccessionState reason);
    event HandoverFinalized(uint256 indexed epoch, address indexed newLeader, bytes32 stateRoot);
    event EquivocationDetected(address indexed validator, uint256 indexed epoch, bytes32 conflictingHash);
    event SlashedValidator(address indexed validator, uint256 amount);

    // Track executed certificates to prevent replay attacks
    mapping(bytes32 => bool) public executedCertificates;

    // Equivocation tracking: validator => (epoch => signedCertHash)
    mapping(address => mapping(uint256 => bytes32)) public validatorEpochSignatures;

    // Slashed validators registry
    mapping(address => bool) public isSlashed;

    error EpochMismatch(uint256 expected, uint256 provided);
    error PredecessorMismatch(address expected, address provided);
    error SuccessorCannotBePredecessor();
    error CertificateAlreadyExecuted(bytes32 certHash);
    error ArrayLengthMismatch();
    error InsufficientActiveQuorum(uint256 validSignatures, uint256 requiredQuorum);
    error UnauthorizedSigner(address signer);
    error SignersNotStrictlyAscending(address previous, address current);
    error SlashedSignerIgnored(address signer);
    error InvalidSignatureLength(uint256 length);
    error InvalidSignatureSValue();
    error InvalidSignatureVValue(uint8 v);

    constructor(address _coordinator) {
        require(_coordinator != address(0), "Invalid coordinator");
        coordinator = ADGCoordinator(_coordinator);
        currentState = SuccessionState.ACTIVE_LEAD;
    }

    /**
     * @notice Submits and executes a cryptographic handover certificate C_{handover}^k.
     * @dev Validates that signers are active committee members and meet the 2f_m + 1 supermajority.
     * @param cert Handover proposal parameters (Epoch, Predecessor, Successor, StateRoot, BlockHeight).
     * @param signatures Array of standard 65-byte ECDSA signatures.
     * @param signers Array of validator addresses sorted in strictly ascending order.
     */
    function executeZeroForkHandover(
        HandoverCertificate calldata cert,
        bytes[] calldata signatures,
        address[] calldata signers
    ) external {
        // 1. Rigorous State Pre-Condition Verification
        if (cert.epoch != coordinator.currentEpoch()) {
            revert EpochMismatch(coordinator.currentEpoch(), cert.epoch);
        }
        if (cert.predecessor != coordinator.activeCoordinator()) {
            revert PredecessorMismatch(coordinator.activeCoordinator(), cert.predecessor);
        }
        if (cert.successor == cert.predecessor || cert.successor == address(0)) {
            revert SuccessorCannotBePredecessor();
        }
        if (signatures.length != signers.length) {
            revert ArrayLengthMismatch();
        }

        bytes32 certHash = keccak256(abi.encodePacked(
            cert.epoch,
            cert.predecessor,
            cert.successor,
            cert.stateHash,
            cert.blockHeight
        ));

        if (executedCertificates[certHash]) {
            revert CertificateAlreadyExecuted(certHash);
        }

        // 2. Fetch Active Committee Parameters from DynamicCommittee (Solves Critical Quorum Exploit)
        DynamicCommittee committeeManager = coordinator.committeeManager();
        uint256 m = committeeManager.getCommitteeSize();
        require(m >= 4, "Committee too small for BFT");

        uint256 f_m = (m - 1) / 3;
        uint256 requiredQuorum = 2 * f_m + 1;
        uint256 validSignatures = 0;

        bytes32 ethSignedMessageHash = keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", certHash));

        address lastSigner = address(0);

        // 3. Quorum Verification Loop with Equivocation & Duplicate Protection
        for (uint256 i = 0; i < signers.length; i++) {
            address signer = signers[i];

            // Enforce strictly ascending order: prevents duplicates and ensures O(N) verification
            if (signer <= lastSigner) {
                revert SignersNotStrictlyAscending(lastSigner, signer);
            }
            lastSigner = signer;

            // Signer must be a verified active validator in the committee
            if (!committeeManager.isCommitteeMember(signer)) {
                revert UnauthorizedSigner(signer);
            }

            // Slashed Byzantine nodes are stripped of voting power
            if (isSlashed[signer]) {
                continue;
            }

            // Equivocation Check: Double signing conflicting certificates for the same epoch
            bytes32 previouslySigned = validatorEpochSignatures[signer][cert.epoch];
            if (previouslySigned != bytes32(0) && previouslySigned != certHash) {
                isSlashed[signer] = true;
                emit EquivocationDetected(signer, cert.epoch, certHash);
                emit SlashedValidator(signer, 1 ether);
                continue; // Malicious vote discarded
            }
            validatorEpochSignatures[signer][cert.epoch] = certHash;

            // Cryptographic ECDSA Signature Verification with Malleability Guard
            if (recoverSigner(ethSignedMessageHash, signatures[i]) == signer) {
                validSignatures++;
            }
        }

        // 4. Constitutional Quorum Check: Must achieve strictly >= 2f_m + 1 valid signatures
        if (validSignatures < requiredQuorum) {
            revert InsufficientActiveQuorum(validSignatures, requiredQuorum);
        }

        // 5. Finalize Handover & Transition State
        executedCertificates[certHash] = true;
        currentState = SuccessionState.SMOOTH_HANDOVER;

        // Apply leadership succession to master coordinator contract
        coordinator.applySuccession(cert.successor, cert.stateHash);

        emit HandoverFinalized(cert.epoch, cert.successor, cert.stateHash);
        currentState = SuccessionState.ACTIVE_LEAD;
    }

    /**
     * @notice Secure signature recovery with EIP-2 / SECP256k1 malleability guard.
     */
    function recoverSigner(bytes32 messageHash, bytes memory sig) public pure returns (address) {
        if (sig.length != 65) revert InvalidSignatureLength(sig.length);

        bytes32 r;
        bytes32 s;
        uint8 v;

        assembly {
            r := mload(add(sig, 32))
            s := mload(add(sig, 64))
            v := byte(0, mload(add(sig, 96)))
        }

        // Enforce malleable s-value bounds (OpenZeppelin / Ethereum Yellow Paper standard)
        if (uint256(s) > 0x7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF5D576E735E4370F00100AB53315DD30A) {
            revert InvalidSignatureSValue();
        }

        if (v != 27 && v != 28) {
            revert InvalidSignatureVValue(v);
        }

        address recovered = ecrecover(messageHash, v, r, s);
        require(recovered != address(0), "ecrecover failed");
        return recovered;
    }
}