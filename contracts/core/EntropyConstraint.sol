// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title EntropyConstraint
 * @notice Formal on-chain verification of Decentralization Entropy (DE) and Herfindahl-Hirschman Index (AC).
 * @dev Implements fixed-point natural logarithm and Shannon entropy lower bound enforcement: DE(a) >= DE_min.
 */
contract EntropyConstraint {
    uint256 public constant WAD = 1e18; // 18 decimal fixed-point base
    uint256 public constant LN2_WAD = 693147180559945309; // ln(2) * 1e18
    uint256 public constant MIN_AUTHORITY_THRESHOLD = 1e12; // Epsilon threshold to prevent ln(0)

    error EntropyBelowConstitutionalBound(uint256 currentDE, uint256 minimumDE);
    error InvalidSimplexNormalization(uint256 totalWeight);
    error InvalidPopulationSize(uint256 nodeCount);

    event EntropyVerified(uint256 indexed epoch, uint256 decentralizationEntropy, uint256 concentrationIndex);

    /**
     * @notice Computes natural logarithm ln(x) for x in WAD precision using 64.64 bitwise binary logarithm.
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

        // Compute integer log2
        uint256 integerLog2 = 0;
        while (val >= 2 * WAD) {
            val /= 2;
            integerLog2++;
        }

        // Fractional part via binary approximation
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
     * @notice Evaluates Normalized Shannon Decentralization Entropy DE(a) = - (1 / ln N) * sum(a_i * ln(a_i)).
     * @param weights Normalized authority distribution array (in WAD, sum must equal 1e18).
     * @return de Normalized entropy in WAD [0, 1e18].
     * @return ac Herfindahl-Hirschman Concentration Index in WAD [1/N, 1e18].
     */
    function calculateEntropy(uint256[] calldata weights) public pure returns (uint256 de, uint256 ac) {
        uint256 n = weights.length;
        if (n <= 1) revert InvalidPopulationSize(n);

        uint256 totalWeight = 0;
        uint256 rawEntropySum = 0;
        uint256 concentrationSum = 0;

        for (uint256 i = 0; i < n; i++) {
            uint256 a_i = weights[i];
            totalWeight += a_i;
            concentrationSum += (a_i * a_i) / WAD;

            if (a_i > MIN_AUTHORITY_THRESHOLD) {
                int256 ln_ai = lnWad(a_i); // Negative value since a_i < WAD
                int256 p_ln_p = (int256(a_i) * ln_ai) / int256(WAD);
                rawEntropySum += uint256(-p_ln_p);
            }
        }

        // Verify simplex constraint: sum(a_i) == 1.0 (with 0.001% tolerance for numerical rounding)
        if (totalWeight < WAD - 1e14 || totalWeight > WAD + 1e14) {
            revert InvalidSimplexNormalization(totalWeight);
        }

        int256 lnN = lnWad(n * WAD);
        de = (rawEntropySum * WAD) / uint256(lnN);
        ac = concentrationSum;
    }

    /**
     * @notice Strictly verifies that the given authority allocation satisfies DE >= DE_min.
     * @param epoch Consensus epoch identifier.
     * @param weights Normalized authority vector.
     * @param deMin Minimum constitutional entropy bound (e.g., 0.60 * 1e18).
     */
    function verifyEntropyInvariant(
        uint256 epoch,
        uint256[] calldata weights,
        uint256 deMin
    ) external returns (bool valid, uint256 de, uint256 ac) {
        (de, ac) = calculateEntropy(weights);
        if (de < deMin) {
            revert EntropyBelowConstitutionalBound(de, deMin);
        }
        emit EntropyVerified(epoch, de, ac);
        return (true, de, ac);
    }
}