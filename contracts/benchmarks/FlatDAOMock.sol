// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title FlatDAOMock
 * @notice Baseline 3 Reference Benchmark: Simulates standard token-weighted on-chain DAO governance (Governor Bravo style).
 * @dev Models the authentic EVM gas explosion caused by per-voter storage allocation (SSTORE opcodes).
 *      Recording individual voting receipts across m participants naturally scales to 2.86M gas at m=128 (Table 11).
 */
contract FlatDAOMock {
    uint256 public constant WAD = 1e18;
    uint256 public constant VOTING_PERIOD = 3 days;
    uint256 public constant QUORUM_PERCENTAGE = 20; // 20% token quorum required

    struct Proposal {
        bytes32 proposalHash;
        uint256 forVotes;
        uint256 againstVotes;
        uint256 creationTime;
        bool executed;
        uint256 totalVotersCount;
    }

    struct Receipt {
        bool hasVoted;
        uint8 support; // 0 = Against, 1 = For, 2 = Abstain
        uint256 votes;
    }

    // Mapping: proposalId => Proposal
    mapping(uint256 => Proposal) public proposals;
    // Authentic OpenZeppelin / Governor Bravo per-voter storage mapping (induces ~22,000 gas per voter via SSTORE)
    mapping(uint256 => mapping(address => Receipt)) public receipts;
    // Voter token balances
    mapping(address => uint256) public tokenBalance;

    uint256 public proposalCounter;
    uint256 public totalCirculatingSupply;

    event ProposalCreated(uint256 indexed proposalId, bytes32 indexed hash, uint256 creationTime);
    event VoteCast(address indexed voter, uint256 indexed proposalId, uint8 support, uint256 weight);
    event ProposalExecuted(uint256 indexed proposalId);

    error VotingPeriodExpired(uint256 proposalId);
    error VoterAlreadyCastBallot(address voter, uint256 proposalId);
    error InsufficientTokenBalance(address voter);
    error QuorumNotMet(uint256 totalVotes, uint256 requiredQuorum);
    error LengthMismatch();

    constructor(address[] memory initialHolders, uint256[] memory balances) {
        require(initialHolders.length == balances.length, "Mismatched arrays");
        for (uint256 i = 0; i < initialHolders.length; i++) {
            tokenBalance[initialHolders[i]] = balances[i];
            totalCirculatingSupply += balances[i];
        }
    }

    /**
     * @notice Creates a standard DAO governance proposal.
     */
    function createProposal(bytes32 hash) external returns (uint256) {
        proposalCounter++;
        proposals[proposalCounter] = Proposal({
            proposalHash: hash,
            forVotes: 0,
            againstVotes: 0,
            creationTime: block.timestamp,
            executed: false,
            totalVotersCount: 0
        });

        emit ProposalCreated(proposalCounter, hash, block.timestamp);
        return proposalCounter;
    }

    /**
     * @notice Casts an individual token-weighted vote with persistent on-chain receipt storage.
     */
    function castTokenWeightedVote(
        uint256 proposalId,
        uint8 support,
        address voter
    ) public returns (uint256) {
        Proposal storage p = proposals[proposalId];
        if (block.timestamp > p.creationTime + VOTING_PERIOD) {
            revert VotingPeriodExpired(proposalId);
        }

        Receipt storage receipt = receipts[proposalId][voter];
        if (receipt.hasVoted) {
            revert VoterAlreadyCastBallot(voter, proposalId);
        }

        uint256 weight = tokenBalance[voter];
        if (weight == 0) {
            revert InsufficientTokenBalance(voter);
        }

        // Authentic Storage Operations (SSTORE 20,000 gas per voter)
        receipt.hasVoted = true;
        receipt.support = support;
        receipt.votes = weight;

        if (support == 1) {
            p.forVotes += weight;
        } else {
            p.againstVotes += weight;
        }
        p.totalVotersCount++;

        emit VoteCast(voter, proposalId, support, weight);
        return weight;
    }

    /**
     * @notice Batches vote casting across m voters to directly measure Table 11 cumulative gas on EVM.
     * @param proposalId The proposal identifier.
     * @param voters Array of voter addresses (m in [4, 16, 64, 128]).
     * @param supportDecisions Array of vote choices (0 = Against, 1 = For).
     */
    function batchCastVotes(
        uint256 proposalId,
        address[] calldata voters,
        uint8[] calldata supportDecisions
    ) external returns (uint256 totalWeightCast) {
        if (voters.length != supportDecisions.length) revert LengthMismatch();
        uint256 m = voters.length;

        for (uint256 i = 0; i < m; i++) {
            totalWeightCast += castTokenWeightedVote(proposalId, supportDecisions[i], voters[i]);
        }
    }

    /**
     * @notice Simulates proposal execution checking quorum requirements.
     */
    function executeProposal(uint256 proposalId) external returns (bool) {
        Proposal storage p = proposals[proposalId];
        uint256 totalVotes = p.forVotes + p.againstVotes;
        uint256 requiredQuorum = (totalCirculatingSupply * QUORUM_PERCENTAGE) / 100;

        if (totalVotes < requiredQuorum) {
            revert QuorumNotMet(totalVotes, requiredQuorum);
        }
        require(p.forVotes > p.againstVotes, "Proposal rejected by majority");
        p.executed = true;

        emit ProposalExecuted(proposalId);
        return true;
    }
}