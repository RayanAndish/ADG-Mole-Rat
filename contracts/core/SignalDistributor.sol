// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title SignalDistributor
 * @notice Manages biological signal distribution for the ADG framework:
 *         1. Global chemical suppression signal \sigma_{IPM}(t) (Equations 10 and 11).
 *         2. Targeted mechanical stimulus vector u_{stim,i}(t) (Equation 12).
 * @dev Replaces divergent low-degree Taylor series with precise fixed-point binary exponential approximation.
 */
contract SignalDistributor {
    uint256 public constant WAD = 1e18;

    address public immutable coordinator;

    // Constitutional Parametric Constants (Matching Table 6)
    uint256 public constant SIGMA_0 = 80e16;       // Max suppression intensity: 0.80 * 1e18
    uint256 public constant ETA_WAD = 3e18;        // Exponential pressure sensitivity: 3.0 * 1e18
    uint256 public constant BW_MIN = 20e16;        // Constitutional bandwidth floor: 0.20 * 1e18 (Equation 11)
    uint256 public constant Q_THRESH = 80e16;      // Reliability activation threshold: 0.80 * 1e18
    uint256 public constant DELTA_DECAY = 1e16;    // Pheromone natural dissipation rate per epoch

    struct SignalState {
        uint256 currentIPM;            // \sigma_{IPM} in WAD [0, SIGMA_0]
        uint256 lastBeaconEpoch;       // Epoch of last IPM emission
        uint256 globalAllowedBandwidth; // Throttled bandwidth scaling factor [BW_MIN, 1e18]
    }

    SignalState public globalSignalState;
    mapping(address => uint256) public nodeStimulus; // u_{stim,i} in WAD [0, 1e18]

    event IPMSignalUpdated(uint256 indexed epoch, uint256 rawIPM, uint256 allowedBandwidth);
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
            lastBeaconEpoch: 1,
            globalAllowedBandwidth: WAD
        });
    }

    /**
     * @notice Computes exp(-x) in WAD precision where x is in WAD.
     * @dev Uses exp(-x) = 2^(-x * log2(e)). log2(e) * 1e18 = 1.442695040888963407e18.
     */
    function expNegWad(uint256 x) public pure returns (uint256) {
        if (x == 0) return WAD;
        if (x >= 40e18) return 0; // exp(-40) underflows 18-decimal precision

        // x2 = x * log2(e) in WAD
        uint256 x2 = (x * 1442695040888963407) / WAD;
        uint256 intPart = x2 / WAD;
        uint256 fracPart = x2 % WAD;

        if (intPart >= 64) return 0;

        // Horner polynomial approximation for 2^(-f) where f in [0, 1)
        // 2^(-f) ≈ 1 - 0.693147*f + 0.240226*f^2 - 0.055504*f^3
        uint256 term1 = (693147180559945309 * fracPart) / WAD;
        uint256 frac2 = (fracPart * fracPart) / WAD;
        uint256 term2 = (240226506959100712 * frac2) / WAD;
        uint256 frac3 = (frac2 * fracPart) / WAD;
        uint256 term3 = (55504108664821579 * frac3) / WAD;

        uint256 fracRes = WAD - term1 + term2 - term3;
        return fracRes >> intPart;
    }

    /**
     * @notice Computes and broadcasts the global IPM attenuation signal (Equation 10).
     * @dev \sigma_{IPM}(t) = \sigma_0 * (1 - exp(-\eta * G_p(t)))
     *      BW_allowed = BW_min + (WAD - BW_min) * (1 - \sigma_{IPM})
     */
    function broadcastIPMSignal(
        uint256 epoch, 
        uint256 governancePressure
    ) external onlyCoordinator returns (uint256) {
        if (governancePressure > WAD) revert InvalidPressureValue(governancePressure);

        // x = \eta * G_p in WAD
        uint256 x = (ETA_WAD * governancePressure) / WAD;
        uint256 expNeg = expNegWad(x);
        uint256 oneMinusExp = expNeg < WAD ? WAD - expNeg : 0;

        // \sigma_{IPM} in WAD [0, SIGMA_0]
        uint256 sigmaIPM = (SIGMA_0 * oneMinusExp) / WAD;

        // Bounded Bandwidth Throttling (Equation 11 with constitutional floor BW_MIN)
        uint256 suppressionFactor = (sigmaIPM * WAD) / SIGMA_0; // normalized to [0, 1e18]
        uint256 dynamicRange = WAD - BW_MIN;
        uint256 allowedBW = BW_MIN + ((dynamicRange * (WAD - suppressionFactor)) / WAD);

        globalSignalState.currentIPM = sigmaIPM;
        globalSignalState.lastBeaconEpoch = epoch;
        globalSignalState.globalAllowedBandwidth = allowedBW;

        emit IPMSignalUpdated(epoch, sigmaIPM, allowedBW);
        return sigmaIPM;
    }

    /**
     * @notice Computes targeted stimulus u_{stim,i}(t) for idle workers (Equation 12).
     * @dev u_{stim,i} = ReLU((w_mean - w_i) / w_mean) * I(l_i <= l_med) * I(Q_i >= Q_thresh)
     */
    function computeAndDispatchStimulus(
        address node,
        uint256 nodeQueueLoad,
        uint256 avgColonyLoad,
        uint256 nodeLatency,
        uint256 medianLatency,
        uint256 nodeReliability
    ) public onlyCoordinator returns (uint256) {
        if (avgColonyLoad == 0) {
            nodeStimulus[node] = 0;
            return 0;
        }

        // Filtering conditions: latency <= median and reliability >= Q_THRESH
        if (nodeLatency <= medianLatency && nodeReliability >= Q_THRESH && nodeQueueLoad < avgColonyLoad) {
            uint256 loadDeficit = avgColonyLoad - nodeQueueLoad;
            uint256 stimulus = (loadDeficit * WAD) / avgColonyLoad;

            nodeStimulus[node] = stimulus;
            emit StimulusDispatched(node, stimulus, (stimulus * 15) / 10); // 1.5x queue priority boost
            return stimulus;
        } else {
            nodeStimulus[node] = 0;
            return 0;
        }
    }

    /**
     * @notice Batch stimulus dispatching across committee nodes to minimize transaction gas.
     */
    function batchDispatchStimulus(
        address[] calldata nodes,
        uint256[] calldata queueLoads,
        uint256 avgColonyLoad,
        uint256[] calldata latencies,
        uint256 medianLatency,
        uint256[] calldata reliabilities
    ) external onlyCoordinator returns (uint256[] memory stimuli) {
        uint256 n = nodes.length;
        require(n == queueLoads.length && n == latencies.length && n == reliabilities.length, "Length mismatch");
        stimuli = new uint256[](n);

        for (uint256 i = 0; i < n; i++) {
            stimuli[i] = computeAndDispatchStimulus(
                nodes[i],
                queueLoads[i],
                avgColonyLoad,
                latencies[i],
                medianLatency,
                reliabilities[i]
            );
        }
    }

    /**
     * @notice Returns effective allowed bandwidth accounting for time decay if beacons stall.
     */
    function getEffectiveBandwidth(uint256 currentEpoch) external view returns (uint256) {
        if (currentEpoch <= globalSignalState.lastBeaconEpoch) {
            return globalSignalState.globalAllowedBandwidth;
        }
        uint256 elapsedEpochs = currentEpoch - globalSignalState.lastBeaconEpoch;
        uint256 decay = elapsedEpochs * DELTA_DECAY;

        if (decay >= globalSignalState.currentIPM) {
            return WAD; // fully recovered to 100% bandwidth
        }
        uint256 decayingIPM = globalSignalState.currentIPM - decay;
        uint256 suppressionFactor = (decayingIPM * WAD) / SIGMA_0;
        uint256 dynamicRange = WAD - BW_MIN;
        return BW_MIN + ((dynamicRange * (WAD - suppressionFactor)) / WAD);
    }
}