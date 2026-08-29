"""
==============================================================================
ADG Framework - 50 Live Sepolia Mined Transactions Plotter
Generates publication-quality 2-panel figure:
Panel A: Block Inclusion Latency (Seconds) vs. Ethereum 12s Slot Baseline
Panel B: EIP-1559 Dynamic Gas Price (Gwei) & On-Chain Gas Consumption
==============================================================================
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Safe project root resolution
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Configure Matplotlib for strict IEEE Academic Formatting
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
    "lines.linewidth": 1.4,
    "grid.alpha": 0.3,
    "grid.linestyle": "--"
})


def plot_sepolia_50_trace(
    csv_file=os.path.join(PROJECT_ROOT, "paper_outputs", "csv_datasets", "sepolia_real_mined_transactions_ledger.csv"),
    fig_dir=os.path.join(PROJECT_ROOT, "paper_outputs", "figures")
):
    os.makedirs(fig_dir, exist_ok=True)
    if not os.path.exists(csv_file):
        print(f"[!] Sepolia CSV not found: {csv_file}")
        return

    print(f"[*] Parsing 50 Live Sepolia transactions from: {csv_file}")
    df = pd.read_csv(csv_file)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7.2, 5.2), sharex=True)

    tx_idx = df["Transaction_Index"].values
    latency = df["Mined_Latency_Seconds"].values
    gas_price = df["Effective_Gas_Price_Gwei"].values
    block_numbers = df["Block_Number"].values

    # Panel A: Block Inclusion Latency vs Ethereum 12-Second Slot
    ax1.plot(tx_idx, latency, "o-", color="#1f77b4", lw=1.8, markersize=4, label="Mined Inclusion Latency (s)")
    ax1.axhline(y=12.0, color="#d62728", linestyle="--", lw=1.5, label="Ethereum PoS Beacon Slot Time (12.0 s)")
    mean_lat = np.mean(latency)
    ax1.axhline(y=mean_lat, color="#2ca02c", linestyle=":", lw=1.5, label=f"Mean Latency ({mean_lat:.2f} s)")
    ax1.set_ylabel("Inclusion Latency (s)")
    ax1.set_title("Tier 3 Public Testnet: 50 Consecutive Mined Blocks on Ethereum Sepolia")
    ax1.legend(loc="upper right")
    ax1.grid(True)
    ax1.set_ylim(0, max(25.0, np.max(latency) * 1.15))

    # Panel B: Effective Gas Price (EIP-1559 Dynamic Pricing)
    ax2.plot(tx_idx, gas_price, "s-", color="#ff7f0e", lw=1.6, markersize=4, label="EIP-1559 Effective Gas Price (Gwei)")
    ax2.set_xlabel("Mined Transaction Sequence ($1$ to $50$) across Blocks $11566628$ – $11566677$")
    ax2.set_ylabel("Gas Price (Gwei)")
    ax2.set_ylim(bottom=min(gas_price) * 0.85, top=max(gas_price) * 1.15)
    ax2.legend(loc="upper right")
    ax2.grid(True)

    plt.tight_layout()

    pdf_path = os.path.join(fig_dir, "fig_sepolia_50_mined_trace.pdf")
    png_path = os.path.join(fig_dir, "fig_sepolia_50_mined_trace.png")
    plt.savefig(pdf_path)
    plt.savefig(png_path)
    plt.close()

    print(f"[+] 50-Tx Sepolia public testnet visualization saved to:")
    print(f"    --> PDF (Vector): {pdf_path}")
    print(f"    --> PNG (300DPI): {png_path}")


if __name__ == "__main__":
    plot_sepolia_50_trace()