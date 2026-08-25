/**
 * Hardhat Ethereum Sepolia Live Deployment & Metadata Exporter
 */
const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  console.log("=================================================================");
  console.log("[*] Deploying Core ADG Contracts to Ethereum Sepolia Testnet...");
  console.log("=================================================================");

  const [deployer] = await hre.ethers.getSigners();
  const networkConfig = hre.config.networks.sepolia || {};
  const rpcUrl = networkConfig.url || "https://ethereum-sepolia-rpc.publicnode.com";

  console.log("    Deployer Address :", deployer.address);
  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log("    Sepolia Balance  :", hre.ethers.formatEther(balance), "ETH");

  // 1. Deploy EntropyConstraint
  const EntropyConstraint = await hre.ethers.getContractFactory("EntropyConstraint");
  const entropyOracle = await EntropyConstraint.deploy();
  await entropyOracle.waitForDeployment();
  const entropyAddr = await entropyOracle.getAddress();
  console.log("[1/3] EntropyConstraint deployed at  :", entropyAddr);

  // 2. Deploy ADGCoordinator
  const ADGCoordinator = await hre.ethers.getContractFactory("ADGCoordinator");
  const coordinator = await ADGCoordinator.deploy(entropyAddr);
  await coordinator.waitForDeployment();
  const coordAddr = await coordinator.getAddress();
  console.log("[2/3] ADGCoordinator deployed at     :", coordAddr);

  // 3. Deploy SuccessionAutomaton
  const SuccessionAutomaton = await hre.ethers.getContractFactory("SuccessionAutomaton");
  const succession = await SuccessionAutomaton.deploy(coordAddr);
  await succession.waitForDeployment();
  const succAddr = await succession.getAddress();
  console.log("[3/3] SuccessionAutomaton deployed at:", succAddr);

  const deploymentPayload = {
    network: "sepolia",
    rpcUrl: rpcUrl,
    chainId: 11155111,
    deployerAddress: deployer.address,
    contracts: {
      EntropyConstraint: entropyAddr,
      ADGCoordinator: coordAddr,
      SuccessionAutomaton: succAddr
    }
  };

  const outputFilePath = path.resolve(__dirname, "../offchain_engine/deployed_contracts_sepolia.json");
  fs.writeFileSync(outputFilePath, JSON.stringify(deploymentPayload, null, 2));
  console.log("\n[+] Sepolia deployment metadata saved to:\n    -->", outputFilePath);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});