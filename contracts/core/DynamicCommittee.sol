// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title DynamicCommittee
 * @notice Manages validator states, dynamic governance regimes (Mode 0, 1, 2), and biological actuation signals.
 * @dev Implements volatile IPM suppression broadcast and targeted physical shoving stimulus.
 */
contract DynamicCommittee {
    enum GovernanceMode { Mode0_Flat, Mode1_AdaptiveCommittee, Mode2_BoundedLead }

    struct NodeTelemetry {
        uint256 reliability;     // Q_i in WAD [0, 1e18]
        uint256 reputation;      // r_i in WAD [0, 1e18]
        uint256 computeCapacity; // c_i in WAD [0, 1e18]
        uint256 queueLoad;       // w_i in WAD [0, 1e18]
        uint256 latencyRel;      // l_i in WAD [0, 1e18]
        uint256 lastActiveLead;  // Timestamp of last leadership tenure
        bool isRegistered;
        bool isSlashed;
    }

    address public immutable coordinatorContract;
    uint256 public constant WAD = 1e18;

    // Constitutional Mode Thresholds (WAD)
    uint256 public thetaLow = 35e16;  // 0.35 * 1e18
    uint256 public thetaHigh = 70e16; // 0.70 * 1e18

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
    event NodeRegistered(address indexed node, uint256 capacity);

    modifier onlyCoordinator() {
        require(msg.sender == coordinatorContract, "Auth: Caller is not ADG Coordinator");
        _;
    }

    constructor(address _coordinator) {
        require(_coordinator != address(0), "Invalid coordinator address");
        coordinatorContract = _coordinator;
        currentMode = GovernanceMode.Mode0_Flat;
    }

    function registerValidator(address node, uint256 capacity, uint256 initialReputation) external {
        require(!nodeRegistry[node].isRegistered, "Node already registered");
        require(node != address(0), "Invalid address");

        nodeRegistry[node] = NodeTelemetry({
            reliability: 1e18, // Initial 100% reliability
            reputation: initialReputation,
            computeCapacity: capacity,
            queueLoad: 0,
            latencyRel: 1e18, // Median latency
            lastActiveLead: 0,
            isRegistered: true,
            isSlashed: false
        });

        validatorAddresses.push(node);
        emit NodeRegistered(node, capacity);
    }

    /**
     * @notice Updates network operational mode based on real-time Governance Pressure G_p.
     */
    function updateGovernancePressure(uint256 epoch, uint256 gPressure) external onlyCoordinator {
        require(gPressure <= WAD, "G_p out of bounds");
        currentGovernancePressure = gPressure;
        GovernanceMode previousMode = currentMode;

        if (gPressure < thetaLow) {
            currentMode = GovernanceMode.Mode0_Flat;
        } else if (gPressure < thetaHigh) {
            currentMode = GovernanceMode.Mode1_AdaptiveCommittee;
        } else {
            currentMode = GovernanceMode.Mode2_BoundedLead;
        }

        // Biological Actuation 1: Calculate IPM Chemical Suppression Signal
        // \sigma_{IPM} = \sigma_0 * (1 - exp(-\eta * G_p))
        if (currentMode == GovernanceMode.Mode2_BoundedLead) {
            ipmSuppressionSignal = (80e16 * gPressure) / WAD; // Linearized scaling for gas efficiency
        } else {
            ipmSuppressionSignal = 0;
        }

        emit ModeTransition(previousMode, currentMode, gPressure);
        emit IPMSignalBroadcasted(epoch, ipmSuppressionSignal);
    }

    /**
     * @notice Actuation 2: Shoving Stimulus Injection for idle nodes (Reeve 1992).
     */
    function injectShovingStimulus(address targetNode, uint256 avgColonyLoad) external onlyCoordinator {
        NodeTelemetry storage node = nodeRegistry[targetNode];
        require(node.isRegistered && !node.isSlashed, "Target ineligible");

        if (node.queueLoad < avgColonyLoad && node.reliability >= 80e16) {
            uint256 stimulus = ((avgColonyLoad - node.queueLoad) * WAD) / avgColonyLoad;
            emit ShovingStimulusInjected(targetNode, stimulus);
        }
    }

    function setAuthorities(address[] calldata nodes, uint256[] calldata authorities) external onlyCoordinator {
        require(nodes.length == authorities.length, "Mismatched lengths");
        for (uint256 i = 0; i < nodes.length; i++) {
            dynamicAuthority[nodes[i]] = authorities[i];
        }
    }

    function getValidatorCount() external view returns (uint256) {
        return validatorAddresses.length;
    }
}