// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title DynamicGovernanceScore
 * @notice Formal on-chain calculation and management of the Dynamic Governance Score (GSF):
 *         GS_i(t) = [ (β_q*Q_i + β_r*r_i + β_c*c_i + β_p*p_i) / (1 + β_w*w_i + β_l*l_i) ] * exp(-ξ * τ_i)
 */
contract DynamicGovernanceScore {
    uint256 public constant WAD = 1e18;

    address public immutable coordinator;

    // Weights: Numerator (sum = 1.0)
    uint256 public betaQ = 35e16; // Reliability weight = 0.35
    uint256 public betaR = 25e16; // Reputation weight = 0.25
    uint256 public betaC = 20e16; // Capacity weight = 0.20
    uint256 public betaP = 20e16; // Participation weight = 0.20

    // Weights: Denominator penalties
    uint256 public betaW = 40e16; // Load penalty = 0.40
    uint256 public betaL = 60e16; // Latency penalty = 0.60

    // Anti-Monopoly Tenure Decay Rate (\xi = 0.05 per epoch)
    uint256 public xiDecay = 5e16;

    struct TelemetryInput {
        uint256 reliability;     // Q_i [0, 1e18]
        uint256 reputation;      // r_i [0, 1e18]
        uint256 capacity;        // c_i [0, 1e18]
        uint256 participation;   // p_i [0, 1e18]
        uint256 queueLoad;       // w_i [0, 1e18]
        uint256 relativeLatency; // l_i [0, 1e18]
        uint256 tenureEpochs;    // \tau_i = elapsed epochs since last lead
    }

    event ScoreEvaluated(address indexed node, uint256 rawNumerator, uint256 rawDenominator, uint256 finalGSF);
    event WeightsUpdated(uint256 bQ, uint256 bR, uint256 bC, uint256 bP);

    error UnauthorizedCaller(address caller);

    modifier onlyCoordinator() {
        if (msg.sender != coordinator) revert UnauthorizedCaller(msg.sender);
        _;
    }

    constructor(address _coordinator) {
        require(_coordinator != address(0), "Invalid coordinator");
        coordinator = _coordinator;
    }

    /**
     * @notice Computes the closed-form GSF for a given node telemetry input.
     */
    function computeGSF(address node, TelemetryInput calldata t) public view returns (uint256) {
        // Numerator: β_q*Q_i + β_r*r_i + β_c*c_i + β_p*p_i
        uint256 numerator = (betaQ * t.reliability +
                             betaR * t.reputation +
                             betaC * t.capacity +
                             betaP * t.participation) / WAD;

        // Denominator: 1.0 + β_w*w_i + β_l*l_i
        uint256 denominator = WAD + ((betaW * t.queueLoad + betaL * t.relativeLatency) / WAD);

        uint256 baseScore = (numerator * WAD) / denominator;

        // Anti-monopoly decay factor: exp(-\xi * \tau_i)
        // Linearized approximation for EVM: max(0.1, 1.0 - \xi * \tau_i)
        uint256 decayFactor = WAD;
        uint256 totalDecay = (xiDecay * t.tenureEpochs);
        if (totalDecay >= 90e16) {
            decayFactor = 10e16; // Minimum floor = 0.10 * 1e18
        } else {
            decayFactor = WAD - totalDecay;
        }

        uint256 finalScore = (baseScore * decayFactor) / WAD;
        return finalScore;
    }

    /**
     * @notice Batch evaluation of GSF scores across an array of validator nodes.
     */
    function batchComputeGSF(
        address[] calldata nodes,
        TelemetryInput[] calldata telemetries
    ) external returns (uint256[] memory scores) {
        require(nodes.length == telemetries.length, "Array length mismatch");
        scores = new uint256[](nodes.length);

        for (uint256 i = 0; i < nodes.length; i++) {
            scores[i] = computeGSF(nodes[i], telemetries[i]);
            emit ScoreEvaluated(nodes[i], 0, 0, scores[i]);
        }
        return scores;
    }
}