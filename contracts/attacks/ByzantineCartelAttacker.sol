// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../core/ADGCoordinator.sol";
import "../core/EntropyConstraint.sol";
import "../core/DynamicCommittee.sol";
import "../governance/SuccessionAutomaton.sol";

/**
 * @title ByzantineCartelAttacker
 * @notice Active attack harness executing adversarial Byzantine vectors against ADG on EVM:
 *         1. Strategic Coalition Collusion (Attempting to exceed rho_max or force DE < DE_min).
 *         2. Malicious Equivocation (Double-signing conflicting succession proposals).
 *         3. Quorum Starvation (Withholding signatures to breach 2f_m + 1 supermajority).
 *         4. Sybil Swarm Injection (Flooding network with unverified, zero-reputation nodes).
 * @dev Validates Theorems 2 and 3 and Lemma 1 by verifying that malicious state transitions are reverted.
 */
contract ByzantineCartelAttacker {
    uint256 public constant WAD = 1e18;

    ADGCoordinator public coordinator;
    EntropyConstraint public entropyOracle;
    DynamicCommittee public committee;
    SuccessionAutomaton public automaton;

    address[] public cartelNodes;
    uint256[] public cartelPrivateKeys; // For deterministic off-chain/local test signing

    event AttackAttempted(string indexed attackType, bool intercepted, bytes reason);
    event SybilSwarmInjected(uint256 count, uint256 successfulRegistrations);
    event EquivocationExecuted(address indexed maliciousSigner, bytes32 hashA, bytes32 hashB);

    constructor(
        address _coordinator,
        address _entropyOracle,
        address _committee,
        address _automaton
    ) {
        coordinator = ADGCoordinator(_coordinator);
        entropyOracle = EntropyConstraint(_entropyOracle);
        committee = DynamicCommittee(_committee);
        automaton = SuccessionAutomaton(_automaton);
    }

    /**
     * @notice Registers a cartel of compromised Byzantine nodes.
     */
    function registerCartelMembers(address[] calldata members) external {
        for (uint256 i = 0; i < members.length; i++) {
            cartelNodes.push(members[i]);
        }
    }

    /**
     * @notice Attack Vector 1: Attempt to inject an authority distribution violating the Coalition Bound (rho_max).
     * @dev Generates an authority vector allocating > rho_max (e.g. 50% or 100%) to top-f colluding nodes.
     *      Expects transaction to be intercepted by EntropyConstraint.sol with CoalitionAuthorityExceedsBound.
     */
    function attackCoalitionConcentration(
        uint256 nodeCount,
        uint256 fCartelSize,
        uint256 cartelShareWad
    ) external returns (bool intercepted, bytes memory returnData) {
        require(nodeCount > 0 && fCartelSize <= nodeCount, "Invalid sizes");
        require(cartelShareWad <= WAD, "Share exceeds 100%");

        uint256[] memory maliciousWeights = new uint256[](nodeCount);

        // Allocate cartelShareWad evenly among fCartelSize nodes
        uint256 perCartelWeight = cartelShareWad / fCartelSize;
        for (uint256 i = 0; i < fCartelSize; i++) {
            maliciousWeights[i] = perCartelWeight;
        }

        // Distribute remaining authority among the honest nodes
        uint256 remainingShare = WAD - (perCartelWeight * fCartelSize);
        uint256 honestCount = nodeCount - fCartelSize;
        if (honestCount > 0) {
            uint256 perHonestWeight = remainingShare / honestCount;
            for (uint256 i = fCartelSize; i < nodeCount; i++) {
                maliciousWeights[i] = perHonestWeight;
            }
        }

        // Attempt verification on EntropyConstraint
        try entropyOracle.verifyConstitutionalInvariants(
            coordinator.currentEpoch(),
            maliciousWeights,
            coordinator.constitutionalDEMin(),
            coordinator.constitutionalRhoMax()
        ) returns (bool, uint256, uint256, uint256) {
            // Attack bypassed security!
            intercepted = false;
            emit AttackAttempted("COALITION_CONCENTRATION_BREACH", false, "");
        } catch (bytes memory err) {
            // Correctly intercepted by constitutional invariant
            intercepted = true;
            returnData = err;
            emit AttackAttempted("COALITION_CONCENTRATION_BREACH", true, err);
        }
    }

    /**
     * @notice Attack Vector 2: Executes a double-signing equivocation attack against SuccessionAutomaton.
     * @dev Submits two valid certificates for the same epoch with conflicting state hashes signed by the same validator.
     */
    function attackEquivocation(
        SuccessionAutomaton.HandoverCertificate calldata certA,
        bytes[] calldata sigsA,
        address[] calldata signersA,
        SuccessionAutomaton.HandoverCertificate calldata certB,
        bytes[] calldata sigsB,
        address[] calldata signersB
    ) external returns (bool firstSucceeded, bool secondIntercepted) {
        // Submit first valid certificate
        try automaton.executeZeroForkHandover(certA, sigsA, signersA) {
            firstSucceeded = true;
        } catch {
            firstSucceeded = false;
        }

        // Submit conflicting certificate for the same epoch signed by overlapping validators
        try automaton.executeZeroForkHandover(certB, sigsB, signersB) {
            secondIntercepted = false; // Equivocation succeeded (system failed)
            emit AttackAttempted("EQUIVOCATION_DOUBLE_SIGN", false, "");
        } catch (bytes memory err) {
            secondIntercepted = true; // Equivocation caught and slashed
            emit AttackAttempted("EQUIVOCATION_DOUBLE_SIGN", true, err);
        }
    }

    /**
     * @notice Attack Vector 3: Quorum Starvation. Submits handover certificate with strictly < 2f_m + 1 signers.
     */
    function attackQuorumStarvation(
        SuccessionAutomaton.HandoverCertificate calldata cert,
        bytes[] calldata insufficientSigs,
        address[] calldata insufficientSigners
    ) external returns (bool intercepted, bytes memory returnData) {
        try automaton.executeZeroForkHandover(cert, insufficientSigs, insufficientSigners) {
            intercepted = false;
            emit AttackAttempted("QUORUM_STARVATION", false, "");
        } catch (bytes memory err) {
            intercepted = true;
            returnData = err;
            emit AttackAttempted("QUORUM_STARVATION", true, err);
        }
    }

    /**
     * @notice Attack Vector 4: Floods the DynamicCommittee with newly generated Sybil identities.
     */
    function attackSybilSwarm(uint256 count) external returns (uint256 successfulRegistrations) {
        successfulRegistrations = 0;
        for (uint256 i = 0; i < count; i++) {
            address fakeIdentity = address(uint160(uint256(keccak256(abi.encodePacked(address(this), i, block.timestamp)))));
            try committee.registerValidator(fakeIdentity, 10e18, 0) {
                successfulRegistrations++;
            } catch {
                // Intercepted or rejected
            }
        }
        emit SybilSwarmInjected(count, successfulRegistrations);
    }
}