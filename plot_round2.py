#!/usr/bin/env python3
"""Create the two reviewer-requested revised manuscript figures."""

import argparse
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
ANALYSIS = ROOT / "analysis_outputs"
OUT = ROOT / "outputs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

mpl.rcParams.update({
    "font.family": "Arial",
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})


def save(fig: plt.Figure, out: Path, stem: str) -> None:
    fig.savefig(out / f"{stem}.pdf", bbox_inches="tight")
    fig.savefig(out / f"{stem}.png", dpi=400, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def figure1(analysis: Path, out: Path) -> None:
    df = pd.read_csv(analysis / "annual_encounters_by_sex_code.csv")
    df["性别"] = df["性别"].map({1: "Male", 2: "Female"})
    years = sorted(df["year"].unique())
    male = df[df["性别"] == "Male"].set_index("year")["encounters"].reindex(years, fill_value=0)
    female = df[df["性别"] == "Female"].set_index("year")["encounters"].reindex(years, fill_value=0)

    fig, ax = plt.subplots(figsize=(7.15, 3.55))
    x = np.arange(len(years))
    width = 0.36
    bars1 = ax.bar(x - width / 2, male, width, label="Male", color="#2F6B9A")
    bars2 = ax.bar(x + width / 2, female, width, label="Female", color="#D17B5F")
    ax.set_xticks(x, years)
    ax.set_xlabel("Admission year")
    ax.set_ylabel("Number of inpatient encounters")
    ax.set_title("Inpatient encounters by admission year and recorded sex")
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.6, alpha=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, ncol=2, loc="upper left")
    ax.yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f}"))
    ax.bar_label(bars1, labels=[f"{int(value):,}" for value in male], padding=2, fontsize=7, rotation=90)
    ax.bar_label(bars2, labels=[f"{int(value):,}" for value in female], padding=2, fontsize=7, rotation=90)
    ax.set_ylim(0, max(max(male), max(female)) * 1.18)
    fig.tight_layout()
    save(fig, out, "Figure1_revised")


def figure2(analysis: Path, out: Path) -> None:
    df = pd.read_csv(analysis / "tumor_procedure_summary.csv")
    tumor_order = ["Lung", "Colorectal", "Breast", "Esophageal", "Gastric", "Liver"]
    procedure_order = [
        "Chemotherapy",
        "Radiotherapy",
        "Targeted therapy",
        "Immunotherapy",
        "Surgical resection",
        "Biopsy/puncture",
        "Interventional therapy",
        "Endoscopic/laparoscopic procedure",
    ]
    palette = {
        "Lung": "#1B5E8A",
        "Colorectal": "#D95F59",
        "Breast": "#8C6BB1",
        "Esophageal": "#2A9D8F",
        "Gastric": "#E9A23B",
        "Liver": "#6A994E",
    }
    offsets = np.linspace(-0.30, 0.30, len(tumor_order))
    ybase = np.arange(len(procedure_order))

    fig, ax = plt.subplots(figsize=(7.15, 5.35))
    for offset, tumor in zip(offsets, tumor_order):
        sub = (
            df[df["tumor_category"] == tumor]
            .set_index("procedure_category")
            .reindex(procedure_order)
        )
        ax.scatter(
            sub["percent"],
            ybase + offset,
            s=30,
            color=palette[tumor],
            label=f"{tumor} (n={int(sub['tumor_patients'].iloc[0]):,})",
            edgecolor="white",
            linewidth=0.4,
            zorder=3,
        )
    ax.set_yticks(ybase, procedure_order)
    ax.invert_yaxis()
    ax.set_xlabel("Patients with recorded procedure (%)")
    ax.set_title("Recorded procedure categories across the six most frequent cancer groups")
    ax.grid(axis="x", color="#D9D9D9", linewidth=0.6, alpha=0.8)
    ax.set_axisbelow(True)
    ax.set_xlim(0, 70)
    ax.legend(
        frameon=False,
        ncol=3,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.13),
        columnspacing=0.9,
        handletextpad=0.35,
    )
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    save(fig, out, "Figure2_revised")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    figure1(args.analysis_dir, args.output_dir)
    figure2(args.analysis_dir, args.output_dir)
