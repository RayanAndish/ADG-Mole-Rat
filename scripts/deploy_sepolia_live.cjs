/**
 * Hardhat Ethereum Sepolia Live Deployment & Metadata Exporter (ADG Tier 3)
 * Deploys strictly the core production ADG suite to public Ethereum Sepolia (Chain ID 11155111).
 * Used for benchmarking live EIP-1559 gas dynamics, RPC telemetry, and 50 mined blocks (Section 6.7).
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

  if (balance === 0n) {
    throw new Error("[-] Insufficient Sepolia ETH balance for deployment!");
  }

  // 1. Deploy EntropyConstraint (Constitutional Oracle)
  console.log("\n[1/3] Deploying EntropyConstraint...");
  const EntropyConstraint = await hre.ethers.getContractFactory("EntropyConstraint");
  const entropyOracle = await EntropyConstraint.deploy();
  await entropyOracle.waitForDeployment();
  const entropyAddr = await entropyOracle.getAddress();
  console.log("  [+] EntropyConstraint deployed at  :", entropyAddr);

  // 2. Deploy ADGCoordinator (Closed-Loop Master Engine)
  console.log("\n[2/3] Deploying ADGCoordinator...");
  const ADGCoordinator = await hre.ethers.getContractFactory("ADGCoordinator");
  const coordinator = await ADGCoordinator.deploy(entropyAddr);
  await coordinator.waitForDeployment();
  const coordAddr = await coordinator.getAddress();
  console.log("  [+] ADGCoordinator deployed at     :", coordAddr);

  // Extract auto-deployed DynamicCommittee address
  const committeeAddr = await coordinator.committeeManager();
  console.log("  [+] DynamicCommittee deployed at   :", committeeAddr);

  // 3. Deploy SuccessionAutomaton (Deterministic Handover State Machine)
  console.log("\n[3/3] Deploying SuccessionAutomaton...");
  const SuccessionAutomaton = await hre.ethers.getContractFactory("SuccessionAutomaton");
  const succession = await SuccessionAutomaton.deploy(coordAddr);
  await succession.waitForDeployment();
  const succAddr = await succession.getAddress();
  console.log("  [+] SuccessionAutomaton deployed at:", succAddr);

  // CRITICAL POST-DEPLOYMENT STEP: Authorize SuccessionAutomaton in Coordinator
  console.log("\n[*] Authorizing SuccessionAutomaton in ADGCoordinator...");
  const authTx = await coordinator.setSuccessionAutomaton(succAddr);
  console.log("    Waiting for Sepolia block inclusion (Tx:", authTx.hash, ")...");
  await authTx.wait(1);
  console.log("  [✔] SuccessionAutomaton successfully linked and authorized!");

  // 4. Export Sepolia Metadata for Off-Chain Engine
  const deploymentPayload = {
    network: "sepolia",
    chainId: 11155111,
    rpcUrl: rpcUrl,
    deployerAddress: deployer.address,
    deployedAt: new Date().toISOString(),
    contracts: {
      EntropyConstraint: entropyAddr,
      ADGCoordinator: coordAddr,
      DynamicCommittee: committeeAddr,
      SuccessionAutomaton: succAddr
    },
    artifactsDir: path.resolve(__dirname, "../artifacts/contracts")
  };

  const outputFilePath = path.resolve(__dirname, "../offchain_engine/deployed_contracts_sepolia.json");
  fs.writeFileSync(outputFilePath, JSON.stringify(deploymentPayload, null, 2));
  console.log("\n=================================================================");
  console.log(`[✔] Sepolia deployment complete! Metadata saved to:\n    --> ${outputFilePath}`);
  console.log("=================================================================\n");
}

main().catch((error) => {
  console.error("[-] Sepolia Deployment failed:", error);
  process.exitCode = 1;
});