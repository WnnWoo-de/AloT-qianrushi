#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DETAIL_CSV = BASE_DIR / "summary_detailed_runs.csv"
AGG_CSV = BASE_DIR / "summary_aggregated.csv"
OUT_FIG = BASE_DIR / "summary_distribution_plot.png"

scene_order = ["normal_occ", "lio_only", "mixed_all"]
scene_labels = {
    "normal_occ": "Normal Occlusion",
    "lio_only": "Single-Modal Degeneration",
    "mixed_all": "Mixed Degeneration",
}

df = pd.read_csv(DETAIL_CSV)
agg = pd.read_csv(AGG_CSV)

fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))

rng = np.random.default_rng(0)
offset_r1 = -0.12
offset_r2 =  0.12

panels = [
    ("rmse1", "rmse2", "Dual-Robot RMSE [m]"),
    ("max_dev1", "max_dev2", "Max Deviation [m]")
]

for ax, (col1, col2, title) in zip(axes, panels):
    for i, scene in enumerate(scene_order):
        sub = df[df["scene"] == scene]

        x_r1 = np.full(len(sub), i + offset_r1) + rng.normal(0, 0.015, len(sub))
        x_r2 = np.full(len(sub), i + offset_r2) + rng.normal(0, 0.015, len(sub))

        # raw seed points
        ax.scatter(x_r1, sub[col1], alpha=0.35, s=20, marker="o",
                   label="R1 runs" if i == 0 else None)
        ax.scatter(x_r2, sub[col2], alpha=0.35, s=20, marker="s",
                   label="R2 runs" if i == 0 else None)

        # mean points
        mean1 = sub[col1].mean()
        mean2 = sub[col2].mean()
        ax.scatter(i + offset_r1, mean1, s=90, marker="o",
                   edgecolors="black", linewidths=1.0,
                   label="R1 mean" if i == 0 else None)
        ax.scatter(i + offset_r2, mean2, s=90, marker="s",
                   edgecolors="black", linewidths=1.0,
                   label="R2 mean" if i == 0 else None)

    ax.set_xticks(range(len(scene_order)))
    ax.set_xticklabels([scene_labels[s] for s in scene_order], rotation=0)
    ax.set_title(title)
    ax.grid(alpha=0.3)
    ax.set_axisbelow(True)

axes[0].set_ylabel("Error [m]")

# stability annotation: put it above the Max Deviation panel
for i, scene in enumerate(scene_order):
    stab = agg.loc[agg["scene"] == scene, "stability_str"].iloc[0]
    sub = df[df["scene"] == scene]
    y_top = max(sub["max_dev1"].max(), sub["max_dev2"].max())
    axes[1].text(i, y_top * 1.08, stab, ha="center", va="bottom", fontsize=9)

fig.legend(loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 1.03))
fig.suptitle("Current Method (3.2.3): Summary Across Degradation Scenarios", y=1.08)
fig.text(
    0.5, 1.1,
    "Small dots = repeated runs, large dots = mean values, text = stability",
    ha="center", va="center", fontsize=10
)

fig.tight_layout()
fig.savefig(OUT_FIG, dpi=300, bbox_inches="tight")
print(f"Saved to: {OUT_FIG}")