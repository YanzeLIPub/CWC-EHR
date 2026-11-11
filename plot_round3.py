#!/usr/bin/env python3
"""Draw the two validation figures from their aggregate CSV inputs."""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import StrMethodFormatter
import pandas as pd


def bars(categories, counts, x_label, y_label, path):
    fig, ax = plt.subplots(figsize=(6.2, 3.4), layout="constrained")
    marks = ax.bar(categories, counts, width=0.66, color="#2E607D")
    ax.bar_label(marks, labels=[f"{count:,}" for count in counts], padding=3, fontsize=9)
    ax.set_xlabel(x_label, labelpad=7)
    ax.set_ylabel(y_label, labelpad=7)
    ax.set_ylim(0, max(counts) * 1.17)
    ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.7)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(path, metadata={"CreationDate": None, "ModDate": None})
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    matplotlib.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "pdf.fonttype": 42})
    admissions = pd.read_csv(args.analysis_dir / "figure1_source.csv")
    bars(
        admissions["shifted_admission_year"].astype(str),
        admissions["encounters"],
        "Shifted admission year",
        "Encounter records",
        args.output_dir / "02_Figure1.pdf",
    )
    lab = pd.read_csv(args.analysis_dir / "figure2_source.csv")
    bars(
        lab["nonempty_percent_bin"],
        lab["laboratory_fields"],
        "Laboratory rows with a nonempty value (%)",
        "Laboratory variables",
        args.output_dir / "03_Figure2.pdf",
    )


if __name__ == "__main__":
    main()
