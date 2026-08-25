// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title TendermintMock
 * @notice Baseline 3: Simulates canonical Tendermint 2-step consensus (Prevote, Precommit)
 *         and deterministic round-robin leader rotation for gas/latency benchmarking.
 */
contract TendermintMock {
    uint256 public currentHeight;
    uint256 public currentRound;

    address[] public validators;
    mapping(uint256 => mapping(uint256 => bytes32)) public lockedBlocks; // height -> round -> blockHash
    mapping(uint256 => mapping(uint256 => uint256)) public prevoteCount;
    mapping(uint256 => mapping(uint256 => uint256)) public precommitCount;

    event RoundStepExecuted(uint256 indexed height, uint256 indexed round, string step, address proposer);
    event BlockCommitted(uint256 indexed height, bytes32 blockHash, uint256 round);

    constructor(address[] memory _validators) {
        require(_validators.length >= 4, "Minimum 4 validators for BFT");
        validators = _validators;
        currentHeight = 1;
        currentRound = 0;
    }

    /**
     * @notice Deterministic Proposer Selection: Proposer(h, r) = validators[(h + r) % N]
     */
    function getProposer(uint256 height, uint256 round) public view returns (address) {
        return validators[(height + round) % validators.length];
    }

    /**
     * @notice Simulates Tendermint propose -> prevote -> precommit lifecycle.
     */
    function executeTendermintRound(
        bytes32 blockHash,
        uint256 votingPowerSum
    ) external returns (bool committed) {
        address proposer = getProposer(currentHeight, currentRound);
        emit RoundStepExecuted(currentHeight, currentRound, "PROPOSE", proposer);

        // Step 1: 2/3+ Prevote verification gas cost simulation
        uint256 twoThirdsQuorum = (validators.length * 2) / 3 + 1;
        uint256 simulatedPrevotes = 0;
        for (uint256 i = 0; i < twoThirdsQuorum; i++) {
            simulatedPrevotes++;
        }
        prevoteCount[currentHeight][currentRound] = simulatedPrevotes;
        emit RoundStepExecuted(currentHeight, currentRound, "PREVOTE", address(0));

        // Step 2: 2/3+ Precommit verification gas cost simulation
        uint256 simulatedPrecommits = 0;
        for (uint256 i = 0; i < twoThirdsQuorum; i++) {
            simulatedPrecommits++;
        }
        precommitCount[currentHeight][currentRound] = simulatedPrecommits;
        emit RoundStepExecuted(currentHeight, currentRound, "PRECOMMIT", address(0));

        // Commit Block
        lockedBlocks[currentHeight][currentRound] = blockHash;
        emit BlockCommitted(currentHeight, blockHash, currentRound);

        currentHeight++;
        currentRound = 0;
        return true;
    }

    /**
     * @notice Simulates Timeout / Round Skip (Round-Robin Proposer Failover).
     */
    function timeoutSkipRound() external {
        currentRound++;
        emit RoundStepExecuted(currentHeight, currentRound, "TIMEOUT_SKIP", getProposer(currentHeight, currentRound));
    }
}