// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title DynamicCommittee
 * @notice Manages validator registry, dynamic governance regimes (Mode 0, 1, 2), and biological actuation signals.
 * @dev Implements non-chattering 4-threshold hysteresis (Equation 7), volatile IPM suppression (Equation 10),
 *      and targeted physical shoving stimulus (Equation 12).
 */
contract DynamicCommittee {
    enum GovernanceMode { 
        Mode0_Flat, 
        Mode1_AdaptiveCommittee, 
        Mode2_BoundedLead 
    }

    struct NodeTelemetry {
        uint256 reliability;     // Q_i in WAD [0, 1e18]
        uint256 reputation;      // r_i in WAD [0, 1e18]
        uint256 computeCapacity; // c_i in WAD [0, 1e18]
        uint256 energyBudget;    // e_i in WAD [0, 1e18] (Resolves Issue 18)
        uint256 participation;   // p_i in WAD [0, 1e18]
        uint256 queueLoad;       // w_i in WAD [0, 1e18]
        uint256 latencyRel;      // l_i in WAD [0, 1e18]
        uint256 lastActiveLead;  // Epoch or timestamp when node was last leader
        bool isRegistered;
        bool isSlashed;
    }

    address public immutable coordinatorContract;
    uint256 public constant WAD = 1e18;

    // Constitutional Four-Threshold Hysteresis Boundaries (Equation 7)
    uint256 public thetaLowDown = 30e16;  // 0.30 * 1e18
    uint256 public thetaLowUp = 35e16;    // 0.35 * 1e18
    uint256 public thetaHighDown = 65e16; // 0.65 * 1e18
    uint256 public thetaHighUp = 70e16;   // 0.70 * 1e18

    // Active Governance State
    GovernanceMode public currentMode;
    uint256 public currentGovernancePressure; // G_p in WAD
    uint256 public ipmSuppressionSignal;      // \sigma_{IPM} in WAD [0, 1e18]

    address[] public validatorAddresses;
    mapping(address => NodeTelemetry) public nodeRegistry;
    mapping(address => uint256) public dynamicAuthority; // a_i in WAD

    event ModeTransition(GovernanceMode indexed previousMode, GovernanceMode indexed newMode, uint256 governancePressure);
    event IPMSignalBroadcasted(uint256 indexed epoch, uint256 signalIntensity);
    event ShovingStimulusInjected(address indexed targetNode, uint256 stimulusIntensity);
    event NodeRegistered(address indexed node, uint256 capacity, uint256 initialReputation);
    event NodeSlashed(address indexed node);

    modifier onlyCoordinator() {
        require(msg.sender == coordinatorContract, "Auth: Caller is not ADG Coordinator");
        _;
    }

    constructor(address _coordinator) {
        require(_coordinator != address(0), "Invalid coordinator address");
        coordinatorContract = _coordinator;
        currentMode = GovernanceMode.Mode0_Flat;
    }

    /**
     * @notice Registers a new validator node with 7-factor initial state telemetry.
     */
    function registerValidator(
        address node, 
        uint256 capacity, 
        uint256 initialReputation
    ) external {
        require(!nodeRegistry[node].isRegistered, "Node already registered");
        require(node != address(0), "Invalid address");

        nodeRegistry[node] = NodeTelemetry({
            reliability: 1e18,     // Initial 100% reliability (Q_i)
            reputation: initialReputation, // r_i
            computeCapacity: capacity,     // c_i
            energyBudget: 1e18,    // 100% available headroom (e_i)
            participation: 1e18,   // 100% baseline participation (p_i)
            queueLoad: 0,          // w_i
            latencyRel: 1e18,      // l_i = median
            lastActiveLead: 0,
            isRegistered: true,
            isSlashed: false
        });

        validatorAddresses.push(node);
        emit NodeRegistered(node, capacity, initialReputation);
    }

    /**
     * @notice Updates network operational mode via dual-threshold hysteresis automaton (Equation 7).
     */
    function updateGovernancePressure(uint256 epoch, uint256 gPressure) external onlyCoordinator {
        require(gPressure <= WAD, "G_p out of bounds");
        currentGovernancePressure = gPressure;
        GovernanceMode previousMode = currentMode;

        // True Hysteresis State Transition Logic (Prevents Mode Chattering)
        if (gPressure < thetaLowDown || (previousMode == GovernanceMode.Mode0_Flat && gPressure < thetaLowUp)) {
            currentMode = GovernanceMode.Mode0_Flat;
        } else if (gPressure >= thetaHighUp || (previousMode == GovernanceMode.Mode2_BoundedLead && gPressure >= thetaHighDown)) {
            currentMode = GovernanceMode.Mode2_BoundedLead;
        } else {
            currentMode = GovernanceMode.Mode1_AdaptiveCommittee;
        }

        // Biological Actuation 1: Calculate IPM Chemical Suppression Signal (Equation 10)
        // \sigma_{IPM} = \sigma_0 * (1 - exp(-\eta * G_p))
        if (currentMode == GovernanceMode.Mode2_BoundedLead) {
            ipmSuppressionSignal = (80e16 * gPressure) / WAD; // Proportional scaling
        } else {
            ipmSuppressionSignal = 0;
        }

        emit ModeTransition(previousMode, currentMode, gPressure);
        emit IPMSignalBroadcasted(epoch, ipmSuppressionSignal);
    }

    /**
     * @notice Actuation 2: Shoving Stimulus Injection for idle nodes (Equation 12).
     */
    function injectShovingStimulus(address targetNode, uint256 avgColonyLoad) external onlyCoordinator {
        NodeTelemetry storage node = nodeRegistry[targetNode];
        require(node.isRegistered && !node.isSlashed, "Target ineligible");

        if (node.queueLoad < avgColonyLoad && node.reliability >= 80e16) {
            uint256 stimulus = ((avgColonyLoad - node.queueLoad) * WAD) / (avgColonyLoad + 1);
            emit ShovingStimulusInjected(targetNode, stimulus);
        }
    }

    function setAuthorities(address[] calldata nodes, uint256[] calldata authorities) external onlyCoordinator {
        require(nodes.length == authorities.length, "Mismatched lengths");
        for (uint256 i = 0; i < nodes.length; i++) {
            dynamicAuthority[nodes[i]] = authorities[i];
        }
    }

    /**
     * @notice Marks a malicious validator as slashed.
     */
    function slashValidator(address node) external onlyCoordinator {
        require(nodeRegistry[node].isRegistered, "Not registered");
        nodeRegistry[node].isSlashed = true;
        emit NodeSlashed(node);
    }

    // =========================================================================
    //  QUORUM & COMMITTEE INTERFACE FUNCTIONS (Resolves Compiler Error)
    // =========================================================================

    /**
     * @notice Returns the number of active, non-slashed validators in the committee.
     * @dev Resolves member lookup error in SuccessionAutomaton.
     */
    function getCommitteeSize() public view returns (uint256) {
        uint256 activeCount = 0;
        uint256 total = validatorAddresses.length;
        for (uint256 i = 0; i < total; i++) {
            address val = validatorAddresses[i];
            if (nodeRegistry[val].isRegistered && !nodeRegistry[val].isSlashed) {
                activeCount++;
            }
        }
        return activeCount;
    }

    /**
     * @notice Checks if an address is an active, non-slashed validator.
     * @dev Resolves member lookup error in SuccessionAutomaton.
     */
    function isCommitteeMember(address node) external view returns (bool) {
        return nodeRegistry[node].isRegistered && !nodeRegistry[node].isSlashed;
    }

    /**
     * @notice Backwards-compatible total registered validator count.
     */
    function getValidatorCount() external view returns (uint256) {
        return validatorAddresses.length;
    }
}