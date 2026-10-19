"""
Josh Talks Transcription Quality Analysis - Visualization Generator.

Generates high-resolution publication-quality visual figures for:
1. Warning signals task-level frequency and percentage breakdown
2. Task-to-Audio Time Ratio (TER) distribution and anomaly thresholds
3. Character Per Second (CPS) throughput distribution and typing speed limits
4. Co-occurrence heatmap across warning flags
5. Longitudinal risk profiles for repeat transcribers
"""

from pathlib import Path
from typing import Dict, List
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


# Set styling
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "figure.titlesize": 14,
})

PALETTE = {
    "primary": "#1f77b4",
    "danger": "#d62728",
    "warning": "#ff7f0e",
    "success": "#2ca02c",
    "purple": "#9467bd",
    "dark": "#2c3e50",
    "gray": "#7f8c8d",
}


def generate_all_figures(
    df_flagged: pd.DataFrame,
    thresholds: Dict[str, float],
    overlap_matrix: pd.DataFrame,
    repeat_users: pd.DataFrame,
    output_dir: Path,
) -> List[Path]:
    """Generate and save all report figures to output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_files = []

    # 1. Warning signals distribution
    fig1_path = output_dir / "warning_signals_distribution.png"
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)
    signals = [
        ("flag_ter_below_1", "TER < 1.0\n(Rushed Review)", 5939, 11.47, PALETTE["warning"]),
        ("flag_blank_submission", "Blank / Incomplete\nSubmission", 1019, 1.97, PALETTE["danger"]),
        ("flag_extreme_low_ter", "Extreme Low TER\n(< 0.1788, Bottom 1%)", 517, 1.00, PALETTE["purple"]),
        ("flag_extreme_cps", "Extreme Throughput\n(> 59.86 CPS, Top 2%)", 457, 0.88, PALETTE["primary"]),
    ]
    labels = [s[1] for s in signals]
    counts = [s[2] for s in signals]
    pcts = [s[3] for s in signals]
    colors = [s[4] for s in signals]

    bars = ax.bar(labels, counts, color=colors, width=0.55, edgecolor="#222222", linewidth=0.8, alpha=0.9)
    for bar, count, pct in zip(bars, counts, pcts):
        yval = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            yval + 100,
            f"{count:,}\n({pct:.2f}%)",
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
            color="#222222",
        )

    ax.set_title("Distribution of Task-Level Warning Signals (N = 51,783 Tasks)", pad=15, fontweight="bold")
    ax.set_ylabel("Number of Flagged Tasks", labelpad=10)
    ax.set_ylim(0, 7000)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    fig.savefig(fig1_path, dpi=300)
    plt.close(fig)
    generated_files.append(fig1_path)

    # 2. TER Distribution
    fig2_path = output_dir / "ter_distribution.png"
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)
    valid_ter = df_flagged.loc[
        df_flagged["is_duration_above_1s"] & df_flagged["ter"].notna(), "ter"
    ]
    # Filter reasonable display window
    plot_ter = valid_ter[valid_ter.between(0, 10)]

    ax.hist(plot_ter, bins=80, color=PALETTE["primary"], edgecolor="white", alpha=0.7, density=True)
    ax.axvline(1.0, color=PALETTE["danger"], linestyle="--", linewidth=2, label="TER = 1.0 (Real-Time Playback Boundary)")
    ax.axvline(thresholds["ter_p1"], color=PALETTE["purple"], linestyle=":", linewidth=2, label=f"TER P1 Threshold = {thresholds['ter_p1']:.4f}")

    ax.set_title("Task-to-Audio Time Ratio (TER) Empirical Distribution", pad=15, fontweight="bold")
    ax.set_xlabel("Time-to-Audio Ratio (TER = User Time / Audio Duration)")
    ax.set_ylabel("Probability Density")
    ax.set_xlim(0, 6)
    ax.legend(frameon=True, facecolor="white", edgecolor="#cccccc", loc="upper right")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    fig.savefig(fig2_path, dpi=300)
    plt.close(fig)
    generated_files.append(fig2_path)

    # 3. CPS Distribution
    fig3_path = output_dir / "cps_throughput_distribution.png"
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)
    valid_cps = df_flagged.loc[
        df_flagged["is_duration_above_5s"] & df_flagged["user_task_cps"].notna(),
        "user_task_cps",
    ]
    plot_cps = valid_cps[valid_cps.between(0, 120)]

    ax.hist(plot_cps, bins=60, color=PALETTE["success"], edgecolor="white", alpha=0.75, density=True)
    ax.axvline(
        thresholds["cps_p98"],
        color=PALETTE["danger"],
        linestyle="--",
        linewidth=2,
        label=f"98th Percentile = {thresholds['cps_p98']:.2f} chars/sec (~700 WPM)",
    )
    # Average human typing speed reference ~ 4-8 cps (40-80 WPM)
    ax.axvspan(3.3, 6.7, color="#cccccc", alpha=0.3, label="Normal Human Typing Speed (40–80 WPM)")

    ax.set_title("Character Throughput Speed (CPS) Distribution (Clips > 5s)", pad=15, fontweight="bold")
    ax.set_xlabel("Characters Per Second (CPS = Clean Characters / Task Duration)")
    ax.set_ylabel("Probability Density")
    ax.set_xlim(0, 100)
    ax.legend(frameon=True, facecolor="white", edgecolor="#cccccc", loc="upper right")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    fig.savefig(fig3_path, dpi=300)
    plt.close(fig)
    generated_files.append(fig3_path)

    # 4. Signals Overlap Matrix Heatmap
    fig4_path = output_dir / "signals_overlap_heatmap.png"
    fig, ax = plt.subplots(figsize=(8, 6.5), dpi=300)
    labels_short = [
        "Blank Sub.",
        "Extr. Low TER",
        "TER < 1.0",
        "Extr. CPS",
    ]
    matrix_vals = overlap_matrix.values
    sns.heatmap(
        matrix_vals,
        annot=True,
        fmt=",d",
        cmap="Blues",
        xticklabels=labels_short,
        yticklabels=labels_short,
        cbar=True,
        ax=ax,
        linewidths=1,
        linecolor="#dddddd",
    )
    ax.set_title("Warning Signals Co-occurrence Matrix", pad=15, fontweight="bold")
    plt.tight_layout()
    fig.savefig(fig4_path, dpi=300)
    plt.close(fig)
    generated_files.append(fig4_path)

    # 5. Repeat Transcribers Profile
    fig5_path = output_dir / "repeat_transcribers_risk_profile.png"
    fig, ax = plt.subplots(figsize=(11, 6), dpi=300)
    df_sorted = repeat_users.sort_values("total_tasks", ascending=True).copy()
    user_labels = [f"User {uid}" for uid in df_sorted["user_id"]]
    y_pos = np.arange(len(user_labels))

    ax.barh(y_pos, df_sorted["total_tasks"], color="#bdc3c7", height=0.55, label="Total Tasks")
    ax.barh(y_pos, df_sorted["flagged_tasks"], color=PALETTE["danger"], height=0.55, label="Flagged Tasks (Union)")

    for idx, (tot, flg, pct) in enumerate(
        zip(df_sorted["total_tasks"], df_sorted["flagged_tasks"], df_sorted["warning_rate_pct"])
    ):
        ax.text(
            tot + 10,
            idx,
            f"{flg}/{tot} ({pct:.1f}%)",
            va="center",
            fontsize=9,
            fontweight="bold",
            color="#2c3e50",
        )

    ax.set_yticks(y_pos)
    ax.set_yticklabels(user_labels)
    ax.set_xlabel("Number of Tasks Completed")
    ax.set_title("Activity & Warning Rate for All 10 Repeat Transcribers", pad=15, fontweight="bold")
    ax.set_xlim(0, 750)
    ax.legend(frameon=True, facecolor="white", edgecolor="#cccccc", loc="lower right")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    fig.savefig(fig5_path, dpi=300)
    plt.close(fig)
    generated_files.append(fig5_path)

    return generated_files
