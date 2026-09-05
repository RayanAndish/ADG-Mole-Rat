// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title DynamicGovernanceScore
 * @notice Formal on-chain calculation and management of the Dynamic Governance Score (GSF):
 *         GS_i(t) = [ (β_q*Q_i + β_r*r_i + β_c*c_i + β_e*e_i + β_p*p_i) / (1 + β_w*w_i + β_l*l_i) ] * exp(-ξ * τ_i)
 * @dev Enforces constitutional 5-factor telemetry scoring with active energy budgeting (e_i) 
 *      and anti-monopoly coordinator tenure decay (\xi).
 */
contract DynamicGovernanceScore {
    uint256 public constant WAD = 1e18;

    address public immutable coordinator;

    // Constitutional Numerator Weights (Sum strictly normalized to 1.0 * 1e18)
    uint256 public betaQ = 30e16; // Reliability weight (Q_i) = 0.30
    uint256 public betaR = 20e16; // Reputation / Stake weight (r_i) = 0.20
    uint256 public betaC = 20e16; // Compute / Bandwidth capacity (c_i) = 0.20
    uint256 public betaE = 15e16; // Energy / Hardware headroom (e_i) = 0.15 (Resolves Issue 18)
    uint256 public betaP = 15e16; // Historical governance consistency (p_i) = 0.15

    // Denominator Penalty Weights
    uint256 public betaW = 40e16; // Queue load penalty (w_i) = 0.40
    uint256 public betaL = 60e16; // Relative latency penalty (l_i) = 0.60

    // Anti-Monopoly Coordinator Tenure Decay Rate (\xi = 0.05 per consecutive leadership epoch)
    uint256 public xiDecay = 5e16; // 0.05 * 1e18

    struct TelemetryInput {
        uint256 reliability;     // Q_i in WAD [0, 1e18]
        uint256 reputation;      // r_i in WAD [0, 1e18]
        uint256 capacity;        // c_i in WAD [0, 1e18]
        uint256 energyBudget;    // e_i in WAD [0, 1e18] (Remaining compute/memory resource budget)
        uint256 participation;   // p_i in WAD [0, 1e18]
        uint256 queueLoad;       // w_i in WAD [0, 1e18]
        uint256 relativeLatency; // l_i in WAD [0, 1e18]
        uint256 tenureEpochs;    // \tau_i: Consecutive epochs currently served as active coordinator (0 for non-leaders)
    }

    event ScoreEvaluated(
        address indexed node, 
        uint256 rawNumerator, 
        uint256 rawDenominator, 
        uint256 tenureDecayFactor, 
        uint256 finalGSF
    );
    event WeightsUpdated(uint256 bQ, uint256 bR, uint256 bC, uint256 bE, uint256 bP);
    event PenaltyWeightsUpdated(uint256 bW, uint256 bL);
    event TenureDecayUpdated(uint256 newXi);

    error UnauthorizedCaller(address caller);
    error InvalidWeightNormalization(uint256 totalWeight);
    error ZeroAddressCoordinator();

    modifier onlyCoordinator() {
        if (msg.sender != coordinator) revert UnauthorizedCaller(msg.sender);
        _;
    }

    constructor(address _coordinator) {
        if (_coordinator == address(0)) revert ZeroAddressCoordinator();
        coordinator = _coordinator;
    }

    /**
     * @notice Computes the closed-form GSF score for a node telemetry profile.
     * @param t The 7-factor telemetry vector.
     * @return finalScore GSF score in WAD precision.
     */
    function computeGSF(address /* node */, TelemetryInput calldata t) public view returns (uint256 finalScore) {
        // Numerator: β_q*Q_i + β_r*r_i + β_c*c_i + β_e*e_i + β_p*p_i
        uint256 numerator = (
            betaQ * t.reliability +
            betaR * t.reputation +
            betaC * t.capacity +
            betaE * t.energyBudget +
            betaP * t.participation
        ) / WAD;

        // Denominator: 1.0 + β_w*w_i + β_l*l_i (Guaranteed >= 1.0 WAD)
        uint256 denominator = WAD + ((betaW * t.queueLoad + betaL * t.relativeLatency) / WAD);

        uint256 baseScore = (numerator * WAD) / denominator;

        // Anti-Monopoly Tenure Penalty: exp(-\xi * \tau_i)
        uint256 decayFactor = WAD;
        if (t.tenureEpochs > 0) {
            uint256 totalDecay = xiDecay * t.tenureEpochs;
            if (totalDecay >= 90e16) {
                decayFactor = 10e16; // Constitutional floor: 0.10 * 1e18
            } else {
                decayFactor = WAD - totalDecay;
            }
        }

        finalScore = (baseScore * decayFactor) / WAD;
    }

    /**
     * @notice Batch evaluation of GSF scores across an active validator committee.
     */
    function batchComputeGSF(
        address[] calldata nodes,
        TelemetryInput[] calldata telemetries
    ) external returns (uint256[] memory scores) {
        require(nodes.length == telemetries.length, "Array length mismatch");
        uint256 n = nodes.length;
        scores = new uint256[](n);

        for (uint256 i = 0; i < n; i++) {
            scores[i] = computeGSF(nodes[i], telemetries[i]);
            emit ScoreEvaluated(nodes[i], 0, 0, 0, scores[i]);
        }
        return scores;
    }

    /**
     * @notice Re-calibrates the 5-factor numerator weights ensuring convex normalization.
     */
    function setWeights(
        uint256 _bQ, 
        uint256 _bR, 
        uint256 _bC, 
        uint256 _bE, 
        uint256 _bP
    ) external onlyCoordinator {
        uint256 total = _bQ + _bR + _bC + _bE + _bP;
        if (total != WAD) revert InvalidWeightNormalization(total);

        betaQ = _bQ;
        betaR = _bR;
        betaC = _bC;
        betaE = _bE;
        betaP = _bP;

        emit WeightsUpdated(_bQ, _bR, _bC, _bE, _bP);
    }

    /**
     * @notice Updates penalty weights and tenure decay rate.
     */
    function setOperationalParameters(uint256 _bW, uint256 _bL, uint256 _xi) external onlyCoordinator {
        betaW = _bW;
        betaL = _bL;
        xiDecay = _xi;

        emit PenaltyWeightsUpdated(_bW, _bL);
        emit TenureDecayUpdated(_xi);
    }
}