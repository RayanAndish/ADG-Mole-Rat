"""
Master Publication Artifacts Generator (Path-Safe & Regex Cleaned)
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 10,
    "axes.labelsize": 11,
    "axes.titlesize": 11,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "figure.titlesize": 12,
    "figure.dpi": 300,
    "lines.linewidth": 1.5,
    "grid.alpha": 0.3,
    "grid.linestyle": "--"
})


def generate_latex_tables(
    csv_dir=os.path.join(PROJECT_ROOT, "paper_outputs", "csv_datasets"),
    tables_dir=os.path.join(PROJECT_ROOT, "paper_outputs", "tables")
):
    os.makedirs(tables_dir, exist_ok=True)
    print("[*] Generating Camera-Ready LaTeX Tables...")

    # Table 1: Scalability Performance Table
    sc_file = os.path.join(csv_dir, "monte_carlo_scalability_results.csv")
    if os.path.exists(sc_file):
        sc_df = pd.read_csv(sc_file)
        with open(os.path.join(tables_dir, "table_performance_metrics.tex"), "w") as f:
            f.write("% ==============================================================================\n")
            f.write("% TABLE: Scalability & Performance Metrics across Population Scales (N)\n")
            f.write("% ==============================================================================\n")
            f.write("\\begin{table*}[t]\n\\centering\n\\small\n")
            f.write("\\caption{Monte Carlo Scalability Evaluation across Independent Runs per Scale.}\n")
            f.write("\\label{tab:performance_metrics}\n")
            f.write("\\begin{tabular}{rccccc}\n\\hline\\hline\n")
            f.write("Population ($N$) & Throughput (TPS) & 99th Latency (ms) & $T_{adapt}$ (Epochs) & Min $DE(t)$ & Decay Rate ($c$) \\\\ \\hline\n")
            for _, row in sc_df.iterrows():
                f.write(f"{int(row['Node_Count_N'])} & ${row['TPS_Mean']:.1f} \\pm {row['TPS_Std']:.1f}$ & "
                        f"${row['Latency_99th_Mean_ms']:.2f} \\pm {row['Latency_99th_Std_ms']:.2f}$ & "
                        f"${row['T_adapt_Mean_epochs']:.2f} \\pm {row['T_adapt_Std_epochs']:.2f}$ & "
                        f"${row['Min_DE_Mean']:.4f}$ & ${row['Lyapunov_Decay_c']:.4f}$ \\\\\n")
            f.write("\\hline\\hline\n\\end{tabular}\n\\end{table*}\n")

    # Table 2: Gas Comparison Table
    gas_file = os.path.join(csv_dir, "evm_gas_benchmarks.csv")
    if os.path.exists(gas_file):
        gas_df = pd.read_csv(gas_file)
        with open(os.path.join(tables_dir, "table_gas_comparison.tex"), "w") as f:
            f.write("\\begin{table}[h]\n\\centering\n\\small\n")
            f.write("\\caption{On-Chain EVM Gas Consumption Benchmarking (in Gas Units).}\n")
            f.write("\\label{tab:gas_comparison}\n")
            f.write("\\begin{tabular}{rcccc}\n\\hline\\hline\n")
            f.write("Committee ($m$) & ADG Epoch Advance & ADG Succession & PBFT View-Change & Flat DAO Voting \\\\ \\hline\n")
            for _, row in gas_df.iterrows():
                f.write(f"{int(row['Committee_Size_m'])} & {int(row['ADG_Epoch_Advance_Gas']):,} & "
                        f"{int(row['ADG_ZeroFork_Succession_Gas']):,} & {int(row['PBFT_ViewChange_Gas']):,} & "
                        f"{int(row['FlatDAO_VoteCasting_Gas']):,} \\\\\n")
            f.write("\\hline\\hline\n\\end{tabular}\n\\end{table}\n")

    print("[+] LaTeX tables successfully generated in:", tables_dir)


def generate_publication_figures(
    csv_dir=os.path.join(PROJECT_ROOT, "paper_outputs", "csv_datasets"),
    fig_dir=os.path.join(PROJECT_ROOT, "paper_outputs", "figures")
):
    os.makedirs(fig_dir, exist_ok=True)
    print("[*] Rendering High-Resolution Vector Figures (.pdf / .png)...")

    # Figure 1: Byzantine Resilience
    byz_file = os.path.join(csv_dir, "byzantine_resilience_results.csv")
    if os.path.exists(byz_file):
        byz_df = pd.read_csv(byz_file)
        plt.figure(figsize=(6.5, 4.0))
        plt.plot(byz_df["Byzantine_Fraction_f"] * 100, byz_df["ADG_P_Capture"], "o-", color="#1f77b4", label="ADG (Ours) $P_{cap}$", lw=2)
        plt.plot(byz_df["Byzantine_Fraction_f"] * 100, byz_df["FlatDAO_P_Capture"], "s--", color="#d62728", label="Flat DAO Voting $P_{cap}$", lw=1.5)
        plt.axvline(x=33.3, color="black", linestyle=":", label=r"Theoretical BFT Bound ($f=33.3\%$)")
        plt.xlabel("Byzantine Adversary Fraction $f$ (%)")
        plt.ylabel(r"Governance Capture Probability $P(Capture)$")
        plt.title("Governance Capture Resilience under Adaptive Adversary")
        plt.legend(loc="upper left")
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(os.path.join(fig_dir, "fig_byzantine_resilience.pdf"))
        plt.savefig(os.path.join(fig_dir, "fig_byzantine_resilience.png"))
        plt.close()

    # Figure 2: Gas Scaling Comparison
    gas_file = os.path.join(csv_dir, "evm_gas_benchmarks.csv")
    if os.path.exists(gas_file):
        gas_df = pd.read_csv(gas_file)
        plt.figure(figsize=(6.5, 4.0))
        plt.plot(gas_df["Committee_Size_m"], gas_df["ADG_Epoch_Advance_Gas"], "o-", color="#2ca02c", label="ADG Epoch Advance", lw=2)
        plt.plot(gas_df["Committee_Size_m"], gas_df["ADG_ZeroFork_Succession_Gas"], "^-", color="#17becf", label="ADG Zero-Fork Handover", lw=2)
        plt.plot(gas_df["Committee_Size_m"], gas_df["PBFT_ViewChange_Gas"], "s--", color="#d62728", label=r"PBFT View-Change $\mathcal{O}(m^2)$", lw=1.5)
        plt.plot(gas_df["Committee_Size_m"], gas_df["FlatDAO_VoteCasting_Gas"], "x--", color="#ff7f0e", label="Flat DAO Voting", lw=1.5)
        plt.xlabel("Committee Size ($m$)")
        plt.ylabel("EVM Gas Consumption (Gas Units)")
        plt.yscale("log")
        plt.title("EVM Gas Overhead Scaling Comparison")
        plt.legend(loc="upper left")
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(os.path.join(fig_dir, "fig_gas_comparison.pdf"))
        plt.savefig(os.path.join(fig_dir, "fig_gas_comparison.png"))
        plt.close()

    # Figure 3: Global Sobol Sensitivity
    sobol_file = os.path.join(csv_dir, "sobol_sensitivity_results.csv")
    if os.path.exists(sobol_file):
        sobol_df = pd.read_csv(sobol_file)
        plt.figure(figsize=(7.0, 4.0))
        x_indices = np.arange(len(sobol_df))
        bar_width = 0.35
        plt.bar(x_indices - bar_width/2, sobol_df["First_Order_S1"], width=bar_width, label="First-Order Index ($S_1$)", color="#1f77b4")
        plt.bar(x_indices + bar_width/2, sobol_df["Total_Order_ST"], width=bar_width, label="Total-Order Index ($S_T$)", color="#aec7e8")
        plt.xticks(x_indices, sobol_df["Parameter"], rotation=25)
        plt.xlabel("Governance Parameter")
        plt.ylabel("Sobol Sensitivity Index")
        plt.title("Global Sobol Sensitivity Variance Decomposition")
        plt.legend(loc="upper right")
        plt.grid(True, axis="y")
        plt.tight_layout()
        plt.savefig(os.path.join(fig_dir, "fig_sobol_sensitivity.pdf"))
        plt.savefig(os.path.join(fig_dir, "fig_sobol_sensitivity.png"))
        plt.close()

    print("[+] Publication vector figures generated in:", fig_dir)


if __name__ == "__main__":
    generate_latex_tables()
    generate_publication_figures()