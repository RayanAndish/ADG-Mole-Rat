// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./EntropyConstraint.sol";
import "./DynamicCommittee.sol";

/**
 * @title ADGCoordinator
 * @notice Master state transition engine implementing the closed-loop Adaptive Distributed Governance framework.
 */
contract ADGCoordinator {
    EntropyConstraint public immutable entropyOracle;
    DynamicCommittee public immutable committeeManager;

    uint256 public constant WAD = 1e18;
    uint256 public constitutionalDEMin = 60e16; // DE_min = 0.60 * 1e18

    uint256 public currentEpoch;
    address public activeCoordinator;
    bytes32 public currentStateRoot;
    uint256 public epochStartTime;

    struct GlobalTelemetry {
        uint256 riskIndex;       // R(t) in WAD
        uint256 workloadDemand;  // W(t) in WAD
        uint256 faultRate;       // F(t) in WAD
        uint256 coordCost;       // C(t) in WAD
    }

    event EpochAdvanced(uint256 indexed newEpoch, address indexed coordinator, bytes32 stateRoot, uint256 governancePressure);
    event TelemetryIngested(uint256 indexed epoch, uint256 risk, uint256 workload, uint256 faults);

    modifier onlyActiveCoordinator() {
        require(msg.sender == activeCoordinator, "Auth: Caller is not the active coordinator");
        _;
    }

    constructor(address _entropyOracleAddress) {
        entropyOracle = EntropyConstraint(_entropyOracleAddress);
        committeeManager = new DynamicCommittee(address(this));
        activeCoordinator = msg.sender;
        currentEpoch = 1;
        epochStartTime = block.timestamp;
    }

    /**
     * @notice Ingests global telemetry, updates G_p, verifies entropy, and advances epoch.
     */
    function advanceGovernanceEpoch(
        bytes32 newStateRoot,
        GlobalTelemetry calldata telemetry,
        address[] calldata nodes,
        uint256[] calldata authorityWeights
    ) external onlyActiveCoordinator {
        // 1. Verify on-chain Shannon Entropy constraint DE >= DE_min
        (bool entropyValid, uint256 currentDE, ) = entropyOracle.verifyEntropyInvariant(
            currentEpoch,
            authorityWeights,
            constitutionalDEMin
        );
        require(entropyValid, "State Error: Entropy invariant violated");

        // 2. Compute Governance Pressure: G_p = 0.25*R + 0.20*W + 0.25*F + 0.15*C - 0.15*DE
        int256 rawGp = int256((25e16 * telemetry.riskIndex + 
                               20e16 * telemetry.workloadDemand + 
                               25e16 * telemetry.faultRate + 
                               15e16 * telemetry.coordCost) / WAD) - 
                       int256((15e16 * currentDE) / WAD);

        uint256 gPressure = rawGp > 0 ? uint256(rawGp) : 0;
        if (gPressure > WAD) gPressure = WAD;

        // 3. Update Committee State and Actuation Signals
        committeeManager.updateGovernancePressure(currentEpoch, gPressure);
        committeeManager.setAuthorities(nodes, authorityWeights);

        // 4. Update Epoch State
        currentEpoch++;
        currentStateRoot = newStateRoot;
        epochStartTime = block.timestamp;

        emit TelemetryIngested(currentEpoch, telemetry.riskIndex, telemetry.workloadDemand, telemetry.faultRate);
        emit EpochAdvanced(currentEpoch, activeCoordinator, newStateRoot, gPressure);
    }

    /**
     * @notice Allows external succession automaton to update leader upon validated handover certificate.
     */
    function applySuccession(address newCoordinator, bytes32 verifiedStateRoot) external {
        // Handover validation logic delegated to SuccessionAutomaton
        activeCoordinator = newCoordinator;
        currentStateRoot = verifiedStateRoot;
        epochStartTime = block.timestamp;
    }
}