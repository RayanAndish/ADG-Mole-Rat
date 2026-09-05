"""
Multi-Scale Monte Carlo Scalability & Convergence Benchmark (ADG Tier 1)
Generates:
1. Table 7: Variance decay across horizons T in [50, 100, 1000, 5000, 20000, 100000] (N = 128).
2. Table 8: Horizontal scalability across validator sizes N in [16, 64, 256, 1024, 4096].
3. Figure 13: Publication-grade convergence plot (Strictly NO plot title, dual y-axis, clean layout).
Exports pure CSV outputs with zero LaTeX dependencies and dedicated summary files for large horizons.
"""

import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from offchain_engine.config import ADGSystemConfig
from offchain_engine.discrete_event_simulator import DiscreteEventSimulator


def run_horizon_convergence_suite(
    epoch_scales=[50, 100, 1000, 5000, 20000, 100000],
    node_count=128,
    output_dir=os.path.join(PROJECT_ROOT, "paper_outputs", "csv_datasets")
) -> pd.DataFrame:
    """
    Executes Multi-Scale Monte Carlo evaluation across operational horizons (Table 7).
    """
    os.makedirs(output_dir, exist_ok=True)
    summary_results = []

    print("\n" + "=" * 70)
    print(f"[*] SUITE 1: Executing Multi-Horizon Variance Decay Suite (Table 7)")
    print(f"    Fixed Population N = {node_count} | Horizons: {epoch_scales}")
    print("=" * 70)

    for total_epochs in epoch_scales:
        print(f"\n[+] Running Horizon: {total_epochs:,} Epochs...")

        cfg = ADGSystemConfig(random_seed=42 + total_epochs, default_node_count=node_count)
        sim = DiscreteEventSimulator(node_count=node_count, total_epochs=total_epochs, config=cfg)

        shock_start = max(5, total_epochs // 4)
        sim_out = sim.run_simulation(
            shock_start_epoch=shock_start,
            shock_duration=max(10, min(50, total_epochs // 10)),
            shock_risk=0.90,
            shock_workload=0.95
        )

        epochs_arr = sim_out["epochs"]
        gp_arr = sim_out["governance_pressure"]
        de_arr = sim_out["decentralization_entropy"]
        top_f_arr = sim_out["top_f_coalition_share"]
        gini_arr = sim_out["gini_coefficient"]
        energy_arr = sim_out["lyapunov_energy"]
        tps_arr = sim_out["tps"]
        lat_arr = sim_out["latency_ms"]

        # 1. Export Raw Trace CSV
        trace_df = pd.DataFrame({
            "Epoch": epochs_arr,
            "Governance_Pressure_Gp": np.round(gp_arr, 6),
            "Decentralization_Entropy_DE": np.round(de_arr, 6),
            "Top_f_Coalition_Share": np.round(top_f_arr, 6),
            "Gini_Coefficient": np.round(gini_arr, 8),
            "Lyapunov_Energy_V": np.round(energy_arr, 8),
            "TPS": np.round(tps_arr, 2),
            "Latency_ms": np.round(lat_arr, 3)
        })
        trace_csv_path = os.path.join(output_dir, f"monte_carlo_results_N_{total_epochs}.csv")
        trace_df.to_csv(trace_csv_path, index=False)

        # 2. For massive traces (20k and 100k), generate an aggregated Summary CSV
        if total_epochs >= 20000:
            summary_trace = pd.DataFrame({
                "Metric": ["Throughput_TPS", "Finality_Latency_ms", "Decentralization_Entropy", "Gini_Index", "Lyapunov_Energy"],
                "Mean": [np.mean(tps_arr), np.mean(lat_arr), np.mean(de_arr), np.mean(gini_arr), np.mean(energy_arr)],
                "Std": [np.std(tps_arr), np.std(lat_arr), np.std(de_arr), np.std(gini_arr), np.std(energy_arr)],
                "Variance": [np.var(tps_arr), np.var(lat_arr), np.var(de_arr), np.var(gini_arr), np.var(energy_arr)],
                "Min": [np.min(tps_arr), np.min(lat_arr), np.min(de_arr), np.min(gini_arr), np.min(energy_arr)],
                "Max": [np.max(tps_arr), np.max(lat_arr), np.max(de_arr), np.max(gini_arr), np.max(energy_arr)]
            })
            summary_trace_path = os.path.join(output_dir, f"monte_carlo_results_N_{total_epochs}_summary.csv")
            summary_trace.to_csv(summary_trace_path, index=False)

        # 3. Compile Master Moments for Table 7
        stats_row = {
            "Execution_Scale_T": total_epochs,
            "Mean_Throughput_TPS": round(float(np.mean(tps_arr)), 1),
            "Throughput_Std": round(float(np.std(tps_arr)), 1),
            "Throughput_Variance": float(f"{np.var(tps_arr):.2e}"),
            "Finality_Latency_Mean_ms": round(float(np.mean(lat_arr)), 2),
            "Latency_Std_ms": round(float(np.std(lat_arr)), 2),
            "Latency_Variance": round(float(np.var(lat_arr)), 2),
            "Mean_Gini_Index": float(f"{np.mean(gini_arr):.6e}"),
            "Min_Preserved_DE": round(float(np.min(de_arr)), 4),
            "Final_Lyapunov_Energy": float(f"{energy_arr[-1]:.2e}")
        }
        summary_results.append(stats_row)
        print(f"    --> TPS: {stats_row['Mean_Throughput_TPS']} ± {stats_row['Throughput_Std']} | "
              f"Latency: {stats_row['Finality_Latency_Mean_ms']} ms | "
              f"Gini: {stats_row['Mean_Gini_Index']} | Min DE: {stats_row['Min_Preserved_DE']}")

    df_table7 = pd.DataFrame(summary_results)
    table7_path = os.path.join(output_dir, "monte_carlo_scale_convergence_summary.csv")
    df_table7.to_csv(table7_path, index=False)
    print(f"\n[✔] Table 7 Master CSV exported to:\n    --> {table7_path}")
    return df_table7


def run_population_scale_suite(
    populations=[16, 64, 256, 1024, 4096],
    total_epochs=100,
    runs_per_scale=30,
    output_dir=os.path.join(PROJECT_ROOT, "paper_outputs", "csv_datasets")
) -> pd.DataFrame:
    """
    Executes Horizontal Validator Population Scale-Up (Table 8).
    Evaluates N from 16 to 4096 across independent Monte Carlo trials.
    """
    os.makedirs(output_dir, exist_ok=True)
    table8_rows = []

    print("\n" + "=" * 70)
    print(f"[*] SUITE 2: Executing Population Scale-Up Suite (Table 8)")
    print(f"    Populations N in {populations} | {runs_per_scale} Monte Carlo Seeds per Scale")
    print("=" * 70)

    for n_nodes in populations:
        print(f"\n[+] Benchmarking Population Scale N = {n_nodes:,} nodes...")
        tps_runs = []
        p99_latency_runs = []
        t_adapt_runs = []
        min_de_runs = []
        c_rate_runs = []

        for seed in range(runs_per_scale):
            cfg = ADGSystemConfig(random_seed=1000 + seed, default_node_count=n_nodes)
            sim = DiscreteEventSimulator(node_count=n_nodes, total_epochs=total_epochs, config=cfg)

            # Standardized shock between epochs 30 and 50 (Section 6.2)
            out = sim.run_simulation(
                shock_start_epoch=30,
                shock_duration=20,
                shock_risk=0.90,
                shock_workload=0.95
            )

            gp = out["governance_pressure"]
            tps_runs.append(np.mean(out["tps"]))
            p99_latency_runs.append(np.percentile(out["latency_ms"], 99))
            min_de_runs.append(np.min(out["decentralization_entropy"]))
            c_rate_runs.append(out["lyapunov_dissipation_c"])

            # Recovery time: epochs from shock end (epoch 50) until G_p relaxes < 0.35
            post_shock_gp = gp[50:]
            rec_indices = np.where(post_shock_gp < 0.35)[0]
            t_rec = float(rec_indices[0]) if len(rec_indices) > 0 else 1.0
            t_adapt_runs.append(max(1.0, t_rec))

        row = {
            "Population_N": n_nodes,
            "Mean_Throughput_TPS": round(float(np.mean(tps_runs)), 1),
            "Throughput_Std": round(float(np.std(tps_runs)), 1),
            "99th_Percentile_Latency_ms": round(float(np.mean(p99_latency_runs)), 2),
            "Latency_p99_Std": round(float(np.std(p99_latency_runs)), 2),
            "Adaptation_Time_T_adapt_Epochs": round(float(np.mean(t_adapt_runs)), 2),
            "Adaptation_Time_Std": round(float(np.std(t_adapt_runs)), 2),
            "Minimum_Preserved_DE": round(float(np.mean(min_de_runs)), 4),
            "Lyapunov_Dissipation_c": round(float(np.mean(c_rate_runs)), 4)
        }
        table8_rows.append(row)
        print(f"    --> N={n_nodes:,} | TPS: {row['Mean_Throughput_TPS']:,} ± {row['Throughput_Std']} | "
              f"p99 Latency: {row['99th_Percentile_Latency_ms']} ms | c: {row['Lyapunov_Dissipation_c']}")

    df_table8 = pd.DataFrame(table8_rows)
    table8_path = os.path.join(output_dir, "monte_carlo_scalability_results.csv")
    df_table8.to_csv(table8_path, index=False)
    print(f"\n[✔] Table 8 Master CSV exported to:\n    --> {table8_path}")
    return df_table8


def plot_figure_13(
    df_table7: pd.DataFrame,
    output_dir=os.path.join(PROJECT_ROOT, "paper_outputs", "figures")
):
    """
    Renders Figure 13: Empirical variance decay and decentralization stability across horizons.
    Strictly adheres to Q1 publication guidelines:
    - NO plot title.
    - Dual y-axis with non-overlapping, high-clarity legend.
    - Logarithmic x-axis for scale horizons.
    """
    os.makedirs(output_dir, exist_ok=True)

    fig, ax1 = plt.subplots(figsize=(8, 4.8), dpi=300)

    horizons = df_table7["Execution_Scale_T"].values
    tps_mean = df_table7["Mean_Throughput_TPS"].values
    gini_mean = df_table7["Mean_Gini_Index"].values

    # Left Axis: Throughput (TPS)
    color_tps = "#1f77b4"
    ax1.set_xscale("log")
    line1 = ax1.plot(
        horizons, tps_mean,
        color=color_tps, marker="o", linewidth=2.0, markersize=6,
        label="Throughput (Transactions Per Second)"
    )
    ax1.set_xlabel("Monte Carlo Execution Scale (Total Epochs $T$)", fontsize=11, fontweight="bold", labelpad=8)
    ax1.set_ylabel("Throughput (Transactions Per Second)", color=color_tps, fontsize=11, fontweight="bold")
    ax1.tick_params(axis="y", labelcolor=color_tps, labelsize=9)
    ax1.tick_params(axis="x", labelsize=9)
    ax1.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.6)

    # Right Axis: Gini Coefficient
    ax2 = ax1.twinx()
    color_gini = "#d62728"
    line2 = ax2.plot(
        horizons, gini_mean,
        color=color_gini, marker="s", linestyle="--", linewidth=2.0, markersize=6,
        label="Gini Coefficient of Authority Concentration"
    )
    ax2.set_ylabel("Gini Coefficient of Authority Concentration", color=color_gini, fontsize=11, fontweight="bold")
    ax2.tick_params(axis="y", labelcolor=color_gini, labelsize=9)
    ax2.set_ylim(-0.02, 0.45)

    # Combine legends into a single box positioned safely at top-right without covering data points
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc="upper right", frameon=True, framealpha=0.9, fontsize=9)

    plt.tight_layout()

    # Save vector PDF and high-res PNG
    pdf_path = os.path.join(output_dir, "figure13_variance_decay.pdf")
    png_path = os.path.join(output_dir, "figure13_variance_decay.png")
    plt.savefig(pdf_path, bbox_inches="tight", dpi=300)
    plt.savefig(png_path, bbox_inches="tight", dpi=300)
    plt.close()

    print(f"\n[✔] Figure 13 successfully generated (NO title, strict layout):\n    --> {pdf_path}\n    --> {png_path}")


def main():
    csv_dir = os.path.join(PROJECT_ROOT, "paper_outputs", "csv_datasets")
    fig_dir = os.path.join(PROJECT_ROOT, "paper_outputs", "figures")

    # 1. Execute Table 7 Suite & Plot Figure 13
    df_table7 = run_horizon_convergence_suite(output_dir=csv_dir)
    plot_figure_13(df_table7, output_dir=fig_dir)

    # 2. Execute Table 8 Suite
    run_population_scale_suite(output_dir=csv_dir)


if __name__ == "__main__":
    main()