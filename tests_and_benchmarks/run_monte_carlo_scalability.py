"""
Scenario 1: Monte Carlo Scalability Benchmark
Evaluates ADG throughput, finality latency, adaptation time (T_adapt), and entropy across N = 16 to 4096 nodes.
Executes 50 independent random seeds per population scale.
"""

import os
import sys
import numpy as np
import pandas as pd
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from offchain_engine.config import ADGSystemConfig
from offchain_engine.discrete_event_simulator import DiscreteEventSimulator


def run_scalability_suite(
    node_scales=[16, 64, 256, 1024, 4096],
    monte_carlo_runs=50,
    epochs_per_run=100,
    output_dir="paper_outputs/csv_datasets"
):
    os.makedirs(output_dir, exist_ok=True)
    results = []

    print(f"[*] Starting Monte Carlo Scalability Benchmark ({monte_carlo_runs} seeds per scale)...")

    for n in node_scales:
        print(f"\n---> Benchmarking Population Scale N = {n} nodes")
        scale_metrics = {
            "tps": [],
            "latency": [],
            "t_adapt": [],
            "min_de": [],
            "decay_rate_c": []
        }

        for seed in range(1, monte_carlo_runs + 1):
            cfg = ADGSystemConfig(random_seed=seed * 1000 + n, default_node_count=n)
            sim = DiscreteEventSimulator(node_count=n, total_epochs=epochs_per_run, config=cfg)
            
            # Run simulation with shock injected between epochs 40 and 60
            sim_output = sim.run_simulation(shock_epoch=40, shock_intensity=0.95)

            gp_hist = sim_output["governance_pressure"]
            de_hist = sim_output["decentralization_entropy"]
            tps_hist = sim_output["tps"]
            lat_hist = sim_output["latency_ms"]

            # Calculate Adaptation Time T_adapt (epochs to return to G_p < 0.35 after shock)
            shock_end = 60
            stabilized_epochs = np.where(gp_hist[shock_end:] < 0.35)[0]
            t_adapt = float(stabilized_epochs[0]) if len(stabilized_epochs) > 0 else float(epochs_per_run - shock_end)

            # Estimate Lyapunov dissipation constant c
            c_decay = sim.lyapunov.verify_dissipation_rate()

            scale_metrics["tps"].append(np.mean(tps_hist))
            scale_metrics["latency"].append(np.percentile(lat_hist, 99)) # 99th percentile
            scale_metrics["t_adapt"].append(t_adapt)
            scale_metrics["min_de"].append(np.min(de_hist))
            scale_metrics["decay_rate_c"].append(c_decay)

        # Aggregate statistical distributions
        mean_tps = np.mean(scale_metrics["tps"])
        std_tps = np.std(scale_metrics["tps"])
        mean_lat = np.mean(scale_metrics["latency"])
        std_lat = np.std(scale_metrics["latency"])
        mean_adapt = np.mean(scale_metrics["t_adapt"])
        std_adapt = np.std(scale_metrics["t_adapt"])
        mean_de = np.mean(scale_metrics["min_de"])
        mean_c = np.mean(scale_metrics["decay_rate_c"])

        print(f"     N={n} | TPS: {mean_tps:.1f} ± {std_tps:.1f} | 99th Latency: {mean_lat:.2f} ms | T_adapt: {mean_adapt:.2f} epochs | Min DE: {mean_de:.4f}")

        results.append({
            "Node_Count_N": n,
            "TPS_Mean": mean_tps,
            "TPS_Std": std_tps,
            "Latency_99th_Mean_ms": mean_lat,
            "Latency_99th_Std_ms": std_lat,
            "T_adapt_Mean_epochs": mean_adapt,
            "T_adapt_Std_epochs": std_adapt,
            "Min_DE_Mean": mean_de,
            "Lyapunov_Decay_c": mean_c
        })

    df = pd.DataFrame(results)
    out_path = os.path.join(output_dir, "monte_carlo_scalability_results.csv")
    df.to_csv(out_path, index=False)
    print(f"\n[+] Scalability benchmark successfully logged to: {out_path}")
    return df


if __name__ == "__main__":
    run_scalability_suite()