# ADG Framework Evaluation

Academic evaluation, simulation, and benchmarking suite for the **Adaptive Dynamic Governance (ADG)** protocol.

## Structure

| Directory | Purpose |
|---|---|
| `contracts/` | Tier 2 – EVM on-chain smart contracts (core, governance, benchmarks, attacks) |
| `offchain_engine/` | Master mathematical & simulation engines (Python) |
| `scripts/` | Deployment & orchestration (Hardhat / Ganache / Sepolia) |
| `tests_and_benchmarks/` | Comprehensive 3-tier experimental suite |
| `paper_outputs/` | Generated CSV datasets, figures, and LaTeX tables |

## Quick Start

```bash
# Install Node dependencies
npm install

# Compile Solidity contracts
npm run compile

# Install Python dependencies
pip install -r requirements.txt
```

## License

MIT
