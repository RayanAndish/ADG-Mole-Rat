// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title FlatDAOMock
 * @notice Baseline 2: Simulates token-weighted flat voting DAO exhibiting high voter apathy and proposal latency.
 */
contract FlatDAOMock {
    struct Proposal {
        bytes32 proposalHash;
        uint256 forVotes;
        uint256 againstVotes;
        uint256 creationTime;
        bool executed;
    }

    mapping(uint256 => Proposal) public proposals;
    mapping(address => uint256) public tokenBalance;
    uint256 public proposalCounter;
    uint256 public constant VOTING_PERIOD = 3 days;

    event ProposalCreated(uint256 indexed proposalId, bytes32 hash);
    event VoteCast(address indexed voter, uint256 indexed proposalId, uint256 weight);

    function createProposal(bytes32 hash) external returns (uint256) {
        proposalCounter++;
        proposals[proposalCounter] = Proposal({
            proposalHash: hash,
            forVotes: 0,
            againstVotes: 0,
            creationTime: block.timestamp,
            executed: false
        });
        emit ProposalCreated(proposalCounter, hash);
        return proposalCounter;
    }

    function castTokenWeightedVote(uint256 proposalId, bool support, uint256 tokens) external {
        Proposal storage p = proposals[proposalId];
        require(block.timestamp <= p.creationTime + VOTING_PERIOD, "Voting expired");

        if (support) {
            p.forVotes += tokens;
        } else {
            p.againstVotes += tokens;
        }
        emit VoteCast(msg.sender, proposalId, tokens);
    }
}