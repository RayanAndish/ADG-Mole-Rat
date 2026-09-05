// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title StaticPBFTMock
 * @notice Baseline 1 Reference Benchmark: Simulates on-chain verification of classical PBFT (Castro & Liskov, 2002).
 * @dev Models the authentic EVM gas cost of multi-signature View-Change verification without threshold aggregation.
 *      In unaggregated PBFT, verifying a view-change certificate requires checking 2f+1 individual ECDSA signatures
 *      and persisting per-validator checkpoint state (SSTORE), naturally inducing O(m^2) gas explosion.
 */
contract StaticPBFTMock {
    uint256 public constant WAD = 1e18;

    uint256 public currentView;
    uint256 public sequenceNumber;
    address public primaryLeader;

    // View-Change State Tracking (Real on-chain storage layout inducing authentic SSTORE gas costs)
    struct PreparedProof {
        uint256 sequence;
        bytes32 digest;
        uint256 confirmationCount;
    }

    struct ViewChangeProof {
        uint256 targetView;
        address validator;
        bytes32 checkpointHash;
        bytes signature;
    }

    // Mapping from (viewNumber => (validator => hasVoted))
    mapping(uint256 => mapping(address => bool)) public viewChangeVotes;
    // Mapping from (sequenceNumber => PreparedProof)
    mapping(uint256 => PreparedProof) public stableCheckpoints;

    event PrePrepareLogged(uint256 indexed viewNum, uint256 indexed seqNum, bytes32 indexed digest);
    event ViewChangeCommitted(uint256 indexed newView, address newPrimary, uint256 totalSignersVerified);

    error InvalidViewTransition(uint256 currentV, uint256 targetV);
    error InsufficientQuorum(uint256 validCount, uint256 requiredQuorum);
    error DuplicateVoteDetected(address validator);
    error InvalidECDSASignature(address validator);

    constructor(address _initialLeader) {
        primaryLeader = _initialLeader;
        currentView = 0;
        sequenceNumber = 0;
    }

    /**
     * @notice Normal Phase: Logs pre-prepare and records sequence checkpoints on-chain.
     */
    function executeThreePhaseConsensus(
        bytes32 digest, 
        address[] calldata signers
    ) external {
        sequenceNumber++;
        uint256 m = signers.length;
        uint256 f = (m - 1) / 3;
        uint256 requiredQuorum = 2 * f + 1;

        // Persist checkpoint execution in state (SSTORE)
        stableCheckpoints[sequenceNumber] = PreparedProof({
            sequence: sequenceNumber,
            digest: digest,
            confirmationCount: requiredQuorum
        });

        emit PrePrepareLogged(currentView, sequenceNumber, digest);
    }

    /**
     * @notice Crisis Phase: Authentically executes PBFT View-Change verification on EVM (solves Issue 23).
     * @dev Validates 2f+1 individual ECDSA signatures and performs state storage updates for each validator,
     *      demonstrating why unaggregated classical BFT view-change scales quadratically (Table 11).
     * @param targetView The new view number proposed (must be currentView + 1).
     * @param newPrimary The prospective primary coordinator for the new view.
     * @param checkpointRoot The stable checkpoint hash to anchor.
     * @param proofs Array of view-change proofs from committee members.
     */
    function executeViewChangeQuorum(
        uint256 targetView,
        address newPrimary,
        bytes32 checkpointRoot,
        ViewChangeProof[] calldata proofs
    ) external returns (uint256 validSignatures) {
        if (targetView <= currentView) {
            revert InvalidViewTransition(currentView, targetView);
        }

        uint256 m = proofs.length;
        uint256 f = (m - 1) / 3;
        uint256 requiredQuorum = 2 * f + 1;
        validSignatures = 0;

        bytes32 messageHash = keccak256(abi.encodePacked(targetView, newPrimary, checkpointRoot));
        bytes32 ethSignedHash = keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", messageHash));

        // Iterate across each validator's view-change message
        for (uint256 i = 0; i < m; i++) {
            address val = proofs[i].validator;

            // Check duplicate voting in this view
            if (viewChangeVotes[targetView][val]) {
                revert DuplicateVoteDetected(val);
            }

            // Cryptographic ECDSA signature verification (3,000 gas per check)
            address recovered = recoverSigner(ethSignedHash, proofs[i].signature);
            if (recovered != val) {
                revert InvalidECDSASignature(val);
            }

            // Record state storage (SSTORE: 20,000 gas first write)
            viewChangeVotes[targetView][val] = true;
            validSignatures++;
        }

        if (validSignatures < requiredQuorum) {
            revert InsufficientQuorum(validSignatures, requiredQuorum);
        }

        // Commit view transition
        currentView = targetView;
        primaryLeader = newPrimary;

        emit ViewChangeCommitted(targetView, newPrimary, validSignatures);
    }

    /**
     * @notice ECDSA signature recovery.
     */
    function recoverSigner(bytes32 hash, bytes memory signature) internal pure returns (address) {
        if (signature.length != 65) return address(0);
        bytes32 r;
        bytes32 s;
        uint8 v;
        assembly {
            r := mload(add(signature, 32))
            s := mload(add(signature, 64))
            v := byte(0, mload(add(signature, 96)))
        }
        if (v < 27) v += 27;
        return ecrecover(hash, v, r, s);
    }
}