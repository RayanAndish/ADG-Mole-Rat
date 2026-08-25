E:\Mole-Rat-ADG>npm run pipeline:full

> adg-framework-evaluation@1.0.0 pipeline:full
> npm run compile && npm run deploy:ganache && npm run sim:scalability && npm run sim:byzantine && npm run sim:churn && npm run sim:sobol && npm run gas:profile && npm run ledger:ganache && npm run ledger:sepolia && npm run artifacts:generate


> adg-framework-evaluation@1.0.0 compile
> hardhat compile

Nothing to compile

> adg-framework-evaluation@1.0.0 deploy:ganache
> hardhat run scripts/deploy_local_ganache.cjs --network ganache

=================================================================
[*] Deploying ADG Contracts to Ganache (Port 7545)...
=================================================================
    Deployer Address : 0xF4BCdF4fa4D90a8576cf83D3dDFca29D877c7C12
    Target RPC URL   : http://127.0.0.1:7545
    Network Name     : ganache
[+] EntropyConstraint deployed at      : 0x1Ca2f6Fd04331351818F468ca7F681F53b1dB834
[+] ADGCoordinator deployed at         : 0x4f7D3868a40Bd36c68684db9C0DE938580E672Bc
[+] DynamicCommittee auto-deployed at  : 0x500eF0bAa8aDD92dFF69e02f68710E895F0C2c65
[+] SignalDistributor deployed at      : 0xDC9ddc1ED9eb0E08a464f520806b4edb948aF093
[+] DynamicGovernanceScore deployed at : 0x088616abeaab03FA9e840Cf87C1882F9413969c5
[+] SuccessionAutomaton deployed at    : 0x5E5740330A5D117090d4D8591996699C00F80caA
[+] Benchmark Mocks deployed (PBFT, DAO, Tendermint)
[+] Adversarial Attack Harnesses deployed

[+] Deployment metadata successfully exported to:
    --> E:\Mole-Rat-ADG\offchain_engine\deployed_contracts_ganache.json

> adg-framework-evaluation@1.0.0 sim:scalability
> python tests_and_benchmarks/run_monte_carlo_scalability.py

[*] Starting 6-Scale Multi-Epoch Monte Carlo Benchmark...
    Scales: [50, 100, 1000, 5000, 20000, 100000] (Node Count N = 128)

=================================================================
[*] Executing Scale: 50 Epochs
=================================================================
[+] Individual scale dataset saved to:
    --> E:\Mole-Rat-ADG\paper_outputs\csv_datasets\monte_carlo_results_N_50.csv
    Summary -> TPS: 114,432.0 (Var: 975,707,558.3) | Latency: 59.41 ms | Gini: 0.0003 | Min DE: 0.9986

=================================================================
[*] Executing Scale: 100 Epochs
=================================================================
[+] Individual scale dataset saved to:
    --> E:\Mole-Rat-ADG\paper_outputs\csv_datasets\monte_carlo_results_N_100.csv
    Summary -> TPS: 136,234.2 (Var: 836,100,820.2) | Latency: 55.96 ms | Gini: 0.0002 | Min DE: 0.9985

=================================================================
[*] Executing Scale: 1,000 Epochs
=================================================================
[+] Individual scale dataset saved to:
    --> E:\Mole-Rat-ADG\paper_outputs\csv_datasets\monte_carlo_results_N_1000.csv
    Summary -> TPS: 146,588.0 (Var: 101,529,089.0) | Latency: 52.65 ms | Gini: 0.0000 | Min DE: 0.9990

=================================================================
[*] Executing Scale: 5,000 Epochs
=================================================================
[+] Individual scale dataset saved to:
    --> E:\Mole-Rat-ADG\paper_outputs\csv_datasets\monte_carlo_results_N_5000.csv
    Summary -> TPS: 145,846.0 (Var: 20,060,921.9) | Latency: 52.35 ms | Gini: 0.0000 | Min DE: 0.9981

=================================================================
[*] Executing Scale: 20,000 Epochs
=================================================================
[+] Individual scale dataset saved to:
    --> E:\Mole-Rat-ADG\paper_outputs\csv_datasets\monte_carlo_results_N_20000.csv
    Summary -> TPS: 140,022.6 (Var: 4,529,703.0) | Latency: 52.23 ms | Gini: 0.0000 | Min DE: 0.9949

=================================================================
[*] Executing Scale: 100,000 Epochs
=================================================================
[+] Individual scale dataset saved to:
    --> E:\Mole-Rat-ADG\paper_outputs\csv_datasets\monte_carlo_results_N_100000.csv
    Summary -> TPS: 143,023.1 (Var: 956,313.9) | Latency: 52.26 ms | Gini: 0.0000 | Min DE: 0.9956

[+] Master 6-Scale Convergence Summary saved to:
    --> E:\Mole-Rat-ADG\paper_outputs\csv_datasets\monte_carlo_scale_convergence_summary.csv

> adg-framework-evaluation@1.0.0 sim:byzantine
> python tests_and_benchmarks/run_byzantine_resilience.py

[*] Starting Byzantine Fault Resilience Suite (N = 128 nodes)...

---> Testing Byzantine Adversary Fraction f = 0.0%
     f=0.00 | ADG P(Cap): 0.0000 | ADG Fork: 0.0% | PBFT Fork: 0.0% | DAO P(Cap): 0.0000

---> Testing Byzantine Adversary Fraction f = 5.0%
     f=0.05 | ADG P(Cap): 0.0000 | ADG Fork: 0.0% | PBFT Fork: 0.0% | DAO P(Cap): 0.0667

---> Testing Byzantine Adversary Fraction f = 10.0%
     f=0.10 | ADG P(Cap): 0.0000 | ADG Fork: 0.0% | PBFT Fork: 0.0% | DAO P(Cap): 0.2000

---> Testing Byzantine Adversary Fraction f = 15.0%
     f=0.15 | ADG P(Cap): 0.0000 | ADG Fork: 0.0% | PBFT Fork: 0.0% | DAO P(Cap): 0.3333

---> Testing Byzantine Adversary Fraction f = 20.0%
     f=0.20 | ADG P(Cap): 0.0000 | ADG Fork: 0.0% | PBFT Fork: 0.0% | DAO P(Cap): 0.5000

---> Testing Byzantine Adversary Fraction f = 25.0%
     f=0.25 | ADG P(Cap): 0.0000 | ADG Fork: 0.0% | PBFT Fork: 13.3% | DAO P(Cap): 0.6333

---> Testing Byzantine Adversary Fraction f = 30.0%
     f=0.30 | ADG P(Cap): 0.0000 | ADG Fork: 0.0% | PBFT Fork: 36.7% | DAO P(Cap): 0.6000

---> Testing Byzantine Adversary Fraction f = 33.0%
     f=0.33 | ADG P(Cap): 0.0000 | ADG Fork: 0.0% | PBFT Fork: 20.0% | DAO P(Cap): 0.6667

---> Testing Byzantine Adversary Fraction f = 35.0%
     f=0.35 | ADG P(Cap): 0.0000 | ADG Fork: 3.3% | PBFT Fork: 100.0% | DAO P(Cap): 0.8000

---> Testing Byzantine Adversary Fraction f = 40.0%
     f=0.40 | ADG P(Cap): 0.0000 | ADG Fork: 10.0% | PBFT Fork: 100.0% | DAO P(Cap): 0.8667

[+] Byzantine resilience benchmark logged to: paper_outputs/csv_datasets\byzantine_resilience_results.csv

> adg-framework-evaluation@1.0.0 sim:churn
> python tests_and_benchmarks/run_leader_crash_churn.py

[*] Starting Leader Crash & Dynamic Churn Benchmark...

---> Evaluating Validator Churn Rate = 5%
     Churn: 5% | Success Rate: 100.0% | Handover Latency: 15.05 ms | Msg Overhead: 242.0

---> Evaluating Validator Churn Rate = 10%
     Churn: 10% | Success Rate: 100.0% | Handover Latency: 15.06 ms | Msg Overhead: 230.0

---> Evaluating Validator Churn Rate = 20%
     Churn: 20% | Success Rate: 100.0% | Handover Latency: 15.05 ms | Msg Overhead: 204.0

---> Evaluating Validator Churn Rate = 30%
     Churn: 30% | Success Rate: 92.0% | Handover Latency: 15.00 ms | Msg Overhead: 178.0

---> Evaluating Validator Churn Rate = 40%
     Churn: 40% | Success Rate: 8.0% | Handover Latency: 14.85 ms | Msg Overhead: 152.0

---> Evaluating Validator Churn Rate = 50%
     Churn: 50% | Success Rate: 0.0% | Handover Latency: 0.00 ms | Msg Overhead: 0.0

[+] Leader crash benchmark logged to: paper_outputs/csv_datasets\leader_crash_churn_results.csv

> adg-framework-evaluation@1.0.0 sim:sobol
> python tests_and_benchmarks/run_sobol_sensitivity.py

[*] Executing Global Sobol Sensitivity Analysis (LHS N = 256)...
[+] Sobol sensitivity analysis logged to: paper_outputs/csv_datasets\sobol_sensitivity_results.csv

> adg-framework-evaluation@1.0.0 gas:profile
> python tests_and_benchmarks/run_evm_gas_benchmarks.py

[*] Profiling EVM Gas Consumption across Smart Contract Operations...
[+] EVM Gas benchmark results logged to: E:\Mole-Rat-ADG\paper_outputs\csv_datasets\evm_gas_benchmarks.csv

> adg-framework-evaluation@1.0.0 ledger:ganache
> python tests_and_benchmarks/run_ganache_ledger.py

[+] Connected to Live Ganache RPC: http://127.0.0.1:7545
[*] Dispatching 20,000 live state-transition transactions to Ganache in chunks of 1000...
    -> Mined 1,000/20,000 TXs (28.4 tx/s) | Latest Block: 42403
    -> Mined 2,000/20,000 TXs (28.5 tx/s) | Latest Block: 43403
    -> Mined 3,000/20,000 TXs (28.4 tx/s) | Latest Block: 44403
    -> Mined 4,000/20,000 TXs (28.2 tx/s) | Latest Block: 45403
    -> Mined 5,000/20,000 TXs (28.0 tx/s) | Latest Block: 46403
    -> Mined 6,000/20,000 TXs (27.7 tx/s) | Latest Block: 47403
    -> Mined 7,000/20,000 TXs (27.8 tx/s) | Latest Block: 48403
    -> Mined 8,000/20,000 TXs (27.8 tx/s) | Latest Block: 49403
    -> Mined 9,000/20,000 TXs (27.8 tx/s) | Latest Block: 50403
    -> Mined 10,000/20,000 TXs (27.7 tx/s) | Latest Block: 51403
    -> Mined 11,000/20,000 TXs (27.7 tx/s) | Latest Block: 52403
    -> Mined 12,000/20,000 TXs (27.7 tx/s) | Latest Block: 53403
    -> Mined 13,000/20,000 TXs (27.7 tx/s) | Latest Block: 54403
    -> Mined 14,000/20,000 TXs (27.7 tx/s) | Latest Block: 55403
    -> Mined 15,000/20,000 TXs (27.7 tx/s) | Latest Block: 56403
    -> Mined 16,000/20,000 TXs (27.7 tx/s) | Latest Block: 57403
    -> Mined 17,000/20,000 TXs (27.7 tx/s) | Latest Block: 58403
    -> Mined 18,000/20,000 TXs (27.7 tx/s) | Latest Block: 59403
    -> Mined 19,000/20,000 TXs (27.7 tx/s) | Latest Block: 60403
    -> Mined 20,000/20,000 TXs (27.7 tx/s) | Latest Block: 61403

[+] 20,000 Ganache blockchain transactions successfully exported to:
    --> E:\Mole-Rat-ADG\paper_outputs\csv_datasets\ganache_blockchain_ledger_full.csv
    Mean Latency : 36.09 ms | Std: 4.65 | Variance: 21.64
    Mean Gas Used: 95519.1 | Variance: 94.56

> adg-framework-evaluation@1.0.0 ledger:sepolia
> python tests_and_benchmarks/run_sepolia_live_benchmark.py

[+] Connected to Live Sepolia via: https://ethereum-sepolia-rpc.publicnode.com
    Account : 0xE070cB040318102Dc47F90e7ca9d8b4AB5b66356
    Balance : 0.535949925553200961 ETH (Chain ID: 11155111)
[*] Broadcasting 50 live state-transition transactions...
    [01/50] Mined in Block 11566628 | Latency: 13.04s | Gas: 95440
    [02/50] Mined in Block 11566629 | Latency: 10.63s | Gas: 95440
    [03/50] Mined in Block 11566630 | Latency: 11.84s | Gas: 95440
    [04/50] Mined in Block 11566631 | Latency: 8.64s | Gas: 95440
    [05/50] Mined in Block 11566632 | Latency: 9.30s | Gas: 95440
    [06/50] Mined in Block 11566633 | Latency: 10.60s | Gas: 95440
    [07/50] Mined in Block 11566634 | Latency: 10.16s | Gas: 95440
    [08/50] Mined in Block 11566635 | Latency: 9.53s | Gas: 95440
    [09/50] Mined in Block 11566636 | Latency: 9.22s | Gas: 95440
    [10/50] Mined in Block 11566637 | Latency: 13.45s | Gas: 95480
    [11/50] Mined in Block 11566638 | Latency: 6.62s | Gas: 95480
    [12/50] Mined in Block 11566639 | Latency: 10.04s | Gas: 95480
    [13/50] Mined in Block 11566640 | Latency: 11.43s | Gas: 95480
    [14/50] Mined in Block 11566641 | Latency: 8.67s | Gas: 95480
    [15/50] Mined in Block 11566642 | Latency: 9.84s | Gas: 95480
    [16/50] Mined in Block 11566643 | Latency: 11.08s | Gas: 95480
    [17/50] Mined in Block 11566644 | Latency: 8.87s | Gas: 95480
    [18/50] Mined in Block 11566645 | Latency: 11.02s | Gas: 95480
    [19/50] Mined in Block 11566646 | Latency: 9.82s | Gas: 95480
    [20/50] Mined in Block 11566647 | Latency: 10.15s | Gas: 95480
    [21/50] Mined in Block 11566648 | Latency: 9.83s | Gas: 95480
    [22/50] Mined in Block 11566649 | Latency: 9.27s | Gas: 95480
    [23/50] Mined in Block 11566650 | Latency: 22.13s | Gas: 95480
    [24/50] Mined in Block 11566651 | Latency: 9.85s | Gas: 95480
    [25/50] Mined in Block 11566652 | Latency: 11.16s | Gas: 95480
    [26/50] Mined in Block 11566653 | Latency: 8.93s | Gas: 95480
    [27/50] Mined in Block 11566654 | Latency: 9.88s | Gas: 95480
    [28/50] Mined in Block 11566655 | Latency: 11.26s | Gas: 95480
    [29/50] Mined in Block 11566656 | Latency: 8.77s | Gas: 95480
    [30/50] Mined in Block 11566657 | Latency: 10.97s | Gas: 95480
    [31/50] Mined in Block 11566658 | Latency: 10.05s | Gas: 95480
    [32/50] Mined in Block 11566659 | Latency: 9.91s | Gas: 95480
    [33/50] Mined in Block 11566660 | Latency: 9.00s | Gas: 95480
    [34/50] Mined in Block 11566661 | Latency: 10.99s | Gas: 95480
    [35/50] Mined in Block 11566662 | Latency: 9.40s | Gas: 95480
    [36/50] Mined in Block 11566663 | Latency: 9.68s | Gas: 95480
    [37/50] Mined in Block 11566664 | Latency: 9.99s | Gas: 95480
    [38/50] Mined in Block 11566665 | Latency: 9.99s | Gas: 95480
    [39/50] Mined in Block 11566666 | Latency: 11.00s | Gas: 95480
    [40/50] Mined in Block 11566667 | Latency: 9.06s | Gas: 95480
    [41/50] Mined in Block 11566668 | Latency: 9.98s | Gas: 95480
    [42/50] Mined in Block 11566669 | Latency: 11.14s | Gas: 95480
    [43/50] Mined in Block 11566670 | Latency: 8.93s | Gas: 95480
    [44/50] Mined in Block 11566671 | Latency: 10.75s | Gas: 95480
    [45/50] Mined in Block 11566672 | Latency: 9.48s | Gas: 95480
    [46/50] Mined in Block 11566673 | Latency: 10.39s | Gas: 95480
    [47/50] Mined in Block 11566674 | Latency: 9.22s | Gas: 95480
    [48/50] Mined in Block 11566675 | Latency: 11.14s | Gas: 95480
    [49/50] Mined in Block 11566676 | Latency: 8.89s | Gas: 95480
    [50/50] Mined in Block 11566677 | Latency: 10.96s | Gas: 95480

[+] 50 Live Sepolia transactions successfully mined and exported to:
    --> E:\Mole-Rat-ADG\paper_outputs\csv_datasets\sepolia_real_mined_transactions_ledger.csv

> adg-framework-evaluation@1.0.0 artifacts:generate
> python tests_and_benchmarks/generate_all_publication_artifacts.py

[*] Generating Camera-Ready LaTeX Tables...
[+] LaTeX tables successfully generated in: E:\Mole-Rat-ADG\paper_outputs\tables
[*] Rendering High-Resolution Vector Figures (.pdf / .png)...
[+] All publication vector figures generated in: E:\Mole-Rat-ADG\paper_outputs\figures