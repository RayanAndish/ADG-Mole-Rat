/**
 * Hardhat Local Ganache Deployment & Metadata Exporter
 * Deploys all ADG core, governance, benchmark, and attack contracts.
 * Exports addresses, RPC URL, and ABIs to offchain_engine/deployed_contracts_ganache.json
 */
const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  console.log("=================================================================");
  console.log("[*] Deploying ADG Contracts to Ganache (Port 7545)...");
  console.log("=================================================================");

  const [deployer, validator1, validator2, validator3] = await hre.ethers.getSigners();
  const networkConfig = hre.config.networks[hre.network.name] || {};
  const rpcUrl = networkConfig.url || "http://127.0.0.1:7545";

  console.log("    Deployer Address :", deployer.address);
  console.log("    Target RPC URL   :", rpcUrl);
  console.log("    Network Name     :", hre.network.name);

  // 1. Deploy EntropyConstraint
  const EntropyConstraint = await hre.ethers.getContractFactory("EntropyConstraint");
  const entropyOracle = await EntropyConstraint.deploy();
  await entropyOracle.waitForDeployment();
  const entropyAddr = await entropyOracle.getAddress();
  console.log("[+] EntropyConstraint deployed at      :", entropyAddr);

  // 2. Deploy ADGCoordinator
  const ADGCoordinator = await hre.ethers.getContractFactory("ADGCoordinator");
  const coordinator = await ADGCoordinator.deploy(entropyAddr);
  await coordinator.waitForDeployment();
  const coordAddr = await coordinator.getAddress();
  console.log("[+] ADGCoordinator deployed at         :", coordAddr);

  // 3. Extract DynamicCommittee (deployed by ADGCoordinator constructor)
  const committeeAddr = await coordinator.committeeManager();
  console.log("[+] DynamicCommittee auto-deployed at  :", committeeAddr);

  // 4. Deploy SignalDistributor
  const SignalDistributor = await hre.ethers.getContractFactory("SignalDistributor");
  const signalDist = await SignalDistributor.deploy(coordAddr);
  await signalDist.waitForDeployment();
  const signalDistAddr = await signalDist.getAddress();
  console.log("[+] SignalDistributor deployed at      :", signalDistAddr);

  // 5. Deploy DynamicGovernanceScore
  const DynamicGovernanceScore = await hre.ethers.getContractFactory("DynamicGovernanceScore");
  const gsfContract = await DynamicGovernanceScore.deploy(coordAddr);
  await gsfContract.waitForDeployment();
  const gsfAddr = await gsfContract.getAddress();
  console.log("[+] DynamicGovernanceScore deployed at :", gsfAddr);

  // 6. Deploy SuccessionAutomaton
  const SuccessionAutomaton = await hre.ethers.getContractFactory("SuccessionAutomaton");
  const succession = await SuccessionAutomaton.deploy(coordAddr);
  await succession.waitForDeployment();
  const succAddr = await succession.getAddress();
  console.log("[+] SuccessionAutomaton deployed at    :", succAddr);

  // 7. Deploy Benchmarks (StaticPBFT, FlatDAO, Tendermint)
  const StaticPBFTMock = await hre.ethers.getContractFactory("StaticPBFTMock");
  const pbftMock = await StaticPBFTMock.deploy(deployer.address);
  await pbftMock.waitForDeployment();
  const pbftAddr = await pbftMock.getAddress();

  const FlatDAOMock = await hre.ethers.getContractFactory("FlatDAOMock");
  const daoMock = await FlatDAOMock.deploy();
  await daoMock.waitForDeployment();
  const daoAddr = await daoMock.getAddress();

  const validatorList = [deployer.address, validator1.address, validator2.address, validator3.address];
  const TendermintMock = await hre.ethers.getContractFactory("TendermintMock");
  const tendermintMock = await TendermintMock.deploy(validatorList);
  await tendermintMock.waitForDeployment();
  const tendermintAddr = await tendermintMock.getAddress();
  console.log("[+] Benchmark Mocks deployed (PBFT, DAO, Tendermint)");

  // 8. Deploy Attack Harnesses
  const ByzantineCartelAttacker = await hre.ethers.getContractFactory("ByzantineCartelAttacker");
  const cartelAttacker = await ByzantineCartelAttacker.deploy();
  await cartelAttacker.waitForDeployment();
  const cartelAddr = await cartelAttacker.getAddress();

  const SybilChurnInjector = await hre.ethers.getContractFactory("SybilChurnInjector");
  const sybilInjector = await SybilChurnInjector.deploy(committeeAddr);
  await sybilInjector.waitForDeployment();
  const sybilAddr = await sybilInjector.getAddress();

  const EmergencyExploitSimulator = await hre.ethers.getContractFactory("EmergencyExploitSimulator");
  const exploitSim = await EmergencyExploitSimulator.deploy(coordAddr);
  await exploitSim.waitForDeployment();
  const exploitAddr = await exploitSim.getAddress();
  console.log("[+] Adversarial Attack Harnesses deployed");

  // 9. Export metadata JSON for Python engine
  const deploymentPayload = {
    network: "ganache",
    rpcUrl: rpcUrl,
    chainId: 1337,
    deployerAddress: deployer.address,
    contracts: {
      EntropyConstraint: entropyAddr,
      ADGCoordinator: coordAddr,
      DynamicCommittee: committeeAddr,
      SignalDistributor: signalDistAddr,
      DynamicGovernanceScore: gsfAddr,
      SuccessionAutomaton: succAddr,
      StaticPBFTMock: pbftAddr,
      FlatDAOMock: daoAddr,
      TendermintMock: tendermintAddr,
      ByzantineCartelAttacker: cartelAddr,
      SybilChurnInjector: sybilAddr,
      EmergencyExploitSimulator: exploitAddr
    },
    artifactsDir: path.resolve(__dirname, "../artifacts/contracts")
  };

  const outputFilePath = path.resolve(__dirname, "../offchain_engine/deployed_contracts_ganache.json");
  fs.writeFileSync(outputFilePath, JSON.stringify(deploymentPayload, null, 2));
  console.log("\n[+] Deployment metadata successfully exported to:\n    -->", outputFilePath);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});