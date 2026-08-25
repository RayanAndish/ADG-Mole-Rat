/**
 * Live Ethereum Sepolia Testnet Deployment Script
 * Deploys ADGCoordinator, EntropyConstraint, and SuccessionAutomaton to Public Sepolia.
 */
const hre = require("hardhat");

async function main() {
  console.log("[*] Initializing Deployment to Ethereum Sepolia Testnet...");

  const [deployer] = await hre.ethers.getSigners();
  console.log("    Deployer Address:", deployer.address);
  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log("    Sepolia Balance:", hre.ethers.formatEther(balance), "ETH");

  // 1. Deploy EntropyConstraint
  console.log("[1/3] Deploying EntropyConstraint.sol...");
  const EntropyConstraint = await hre.ethers.getContractFactory("EntropyConstraint");
  const entropyOracle = await EntropyConstraint.deploy();
  await entropyOracle.waitForDeployment();
  const entropyAddr = await entropyOracle.getAddress();
  console.log("      -> EntropyConstraint deployed at:", entropyAddr);

  // 2. Deploy ADGCoordinator
  console.log("[2/3] Deploying ADGCoordinator.sol...");
  const ADGCoordinator = await hre.ethers.getContractFactory("ADGCoordinator");
  const coordinator = await ADGCoordinator.deploy(entropyAddr);
  await coordinator.waitForDeployment();
  const coordAddr = await coordinator.getAddress();
  console.log("      -> ADGCoordinator deployed at:", coordAddr);

  // 3. Deploy SuccessionAutomaton
  console.log("[3/3] Deploying SuccessionAutomaton.sol...");
  const SuccessionAutomaton = await hre.ethers.getContractFactory("SuccessionAutomaton");
  const succession = await SuccessionAutomaton.deploy(coordAddr);
  await succession.waitForDeployment();
  const succAddr = await succession.getAddress();
  console.log("      -> SuccessionAutomaton deployed at:", succAddr);

  console.log("\n[+] Deployment Complete. Live Contracts Verified on Sepolia Etherscan.");
  console.log(JSON.stringify({
    network: "sepolia",
    entropyConstraint: entropyAddr,
    adgCoordinator: coordAddr,
    successionAutomaton: succAddr
  }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});