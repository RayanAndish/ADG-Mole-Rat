/**
 * Hardhat Deployment & Metadata Exporter (ADG Universal Deployer)
 * Supports both local Ganache (Port 7545) and public Ethereum Sepolia testnet.
 * Fully synchronized with revised contract constructors and constitutional security setup.
 */
const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const network = await hre.ethers.provider.getNetwork();
  const networkName = hre.network.name;
  const chainId = Number(network.chainId);

  console.log("=================================================================");
  console.log(`[*] Deploying ADG Contracts to: ${networkName.toUpperCase()} (Chain ID: ${chainId})`);
  console.log("=================================================================");

  // دریافت تمامی حساب‌های فعال متصل به گاناش
  const signers = await hre.ethers.getSigners();
  console.log(`[+] Detected ${signers.length} accounts from local provider.`);

  // آدرس مد نظر شما برای دیپلوی
  const TARGET_DEPLOYER = "0xF8AaA335eF3bD0EA15e34f04242Eb88752358A16".toLowerCase();

  // پیدا کردن اکانت شما از میان لیست اکانت‌های گاناش
  let deployer = signers.find(s => s.address.toLowerCase() === TARGET_DEPLOYER);

  if (deployer) {
    console.log("    [✔] Target Deployer Address Identified:", deployer.address);
  } else {
    console.warn(`    [!] Warning: Target address ${TARGET_DEPLOYER} not found in provider signers.`);
    console.warn("        Falling back to first available account:", signers[0].address);
    deployer = signers[0];
  }

  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log("    Deployer Balance :", hre.ethers.formatEther(balance), "ETH");

  // انتخاب ۳ حساب دیگر از همان گاناش شما برای تشکیل کمیته ۴ نفره BFT
  const otherSigners = signers.filter(s => s.address.toLowerCase() !== deployer.address.toLowerCase());

  let validatorList = [];
  if (otherSigners.length >= 3) {
    validatorList = [
      deployer.address,
      otherSigners[0].address,
      otherSigners[1].address,
      otherSigners[2].address
    ];
  } else {
    // در صورت وجود نداشتن حساب‌های کافی، از حساب‌های موجود استفاده می‌شود
    validatorList = signers.map(s => s.address);
  }

  console.log("\n[+] Configured 4 Real Ganache Validators for BFT Mocks:");
  validatorList.forEach((val, idx) => console.log(`    Validator [${idx}]: ${val}`));

  // ---------------------------------------------------------------------------
  // 1. Deploy Core Contracts
  // ---------------------------------------------------------------------------
  console.log("\n[1/4] Deploying Core Layer...");

  const EntropyConstraint = await hre.ethers.getContractFactory("EntropyConstraint");
  const entropyOracle = await EntropyConstraint.deploy();
  await entropyOracle.waitForDeployment();
  const entropyAddr = await entropyOracle.getAddress();
  console.log("  [+] EntropyConstraint deployed at      :", entropyAddr);

  const ADGCoordinator = await hre.ethers.getContractFactory("ADGCoordinator");
  const coordinator = await ADGCoordinator.deploy(entropyAddr);
  await coordinator.waitForDeployment();
  const coordAddr = await coordinator.getAddress();
  console.log("  [+] ADGCoordinator deployed at         :", coordAddr);

  // DynamicCommittee is auto-instantiated by ADGCoordinator constructor
  const committeeAddr = await coordinator.committeeManager();
  console.log("  [+] DynamicCommittee auto-deployed at  :", committeeAddr);

  const SignalDistributor = await hre.ethers.getContractFactory("SignalDistributor");
  const signalDist = await SignalDistributor.deploy(coordAddr);
  await signalDist.waitForDeployment();
  const signalDistAddr = await signalDist.getAddress();
  console.log("  [+] SignalDistributor deployed at      :", signalDistAddr);

  // ---------------------------------------------------------------------------
  // 2. Deploy Governance Contracts & Register Succession Automaton
  // ---------------------------------------------------------------------------
  console.log("\n[2/4] Deploying Governance Layer...");

  const DynamicGovernanceScore = await hre.ethers.getContractFactory("DynamicGovernanceScore");
  const gsfContract = await DynamicGovernanceScore.deploy(coordAddr);
  await gsfContract.waitForDeployment();
  const gsfAddr = await gsfContract.getAddress();
  console.log("  [+] DynamicGovernanceScore deployed at :", gsfAddr);

  const SuccessionAutomaton = await hre.ethers.getContractFactory("SuccessionAutomaton");
  const succession = await SuccessionAutomaton.deploy(coordAddr);
  await succession.waitForDeployment();
  const succAddr = await succession.getAddress();
  console.log("  [+] SuccessionAutomaton deployed at    :", succAddr);

  // CRITICAL SECURITY REGISTRATION: Link SuccessionAutomaton with ADGCoordinator
  const authTx = await coordinator.setSuccessionAutomaton(succAddr);
  await authTx.wait();
  console.log("  [*] SuccessionAutomaton registered in Coordinator (Tx:", authTx.hash.slice(0, 14) + "...)");

  // ---------------------------------------------------------------------------
  // 3. Deploy Benchmark Contracts (PBFT, Tendermint, FlatDAO)
  // ---------------------------------------------------------------------------
  console.log("\n[3/4] Deploying Baseline Benchmark Layer...");

  const StaticPBFTMock = await hre.ethers.getContractFactory("StaticPBFTMock");
  const pbftMock = await StaticPBFTMock.deploy(deployer.address);
  await pbftMock.waitForDeployment();
  const pbftAddr = await pbftMock.getAddress();
  console.log("  [+] StaticPBFTMock deployed at         :", pbftAddr);

  // FlatDAO requires initial token holders and initial balances (Governor Bravo layout)
  const initialBalances = [
    hre.ethers.parseEther("100000"),
    hre.ethers.parseEther("100000"),
    hre.ethers.parseEther("100000"),
    hre.ethers.parseEther("100000")
  ];
  const FlatDAOMock = await hre.ethers.getContractFactory("FlatDAOMock");
  const daoMock = await FlatDAOMock.deploy(validatorList, initialBalances);
  await daoMock.waitForDeployment();
  const daoAddr = await daoMock.getAddress();
  console.log("  [+] FlatDAOMock deployed at            :", daoAddr);

  const TendermintMock = await hre.ethers.getContractFactory("TendermintMock");
  const tendermintMock = await TendermintMock.deploy(validatorList);
  await tendermintMock.waitForDeployment();
  const tendermintAddr = await tendermintMock.getAddress();
  console.log("  [+] TendermintMock deployed at         :", tendermintAddr);

  // ---------------------------------------------------------------------------
  // 4. Deploy Adversarial Attack Harnesses
  // ---------------------------------------------------------------------------
  console.log("\n[4/4] Deploying Adversarial Attack Harnesses...");

  const ByzantineCartelAttacker = await hre.ethers.getContractFactory("ByzantineCartelAttacker");
  const cartelAttacker = await ByzantineCartelAttacker.deploy(coordAddr, entropyAddr, committeeAddr, succAddr);
  await cartelAttacker.waitForDeployment();
  const cartelAddr = await cartelAttacker.getAddress();
  console.log("  [+] ByzantineCartelAttacker deployed   :", cartelAddr);

  const SybilChurnInjector = await hre.ethers.getContractFactory("SybilChurnInjector");
  const sybilInjector = await SybilChurnInjector.deploy(committeeAddr);
  await sybilInjector.waitForDeployment();
  const sybilAddr = await sybilInjector.getAddress();
  console.log("  [+] SybilChurnInjector deployed        :", sybilAddr);

  const EmergencyExploitSimulator = await hre.ethers.getContractFactory("EmergencyExploitSimulator");
  const exploitSim = await EmergencyExploitSimulator.deploy(coordAddr, entropyAddr);
  await exploitSim.waitForDeployment();
  const exploitAddr = await exploitSim.getAddress();
  console.log("  [+] EmergencyExploitSimulator deployed :", exploitAddr);

  // ---------------------------------------------------------------------------
  // 5. Export Metadata Payload for Python Simulation Engine
  // ---------------------------------------------------------------------------
  const networkConfig = hre.config.networks[networkName] || {};
  const rpcUrl = networkConfig.url || "http://127.0.0.1:7545";

  const deploymentPayload = {
    network: networkName,
    chainId: chainId,
    rpcUrl: rpcUrl,
    deployerAddress: deployer.address,
    timestamp: new Date().toISOString(),
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

  const fileName = networkName === "sepolia" 
    ? "deployed_contracts_sepolia.json" 
    : "deployed_contracts_ganache.json";

  const outputFilePath = path.resolve(__dirname, `../offchain_engine/${fileName}`);
  fs.writeFileSync(outputFilePath, JSON.stringify(deploymentPayload, null, 2));

  console.log("\n=================================================================");
  console.log(`[✔] Deployment complete! Metadata exported to:\n    --> ${outputFilePath}`);
  console.log("=================================================================\n");
}

main().catch((error) => {
  console.error("[-] Deployment failed:", error);
  process.exitCode = 1;
});