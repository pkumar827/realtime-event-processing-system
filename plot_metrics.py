"""
Generate report/demo graphs from metrics CSVs produced by the scaler.

Each CSV has columns: elapsed_sec, lag, workers, throughput

Usage:
    # Compare a baseline run against an auto-scaling run (the main use):
    python plot_metrics.py metrics/run_..._baseline.csv metrics/run_..._scaler.csv

    # Just plot a single scaler run:
    python plot_metrics.py metrics/run_..._scaler.csv

Outputs PNGs into metrics/graphs/ (or --out-dir):
    1. <ts>_scaling.png       lag over time with worker count overlaid
    2. <ts>_lag_compare.png   lag: without-scaler vs with-scaler (the key graph)
    3. <ts>_thrpt_compare.png throughput: without-scaler vs with-scaler
"""

import os
import sys
import time

import matplotlib
matplotlib.use("Agg")  # no display needed; write files
import matplotlib.pyplot as plt
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
GRAPH_DIR = os.path.join(REPO_ROOT, "metrics", "graphs")


def load(path):
    df = pd.read_csv(path)
    return df


def plot_scaling(scaler_df, out_path):
    """Lag over time with worker count overlaid on a second axis."""
    fig, ax1 = plt.subplots(figsize=(10, 5))

    ax1.plot(scaler_df["elapsed_sec"], scaler_df["lag"],
             color="#c0392b", linewidth=2, label="Lag (events)")
    ax1.set_xlabel("Time (seconds)")
    ax1.set_ylabel("Consumer lag (events)", color="#c0392b")
    ax1.tick_params(axis="y", labelcolor="#c0392b")
    ax1.set_ylim(bottom=0)

    ax2 = ax1.twinx()
    ax2.step(scaler_df["elapsed_sec"], scaler_df["workers"],
             color="#2471a3", linewidth=2, where="post", label="Workers")
    ax2.set_ylabel("Active workers", color="#2471a3")
    ax2.tick_params(axis="y", labelcolor="#2471a3")
    ax2.set_ylim(0, scaler_df["workers"].max() + 1)

    plt.title("Auto-scaling: lag drives worker count")
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print("wrote", out_path)


def plot_lag_compare(baseline_df, scaler_df, out_path):
    """The key graph: lag stays high without scaling, recovers with scaling."""
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(baseline_df["elapsed_sec"], baseline_df["lag"],
            color="#c0392b", linewidth=2, label="Without auto-scaling (1 worker)")
    ax.plot(scaler_df["elapsed_sec"], scaler_df["lag"],
            color="#27ae60", linewidth=2, label="With auto-scaling")
    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("Consumer lag (events)")
    ax.set_ylim(bottom=0)
    ax.set_title("Consumer lag under load: with vs without auto-scaling")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print("wrote", out_path)


def plot_thrpt_compare(baseline_df, scaler_df, out_path):
    """Throughput sustained: scaling keeps up, baseline caps out."""
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(baseline_df["elapsed_sec"], baseline_df["throughput"],
            color="#c0392b", linewidth=1.6, label="Without auto-scaling (1 worker)")
    ax.plot(scaler_df["elapsed_sec"], scaler_df["throughput"],
            color="#27ae60", linewidth=1.6, label="With auto-scaling")
    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("Throughput (events/sec)")
    ax.set_ylim(bottom=0)
    ax.set_title("Processing throughput: with vs without auto-scaling")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print("wrote", out_path)


def main():
    import argparse
    p = argparse.ArgumentParser(description="Plot scaler metrics")
    p.add_argument("csvs", nargs="+",
                   help="one CSV (scaler) or two CSVs (baseline scaler)")
    p.add_argument("--out-dir", default=GRAPH_DIR,
                   help="directory to write PNGs into")
    args = p.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")

    if len(args.csvs) == 1:
        scaler_df = load(args.csvs[0])
        plot_scaling(scaler_df, os.path.join(args.out_dir, f"{ts}_scaling.png"))
    else:
        baseline_df = load(args.csvs[0])
        scaler_df = load(args.csvs[1])
        plot_scaling(scaler_df, os.path.join(args.out_dir, f"{ts}_scaling.png"))
        plot_lag_compare(baseline_df, scaler_df,
                         os.path.join(args.out_dir, f"{ts}_lag_compare.png"))
        plot_thrpt_compare(baseline_df, scaler_df,
                           os.path.join(args.out_dir, f"{ts}_thrpt_compare.png"))

    print("Graphs written to", args.out_dir)


if __name__ == "__main__":
    main()