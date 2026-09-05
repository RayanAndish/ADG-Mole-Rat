// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title TendermintMock
 * @notice Baseline 2 Reference Benchmark: Simulates on-chain Tendermint Core consensus (Buchman et al., 2018).
 * @dev Models authentic EVM execution costs of Tendermint's two-step Prevote/Precommit validation
 *      and Proof-of-Lock (POL) state transitions with > 2/3 voting power quorum verification (Table 11).
 */
contract TendermintMock {
    uint256 public constant WAD = 1e18;

    uint256 public currentHeight;
    uint256 public currentRound;

    address[] public validatorSet;
    mapping(address => bool) public isValidator;
    mapping(address => uint256) public votingPower; // Voting power in WAD
    uint256 public totalVotingPower;

    // Proof-of-Lock (POL) State Storage
    struct LockedBlockRecord {
        bytes32 blockHash;
        uint256 round;
        uint256 accumulatedPower;
        bool isFinalized;
    }

    struct ValidatorVote {
        address validator;
        bytes signature;
    }

    // Mapping: height => round => LockedBlockRecord
    mapping(uint256 => mapping(uint256 => LockedBlockRecord)) public polRegistry;
    // Mapping: height => finalizedBlockHash
    mapping(uint256 => bytes32) public finalizedChain;
    // Mapping: height => round => validator => hasPrecommitted (Fixed storage mapping)
    mapping(uint256 => mapping(uint256 => mapping(address => bool))) public hasPrecommitted;

    event RoundStepLogged(uint256 indexed height, uint256 indexed round, string step, address indexed proposer);
    event BlockFinalized(uint256 indexed height, bytes32 blockHash, uint256 round, uint256 votingPowerCommitted);
    event RoundTimedOut(uint256 indexed height, uint256 skippedRound, uint256 nextRound, address nextProposer);

    error OnlyAuthorizedValidator(address caller);
    error QuorumNotAchieved(uint256 accumulatedPower, uint256 requiredQuorum);
    error InvalidVoteSignature(address validator);
    error DuplicateVote(address validator);

    constructor(address[] memory _validators) {
        require(_validators.length >= 4, "Minimum 4 validators for BFT resilience");
        validatorSet = _validators;
        currentHeight = 1;
        currentRound = 0;

        uint256 uniformPower = WAD / _validators.length;
        for (uint256 i = 0; i < _validators.length; i++) {
            address val = _validators[i];
            isValidator[val] = true;
            votingPower[val] = uniformPower;
            totalVotingPower += uniformPower;
        }
    }

    function getProposer(uint256 height, uint256 round) public view returns (address) {
        return validatorSet[(height + round) % validatorSet.length];
    }

    function executeTendermintCommit(
        bytes32 blockHash,
        ValidatorVote[] calldata precommitVotes
    ) external returns (bool) {
        address proposer = getProposer(currentHeight, currentRound);
        emit RoundStepLogged(currentHeight, currentRound, "PROPOSE", proposer);

        uint256 requiredQuorum = (totalVotingPower * 2) / 3 + 1;
        uint256 accumulatedPower = 0;

        bytes32 voteDigest = keccak256(abi.encodePacked(currentHeight, currentRound, "PRECOMMIT", blockHash));
        bytes32 ethSignedDigest = keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", voteDigest));

        for (uint256 i = 0; i < precommitVotes.length; i++) {
            address val = precommitVotes[i].validator;

            if (!isValidator[val]) {
                revert OnlyAuthorizedValidator(val);
            }

            if (hasPrecommitted[currentHeight][currentRound][val]) {
                revert DuplicateVote(val);
            }

            address recovered = recoverSigner(ethSignedDigest, precommitVotes[i].signature);
            if (recovered != val) {
                revert InvalidVoteSignature(val);
            }

            hasPrecommitted[currentHeight][currentRound][val] = true;
            accumulatedPower += votingPower[val];

            if (accumulatedPower >= requiredQuorum) {
                break;
            }
        }

        if (accumulatedPower < requiredQuorum) {
            revert QuorumNotAchieved(accumulatedPower, requiredQuorum);
        }

        polRegistry[currentHeight][currentRound] = LockedBlockRecord({
            blockHash: blockHash,
            round: currentRound,
            accumulatedPower: accumulatedPower,
            isFinalized: true
        });

        finalizedChain[currentHeight] = blockHash;
        emit BlockFinalized(currentHeight, blockHash, currentRound, accumulatedPower);

        currentHeight++;
        currentRound = 0;
        return true;
    }

    function timeoutSkipRound() external {
        uint256 oldRound = currentRound;
        currentRound++;
        address nextProposer = getProposer(currentHeight, currentRound);
        emit RoundTimedOut(currentHeight, oldRound, currentRound, nextProposer);
    }

    function recoverSigner(bytes32 hash, bytes memory sig) internal pure returns (address) {
        if (sig.length != 65) return address(0);
        bytes32 r;
        bytes32 s;
        uint8 v;
        assembly {
            r := mload(add(sig, 32))
            s := mload(add(sig, 64))
            v := byte(0, mload(add(sig, 96)))
        }
        if (v < 27) v += 27;
        return ecrecover(hash, v, r, s);
    }
}