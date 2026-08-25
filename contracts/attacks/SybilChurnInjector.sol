// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../core/DynamicCommittee.sol";

/**
 * @title SybilChurnInjector
 * @notice Adversarial test harness to inject high-frequency node churn, Sybil floods,
 *         and sudden validator dropout on local and testnet environments.
 */
contract SybilChurnInjector {
    DynamicCommittee public immutable committee;
    address public owner;

    address[] public spawnedSybils;
    bool public churnActive;

    event SybilBatchInjected(uint256 count, uint256 totalRegistered);
    event ChurnBurstTriggered(uint256 droppedCount, uint256 remainingActive);

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner");
        _;
    }

    constructor(address _committeeAddress) {
        committee = DynamicCommittee(_committeeAddress);
        owner = msg.sender;
    }

    /**
     * @notice Generates and registers N synthetic Sybil identities.
     */
    function injectSybilFlood(uint256 count) external onlyOwner {
        for (uint256 i = 0; i < count; i++) {
            address sybilAddr = address(uint160(uint256(keccak256(abi.encodePacked(block.timestamp, i, msg.sender)))));
            spawnedSybils.push(sybilAddr);
            // Attempt to register with minimal capacity to dilute entropy
            committee.registerValidator(sybilAddr, 10e18, 5e16); // Low reputation
        }
        emit SybilBatchInjected(count, spawnedSybils.length);
    }

    /**
     * @notice Simulates sudden offline churn of up to 40% of the active validator set.
     */
    function triggerChurnBurst(uint256 dropPercentage) external onlyOwner {
        require(dropPercentage <= 50, "Churn exceeds testing safety bound");
        uint256 total = committee.getValidatorCount();
        uint256 dropCount = (total * dropPercentage) / 100;

        churnActive = true;
        emit ChurnBurstTriggered(dropCount, total - dropCount);
    }
}