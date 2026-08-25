require("@nomicfoundation/hardhat-toolbox");

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
    compilers: [
      { version: "0.8.20" },
      {
        version: "0.8.24",
        settings: {
          evmVersion: "paris",
          optimizer: { enabled: true, runs: 200 },
          viaIR: true,
        },
      },
    ],
  },
  networks: {
    ganache: {
      url: "http://127.0.0.1:7545",
      accounts: {
        mnemonic:
          "art either market skirt absent purchase scrub half advance scorpion crucial diesel",
        path: "m/44'/60'/0'/0",
        initialIndex: 0,
        count: 10,
      },
    },
    localhost: {
      url: "http://127.0.0.1:7545",
    },
    sepolia: {
      url: "https://ethereum-sepolia-rpc.publicnode.com",
      accounts: [
        "f2ef69829e1761b41269d7c97ba4f15918ac54c1faffa7f312bd6ff9cd15a99e",
      ],
      chainId: 11155111,
    },
  },
};
