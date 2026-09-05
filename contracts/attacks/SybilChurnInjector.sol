// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../core/DynamicCommittee.sol";
import "../governance/DynamicGovernanceScore.sol";

/**
 * @title SybilChurnInjector
 * @notice Realistic adversarial test harness injecting high-rate Sybil floods and dynamic validator churn:
 *         1. Verifies Sybil Resistance (Section 6.3): Proves newly spawned identities fail threshold \theta_{act} = 0.20.
 *         2. Models Validator Churn (Section 6.4 & Table 10): Partitions committee into online/offline subsets
 *            to formally validate quorum failure thresholds (churn >= 33.3% preventing minority forks).
 */
contract SybilChurnInjector {
    uint256 public constant WAD = 1e18;

    DynamicCommittee public immutable committee;
    address public owner;

    // Sybil Simulation Parameters (Matching Section 6.3)
    uint256 public constant SYBIL_INITIAL_REPUTATION = 5e16; // 0.05 * 1e18 (low reputation)
    uint256 public constant THETA_ACT = 20e16;              // Activation threshold = 0.20 * 1e18

    address[] public spawnedSybils;
    mapping(address => bool) public isOffline; // Simulates offline/crashed validators during churn
    uint256 public currentChurnPercentage;

    event SybilBatchInjected(uint256 count, uint256 totalSpawned);
    event SybilVerificationResult(address indexed sybil, uint256 gsfScore, bool rejectedByFilter);
    event ChurnStateUpdated(uint256 dropPercentage, uint256 onlineCount, uint256 offlineCount);

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner");
        _;
    }

    constructor(address _committeeAddress) {
        committee = DynamicCommittee(_committeeAddress);
        owner = msg.sender;
    }

    /**
     * @notice Attack Vector 1: Generates N Sybil identities with low initial reputation (Section 6.3).
     */
    function injectSybilFlood(uint256 count) external onlyOwner returns (uint256 successfullyRegistered) {
        successfullyRegistered = 0;
        for (uint256 i = 0; i < count; i++) {
            address sybilAddr = address(uint160(uint256(keccak256(abi.encodePacked(block.timestamp, i, msg.sender)))));
            spawnedSybils.push(sybilAddr);

            try committee.registerValidator(sybilAddr, 10e18, SYBIL_INITIAL_REPUTATION) {
                successfullyRegistered++;
            } catch {
                // Intercepted
            }
        }
        emit SybilBatchInjected(count, spawnedSybils.length);
    }

    /**
     * @notice Verifies that a Sybil node cannot pass the activation threshold \theta_{act} (solves Issue 38).
     * @dev Checks that GSF score evaluated by DynamicGovernanceScore remains strictly < 0.20 * 1e18.
     */
    function verifySybilRejection(
        address gsfScoreContract,
        address sybilAddr
    ) external returns (bool isRejected, uint256 score) {
        DynamicGovernanceScore gsf = DynamicGovernanceScore(gsfScoreContract);

        // Construct telemetry for a fresh Sybil node: zero uptime history, zero participation consistency
        DynamicGovernanceScore.TelemetryInput memory sybilTelemetry = DynamicGovernanceScore.TelemetryInput({
            reliability: 0,                   // Q_i = 0 (no history)
            reputation: SYBIL_INITIAL_REPUTATION, // r_i = 0.05
            capacity: 10e18,                  // c_i = 10 (Fixed: was computeCapacity)
            energyBudget: 1e18,               // e_i = 1.0
            participation: 0,                 // p_i = 0
            queueLoad: 0,                     // w_i = 0
            relativeLatency: 1e18,            // l_i = 1.0 (Fixed: was latencyRel)
            tenureEpochs: 0                   // tau_i = 0
        });

        score = gsf.computeGSF(sybilAddr, sybilTelemetry);
        isRejected = (score < THETA_ACT);

        emit SybilVerificationResult(sybilAddr, score, isRejected);
    }

    /**
     * @notice Attack Vector 2: Simulates sudden validator dropout across churn rates in Table 10 (5% to 50%).
     * @dev Sets a designated fraction of registered validators to offline state.
     */
    function configureValidatorChurn(uint256 dropPercentage) external onlyOwner {
        require(dropPercentage <= 60, "Churn too extreme for testing");
        currentChurnPercentage = dropPercentage;

        uint256 total = committee.getValidatorCount();
        uint256 dropCount = (total * dropPercentage) / 100;

        // Reset previous churn states
        for (uint256 i = 0; i < total; i++) {
            address val = committee.validatorAddresses(i);
            isOffline[val] = false;
        }

        // Set dropCount validators to offline
        for (uint256 i = 0; i < dropCount; i++) {
            address val = committee.validatorAddresses(i);
            isOffline[val] = true;
        }

        uint256 onlineCount = total - dropCount;
        emit ChurnStateUpdated(dropPercentage, onlineCount, dropCount);
    }

    /**
     * @notice Returns the list of strictly online, active validators available to sign handover proposals.
     * @dev Enables benchmark harnesses to test Table 10: whether surviving signers satisfy 2f_m + 1.
     */
    function getOnlineValidators() external view returns (address[] memory onlineNodes) {
        uint256 total = committee.getValidatorCount();
        uint256 onlineCount = 0;

        for (uint256 i = 0; i < total; i++) {
            address val = committee.validatorAddresses(i);
            if (!isOffline[val] && committee.isCommitteeMember(val)) {
                onlineCount++;
            }
        }

        onlineNodes = new address[](onlineCount);
        uint256 idx = 0;
        for (uint256 i = 0; i < total; i++) {
            address val = committee.validatorAddresses(i);
            if (!isOffline[val] && committee.isCommitteeMember(val)) {
                onlineNodes[idx] = val;
                idx++;
            }
        }
    }
}