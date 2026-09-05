// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title EntropyConstraint
 * @notice Formal on-chain verification of Constitutional Governance Invariants:
 *         1. Decentralization Entropy: DE(a) >= DE_min
 *         2. Top-f Byzantine Coalition Authority Bound: sum_{j=1}^f a_(j) <= rho_max < 1/3
 *         3. Single-Node Monopoly Barrier: a_(1) <= 1 - ((N - 1) / N) * DE_min
 *         4. Herfindahl-Hirschman Concentration Index (AC)
 * @dev Replaces heuristic entropy-only validation with deterministic order-statistics coalition safety.
 */
contract EntropyConstraint {
    uint256 public constant WAD = 1e18; // 18-decimal fixed-point base
    uint256 public constant LN2_WAD = 693147180559945309; // ln(2) * 1e18
    uint256 public constant MIN_AUTHORITY_THRESHOLD = 1e12; // Epsilon threshold to prevent ln(0)

    // Constitutional Default Thresholds
    uint256 public constant DEFAULT_DE_MIN = 600000000000000000;   // DE_min = 0.60 * 1e18
    uint256 public constant DEFAULT_RHO_MAX = 320000000000000000;  // rho_max = 0.32 * 1e18 (< 1/3)
    uint256 public constant SIMPLEX_TOLERANCE = 1e14;              // 0.01% numerical rounding tolerance

    // Custom Error Definitions
    error EntropyBelowConstitutionalBound(uint256 currentDE, uint256 minimumDE);
    error CoalitionAuthorityExceedsBound(uint256 currentCoalitionShare, uint256 maximumAllowedShare);
    error SingleNodeMonopolyExceeded(uint256 currentMaxShare, uint256 maximumAllowedShare);
    error InvalidSimplexNormalization(uint256 totalWeight);
    error InvalidPopulationSize(uint256 nodeCount);
    error InvalidConstitutionalBounds(uint256 deMin, uint256 rhoMax);

    // Constitutional Verification Event
    event ConstitutionalInvariantsVerified(
        uint256 indexed epoch,
        uint256 decentralizationEntropy,
        uint256 concentrationIndex,
        uint256 topFCoalitionShare,
        uint256 maxSingleAuthorityShare
    );

    /**
     * @notice Computes natural logarithm ln(x) for x in WAD precision using bitwise binary decomposition.
     * @param x Fixed-point value in WAD precision (1e18 = 1.0).
     * @return result ln(x) in WAD precision (signed representation as int256).
     */
    function lnWad(uint256 x) public pure returns (int256 result) {
        require(x > 0, "Math: ln(0) undefined");
        if (x == WAD) return 0;

        int256 sign = 1;
        uint256 val = x;
        if (x < WAD) {
            sign = -1;
            val = (WAD * WAD) / x;
        }

        uint256 integerLog2 = 0;
        while (val >= 2 * WAD) {
            val /= 2;
            integerLog2++;
        }

        uint256 fracLog2 = 0;
        uint256 y = val;
        for (uint256 i = 0; i < 60; i++) {
            y = (y * y) / WAD;
            if (y >= 2 * WAD) {
                fracLog2 += (1e18 >> (i + 1));
                y /= 2;
            }
        }

        int256 log2Wad = int256((integerLog2 * WAD) + fracLog2);
        result = sign * (log2Wad * int256(LN2_WAD)) / int256(WAD);
    }

    /**
     * @notice Computes the aggregate authority share of the top-f highest-weighted nodes.
     * @dev Uses an insertion-tracked bounded buffer to extract the sum of the f largest elements in O(N * f).
     * @param weights Normalized authority distribution array.
     * @param f Number of adversarial nodes to aggregate (f = floor((N - 1) / 3)).
     * @return topFSum Sum of the f largest weights in WAD.
     * @return maxWeight Value of the single largest weight a_(1) in WAD.
     */
    function computeTopFMetrics(
        uint256[] calldata weights,
        uint256 f
    ) public pure returns (uint256 topFSum, uint256 maxWeight) {
        uint256 n = weights.length;
        if (f == 0) return (0, 0);
        if (f >= n) f = n;

        // Bounded tracking buffer for the top-f elements
        uint256[] memory topList = new uint256[](f);

        for (uint256 i = 0; i < n; i++) {
            uint256 val = weights[i];
            if (val > maxWeight) {
                maxWeight = val;
            }

            // Insert val into topList if it is larger than the current minimum in topList
            if (val > topList[f - 1]) {
                topList[f - 1] = val;
                // Bubble up to maintain sorted order in topList (descending)
                for (uint256 j = f - 1; j > 0; j--) {
                    if (topList[j] > topList[j - 1]) {
                        uint256 temp = topList[j - 1];
                        topList[j - 1] = topList[j];
                        topList[j] = temp;
                    } else {
                        break;
                    }
                }
            }
        }

        uint256 sum = 0;
        for (uint256 j = 0; j < f; j++) {
            sum += topList[j];
        }
        return (sum, maxWeight);
    }

    /**
     * @notice Evaluates Normalized Shannon Decentralization Entropy DE(a) and Concentration Index (AC).
     * @param weights Normalized authority distribution array in WAD.
     * @return de Normalized Shannon entropy in WAD [0, 1e18].
     * @return ac Herfindahl-Hirschman Index in WAD [1/N, 1e18].
     * @return totalWeight Sum of all elements (for simplex validation).
     */
    function calculateEntropyAndConcentration(
        uint256[] calldata weights
    ) public pure returns (uint256 de, uint256 ac, uint256 totalWeight) {
        uint256 n = weights.length;
        if (n <= 1) revert InvalidPopulationSize(n);

        uint256 rawEntropySum = 0;
        uint256 concentrationSum = 0;

        for (uint256 i = 0; i < n; i++) {
            uint256 a_i = weights[i];
            totalWeight += a_i;
            concentrationSum += (a_i * a_i) / WAD;

            if (a_i > MIN_AUTHORITY_THRESHOLD) {
                int256 ln_ai = lnWad(a_i);
                int256 p_ln_p = (int256(a_i) * ln_ai) / int256(WAD);
                rawEntropySum += uint256(-p_ln_p);
            }
        }

        int256 lnN = lnWad(n * WAD);
        de = (rawEntropySum * WAD) / uint256(lnN);
        ac = concentrationSum;
    }

    /**
     * @notice Formally verifies all constitutional safety invariants in Theorem 3 and Equation (14).
     * @param epoch Consensus epoch identifier.
     * @param weights Authority vector proposed by off-chain engine.
     * @param deMin Minimum constitutional entropy bound in WAD.
     * @param rhoMax Maximum allowed aggregate authority for top-f coalition in WAD (< 1/3 WAD).
     */
    function verifyConstitutionalInvariants(
        uint256 epoch,
        uint256[] calldata weights,
        uint256 deMin,
        uint256 rhoMax
    ) public returns (bool valid, uint256 de, uint256 ac, uint256 topFShare) {
        uint256 n = weights.length;
        if (n <= 1) revert InvalidPopulationSize(n);
        if (rhoMax >= (WAD / 3)) revert InvalidConstitutionalBounds(deMin, rhoMax);

        // 1. Simplex Normalization Check
        (uint256 calculatedDE, uint256 calculatedAC, uint256 totalWeight) = calculateEntropyAndConcentration(weights);
        if (totalWeight < WAD - SIMPLEX_TOLERANCE || totalWeight > WAD + SIMPLEX_TOLERANCE) {
            revert InvalidSimplexNormalization(totalWeight);
        }

        // 2. Constitutional Entropy Lower Bound Check
        if (calculatedDE < deMin) {
            revert EntropyBelowConstitutionalBound(calculatedDE, deMin);
        }

        // 3. Byzantine Coalition Bound Check (Top-f share <= rho_max < 1/3)
        uint256 f = (n - 1) / 3;
        (uint256 topFSum, uint256 maxSingleShare) = computeTopFMetrics(weights, f);

        if (topFSum > rhoMax) {
            revert CoalitionAuthorityExceedsBound(topFSum, rhoMax);
        }

        // 4. Single-Node Monopoly Barrier Check: a_(1) <= 1 - ((N - 1) / N) * deMin
        uint256 maxAllowedSingleShare = WAD - (((n - 1) * deMin) / n);
        if (maxSingleShare > maxAllowedSingleShare) {
            revert SingleNodeMonopolyExceeded(maxSingleShare, maxAllowedSingleShare);
        }

        emit ConstitutionalInvariantsVerified(epoch, calculatedDE, calculatedAC, topFSum, maxSingleShare);
        return (true, calculatedDE, calculatedAC, topFSum);
    }

    /**
     * @notice Backwards-compatible interface verifying entropy and applying default coalition bound.
     * @param epoch Consensus epoch identifier.
     * @param weights Normalized authority vector.
     * @param deMin Minimum constitutional entropy bound.
     */
    function verifyEntropyInvariant(
        uint256 epoch,
        uint256[] calldata weights,
        uint256 deMin
    ) external returns (bool valid, uint256 de, uint256 ac) {
        (valid, de, ac, ) = verifyConstitutionalInvariants(epoch, weights, deMin, DEFAULT_RHO_MAX);
    }
}