/**
 * Hardhat Deployment Script for Local Ganache / Hardhat Node (Tier 2)
 */
const hre = require("hardhat");

async function main() {
  console.log("[*] Deploying ADG Smart Contracts to Local EVM Testbed...");

  const [deployer] = await hre.ethers.getSigners();
  console.log("    Deployer Address:", deployer.address);

  // 1. Deploy EntropyConstraint
  const EntropyConstraint = await hre.ethers.getContractFactory("EntropyConstraint");
  const entropyOracle = await EntropyConstraint.deploy();
  await entropyOracle.waitForDeployment();
  console.log("[+] EntropyConstraint deployed at:", await entropyOracle.getAddress());

  // 2. Deploy ADGCoordinator
  const ADGCoordinator = await hre.ethers.getContractFactory("ADGCoordinator");
  const coordinator = await ADGCoordinator.deploy(await entropyOracle.getAddress());
  await coordinator.waitForDeployment();
  console.log("[+] ADGCoordinator deployed at:", await coordinator.getAddress());

  // 3. Deploy SuccessionAutomaton
  const SuccessionAutomaton = await hre.ethers.getContractFactory("SuccessionAutomaton");
  const succession = await SuccessionAutomaton.deploy(await coordinator.getAddress());
  await succession.waitForDeployment();
  console.log("[+] SuccessionAutomaton deployed at:", await succession.getAddress());

  // 4. Deploy Benchmarks
  const StaticPBFTMock = await hre.ethers.getContractFactory("StaticPBFTMock");
  const pbftMock = await StaticPBFTMock.deploy(deployer.address);
  await pbftMock.waitForDeployment();

  const FlatDAOMock = await hre.ethers.getContractFactory("FlatDAOMock");
  const daoMock = await FlatDAOMock.deploy();
  await daoMock.waitForDeployment();

  console.log("[+] Benchmark Mocks successfully deployed.");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});