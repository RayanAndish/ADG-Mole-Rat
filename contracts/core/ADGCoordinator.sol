// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./EntropyConstraint.sol";
import "./DynamicCommittee.sol";

/**
 * @title ADGCoordinator
 * @notice Master closed-loop state transition engine implementing Adaptive Distributed Governance (ADG).
 * @dev Enforces constitutional anti-capture bounds, evaluates dynamic governance pressure (G_p),
 *      and executes non-chattering dual-threshold hysteresis mode transitions.
 */
contract ADGCoordinator {
    EntropyConstraint public immutable entropyOracle;
    DynamicCommittee public immutable committeeManager;

    uint256 public constant WAD = 1e18;

    // Constitutional Invariant Limits
    uint256 public constitutionalDEMin = 60e16;  // DE_min = 0.60 * 1e18
    uint256 public constitutionalRhoMax = 32e16; // rho_max = 0.32 * 1e18 (< 1/3 WAD)

    // Governance State Weights (Sum strictly normalized to 1.0 * 1e18)
    uint256 public weightR = 25e16; // Risk weight = 0.25
    uint256 public weightW = 20e16; // Workload demand weight = 0.20
    uint256 public weightF = 20e16; // Fault rate weight = 0.20
    uint256 public weightC = 15e16; // Coordination cost weight = 0.15
    uint256 public weightD = 20e16; // Entropy deficit (1 - DE) weight = 0.20

    // Four-Threshold Hysteresis Boundaries (Equation 7)
    uint256 public thetaLowDown = 30e16;  // 0.30 * 1e18
    uint256 public thetaLowUp = 35e16;    // 0.35 * 1e18
    uint256 public thetaHighDown = 65e16; // 0.65 * 1e18
    uint256 public thetaHighUp = 70e16;   // 0.70 * 1e18

    // IPM Attenuation Signal Parameters (Equation 10)
    uint256 public sigma0 = 80e16; // Max attenuation = 0.80 * 1e18

    // Operational Regimes
    enum GovernanceMode {
        Mode0_FlatDecentralization,
        Mode1_AdaptiveCommittee,
        Mode2_BoundedLeadership
    }

    GovernanceMode public currentMode;
    uint256 public currentEpoch;
    address public activeCoordinator;
    address public successionAutomaton;
    bytes32 public currentStateRoot;
    uint256 public epochStartTime;
    uint256 public lastGovernancePressure;
    uint256 public currentSigmaIPM;

    struct GlobalTelemetry {
        uint256 riskIndex;       // R(t) in WAD [0, 1e18]
        uint256 workloadDemand;  // W(t) in WAD [0, 1e18]
        uint256 faultRate;       // F(t) in WAD [0, 1e18]
        uint256 coordCost;       // C(t) in WAD [0, 1e18]
    }

    event EpochAdvanced(
        uint256 indexed newEpoch,
        address indexed coordinator,
        bytes32 stateRoot,
        uint256 governancePressure,
        GovernanceMode mode,
        uint256 sigmaIPM
    );
    event TelemetryIngested(
        uint256 indexed epoch,
        uint256 risk,
        uint256 workload,
        uint256 faults,
        uint256 deDeficit
    );
    event SuccessionAutomatonUpdated(address indexed newAutomaton);
    event CoordinatorTransferred(address indexed previousCoordinator, address indexed newCoordinator, bytes32 stateRoot);

    error UnauthorizedCoordinator(address caller);
    error UnauthorizedAutomaton(address caller);
    error ZeroAddressDetected();

    modifier onlyActiveCoordinator() {
        if (msg.sender != activeCoordinator) revert UnauthorizedCoordinator(msg.sender);
        _;
    }

    modifier onlySuccessionAutomaton() {
        if (msg.sender != successionAutomaton) revert UnauthorizedAutomaton(msg.sender);
        _;
    }

    constructor(address _entropyOracleAddress) {
        if (_entropyOracleAddress == address(0)) revert ZeroAddressDetected();
        entropyOracle = EntropyConstraint(_entropyOracleAddress);
        committeeManager = new DynamicCommittee(address(this));
        activeCoordinator = msg.sender;
        currentMode = GovernanceMode.Mode0_FlatDecentralization;
        currentEpoch = 1;
        epochStartTime = block.timestamp;
    }

    /**
     * @notice Registers the authorized SuccessionAutomaton contract (solves critical security flaw).
     */
    function setSuccessionAutomaton(address _automaton) external onlyActiveCoordinator {
        if (_automaton == address(0)) revert ZeroAddressDetected();
        successionAutomaton = _automaton;
        emit SuccessionAutomatonUpdated(_automaton);
    }

    /**
     * @notice Computes dynamic Governance Pressure G_p(t) using convex combination of positive stressors.
     * @dev G_p = w_r*R + w_w*W + w_f*F + w_c*C + w_d*(1 - DE)
     */
    function computeGovernancePressure(
        GlobalTelemetry calldata telemetry,
        uint256 currentDE
    ) public view returns (uint256 gPressure, uint256 deDeficit) {
        deDeficit = currentDE < WAD ? WAD - currentDE : 0;

        gPressure = (
            weightR * telemetry.riskIndex +
            weightW * telemetry.workloadDemand +
            weightF * telemetry.faultRate +
            weightC * telemetry.coordCost +
            weightD * deDeficit
        ) / WAD;

        if (gPressure > WAD) {
            gPressure = WAD;
        }
    }

    /**
     * @notice Updates the operational governance mode via dual-threshold hysteresis automaton (Equation 7).
     */
    function evaluateHysteresisMode(uint256 gPressure) public view returns (GovernanceMode newMode) {
        GovernanceMode prevMode = currentMode;

        if (gPressure < thetaLowDown || (prevMode == GovernanceMode.Mode0_FlatDecentralization && gPressure < thetaLowUp)) {
            newMode = GovernanceMode.Mode0_FlatDecentralization;
        } else if (gPressure >= thetaHighUp || (prevMode == GovernanceMode.Mode2_BoundedLeadership && gPressure >= thetaHighDown)) {
            newMode = GovernanceMode.Mode2_BoundedLeadership;
        } else {
            newMode = GovernanceMode.Mode1_AdaptiveCommittee;
        }
    }

    /**
     * @notice Ingests macroscopic telemetry, verifies constitutional bounds, updates G_p, and advances epoch.
     */
    function advanceGovernanceEpoch(
        bytes32 newStateRoot,
        GlobalTelemetry calldata telemetry,
        address[] calldata nodes,
        uint256[] calldata authorityWeights
    ) external onlyActiveCoordinator {
        // 1. Verify on-chain Constitutional Invariants (DE >= DE_min AND top-f sum <= rho_max)
        (bool valid, uint256 currentDE, , ) = entropyOracle.verifyConstitutionalInvariants(
            currentEpoch,
            authorityWeights,
            constitutionalDEMin,
            constitutionalRhoMax
        );
        require(valid, "State Error: Constitutional invariants violated");

        // 2. Closed-Loop Governance Pressure Evaluation
        (uint256 gPressure, uint256 deDeficit) = computeGovernancePressure(telemetry, currentDE);
        lastGovernancePressure = gPressure;

        // 3. Dual-Threshold Hysteresis Transition
        currentMode = evaluateHysteresisMode(gPressure);

        // 4. Compute Pheromone Attenuation Signal sigma_IPM (Equation 10)
        currentSigmaIPM = (sigma0 * gPressure) / WAD;

        // 5. Update Committee State & Authorities
        committeeManager.updateGovernancePressure(currentEpoch, gPressure);
        committeeManager.setAuthorities(nodes, authorityWeights);

        // 6. Advance Epoch
        currentEpoch++;
        currentStateRoot = newStateRoot;
        epochStartTime = block.timestamp;

        emit TelemetryIngested(currentEpoch, telemetry.riskIndex, telemetry.workloadDemand, telemetry.faultRate, deDeficit);
        emit EpochAdvanced(currentEpoch, activeCoordinator, newStateRoot, gPressure, currentMode, currentSigmaIPM);
    }

    /**
     * @notice Secure leadership handover executed exclusively by verified SuccessionAutomaton.
     */
    function applySuccession(
        address newCoordinator, 
        bytes32 verifiedStateRoot
    ) external onlySuccessionAutomaton {
        if (newCoordinator == address(0)) revert ZeroAddressDetected();
        address oldCoordinator = activeCoordinator;

        activeCoordinator = newCoordinator;
        currentStateRoot = verifiedStateRoot;
        epochStartTime = block.timestamp;

        emit CoordinatorTransferred(oldCoordinator, newCoordinator, verifiedStateRoot);
    }
}