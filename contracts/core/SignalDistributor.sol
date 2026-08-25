// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title SignalDistributor
 * @notice Manages biological signal distribution for the ADG framework:
 *         1. Global chemical suppression signal \sigma_{IPM}(t) (Khallaf et al., 2026; Faulkes, 2026).
 *         2. Targeted mechanical stimulus vector u_{stim,i}(t) (Reeve, 1992; Kutsukake et al., 2012).
 */
contract SignalDistributor {
    uint256 public constant WAD = 1e18;

    address public immutable coordinator;
    uint256 public constant SIGMA_0 = 80e16; // Max suppression intensity = 0.80 * 1e18
    uint256 public constant ETA = 3;         // Exponential gain factor
    uint256 public constant DELTA_DECAY = 1e16; // Half-life decay per unit time (0.01 * 1e18)

    struct SignalState {
        uint256 currentIPM;           // \sigma_{IPM} in WAD [0, 1e18]
        uint256 lastBeaconTimestamp;  // Timestamp of last IPM emission
        uint256 globalAllowedBandwidth; // Throttled bandwidth scaling factor [0, 1e18]
    }

    SignalState public globalSignalState;
    mapping(address => uint256) public nodeStimulus; // u_{stim,i} in WAD

    event IPMSignalUpdated(uint256 indexed epoch, uint256 rawIntensity, uint256 throttledBandwidth);
    event StimulusDispatched(address indexed node, uint256 stimulusIntensity, uint256 priorityBoost);

    error UnauthorizedCaller(address caller);
    error InvalidPressureValue(uint256 pressure);

    modifier onlyCoordinator() {
        if (msg.sender != coordinator) revert UnauthorizedCaller(msg.sender);
        _;
    }

    constructor(address _coordinator) {
        require(_coordinator != address(0), "Invalid coordinator");
        coordinator = _coordinator;
        globalSignalState = SignalState({
            currentIPM: 0,
            lastBeaconTimestamp: block.timestamp,
            globalAllowedBandwidth: WAD
        });
    }

    /**
     * @notice Computes and broadcasts the global IPM attenuation signal.
     * @dev \sigma_{IPM}(t) = \sigma_0 * (1 - exp(-\eta * G_p(t)))
     *      BW_allowed = BW_max * (1 - \sigma_{IPM}(t))
     * @param epoch Current consensus epoch.
     * @param governancePressure Real-time G_p(t) in WAD [0, 1e18].
     */
    function broadcastIPMSignal(uint256 epoch, uint256 governancePressure) external onlyCoordinator returns (uint256) {
        if (governancePressure > WAD) revert InvalidPressureValue(governancePressure);

        // Approximate 1 - exp(-\eta * G_p) via Taylor series expansion for EVM gas efficiency:
        // 1 - exp(-x) ≈ x - x^2/2 + x^3/6
        uint256 x = (ETA * governancePressure); // in WAD
        uint256 expTerm;
        if (x >= 4 * WAD) {
            expTerm = 0; // exp(-4) ≈ 0.018 -> saturated suppression
        } else {
            uint256 x2 = (x * x) / WAD;
            uint256 x3 = (x2 * x) / WAD;
            uint256 series = x - (x2 / 2) + (x3 / 6);
            expTerm = series > WAD ? WAD : series;
        }

        uint256 sigmaIPM = (SIGMA_0 * expTerm) / WAD;
        uint256 allowedBW = WAD - sigmaIPM;

        globalSignalState.currentIPM = sigmaIPM;
        globalSignalState.lastBeaconTimestamp = block.timestamp;
        globalSignalState.globalAllowedBandwidth = allowedBW;

        emit IPMSignalUpdated(epoch, sigmaIPM, allowedBW);
        return sigmaIPM;
    }

    /**
     * @notice Computes targeted stimulus u_{stim,i}(t) for idle workers.
     * @dev u_{stim,i}(t) = ReLU((w_mean - w_i) / w_mean) * I(l_i <= l_median) * I(Q_i >= Q_thresh)
     * @param node Target validator address.
     * @param nodeQueueLoad Instantaneous queue load w_i in WAD.
     * @param avgColonyLoad Mean colony workload demand w_mean in WAD.
     * @param nodeLatency Relative latency l_i in WAD.
     * @param medianLatency Median peer latency l_median in WAD.
     * @param nodeReliability Historical uptime Q_i in WAD.
     */
    function computeAndDispatchStimulus(
        address node,
        uint256 nodeQueueLoad,
        uint256 avgColonyLoad,
        uint256 nodeLatency,
        uint256 medianLatency,
        uint256 nodeReliability
    ) external onlyCoordinator returns (uint256) {
        if (avgColonyLoad == 0) {
            nodeStimulus[node] = 0;
            return 0;
        }

        // Filtering conditions: latency <= median and reliability >= 80%
        if (nodeLatency <= medianLatency && nodeReliability >= 80e16 && nodeQueueLoad < avgColonyLoad) {
            uint256 loadDeficit = avgColonyLoad - nodeQueueLoad;
            uint256 stimulus = (loadDeficit * WAD) / avgColonyLoad;
            
            nodeStimulus[node] = stimulus;
            emit StimulusDispatched(node, stimulus, (stimulus * 2)); // Priority boost
            return stimulus;
        } else {
            nodeStimulus[node] = 0;
            return 0;
        }
    }

    function getEffectiveBandwidth() external view returns (uint256) {
        // Apply time-dependent natural decay if beacons stall
        uint256 elapsed = block.timestamp - globalSignalState.lastBeaconTimestamp;
        uint256 decay = elapsed * DELTA_DECAY;
        if (decay >= globalSignalState.currentIPM) {
            return WAD;
        }
        return WAD - (globalSignalState.currentIPM - decay);
    }
}