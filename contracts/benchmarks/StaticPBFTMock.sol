// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title StaticPBFTMock
 * @notice Baseline 1: Simulates classical PBFT three-phase consensus and costly view-change cascade.
 */
contract StaticPBFTMock {
    uint256 public viewNumber;
    address public primaryLeader;
    uint256 public sequenceNumber;

    event PrePrepare(uint256 indexed viewNum, uint256 indexed seqNum, bytes32 digest);
    event ViewChangeCascade(uint256 indexed newView, uint256 messageCount);

    constructor(address _initialLeader) {
        primaryLeader = _initialLeader;
        viewNumber = 0;
    }

    function executeThreePhaseConsensus(bytes32 digest, uint256 nodeCount) external {
        sequenceNumber++;
        emit PrePrepare(viewNumber, sequenceNumber, digest);

        // Simulate O(N^2) prepare and commit message verification gas cost
        uint256 gasSink = 0;
        for (uint256 i = 0; i < nodeCount; i++) {
            gasSink += uint256(keccak256(abi.encodePacked(block.timestamp, i)));
        }
    }

    function triggerViewChange(uint256 nodeCount) external {
        viewNumber++;
        // Simulate O(N^3) message exchange during view-change crisis
        uint256 gasSink = 0;
        for (uint256 i = 0; i < (nodeCount * nodeCount); i++) {
            gasSink += uint256(keccak256(abi.encodePacked(viewNumber, i)));
        }
        emit ViewChangeCascade(viewNumber, nodeCount * nodeCount);
    }
}