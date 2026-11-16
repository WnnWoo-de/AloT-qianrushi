#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于 sim2d_mvp_3.2.3.py 生成“小型效果汇总表”。

设计目标：
1. 只汇总当前方案（3.2.3，对应 3.2.1 正式方法的工程重构版）；
2. 只跨“场景”维度，不跨“方法”维度；
3. 默认统计三种场景：
   - normal_occ
   - lio_only
   - mixed_all
4. 对每个场景做多 seed 重复实验，输出：
   - 双机器人 RMSE（R1 / R2）
   - 最大偏差（R1 / R2）
   - 稳定性（valid / total 与百分比）

默认 valid run 判定：
- 求解过程没有异常；
- est1 / est2 不含 NaN / Inf；
- RMSE_R1 < 1.0 m；
- RMSE_R2 < 1.0 m。

默认用法：
python3 make_summary_table_3_2_3.py \
    --src ./sim2d_mvp_3.2.3.py \
    --out-dir ./figs/summary_table_3_2_3

输出内容：
- summary_detailed_runs.csv  : 每个 scene × seed 的逐次结果
- summary_aggregated.csv     : 聚合后的数值表
- summary_table.md           : markdown 版小表
- summary_table.png          : 适合汇报/PPT/论文草稿的图片表格
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import io
import importlib.util
import math
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


DEFAULT_SCENES = ["normal_occ", "lio_only", "mixed_all"]
SCENE_LABELS = {
    "normal_occ": "Normal Occlusion",
    "lio_only": "Single-Modal Degeneration",
    "mixed_all": "Mixed Degeneration",
}


@dataclass
class RunRecord:
    scene: str
    scene_label: str
    seed_index: int
    seed_main: int
    valid: int
    rmse1: float
    rmse2: float
    max_dev1: float
    max_dev2: float
    note: str


@dataclass
class AggregateRecord:
    scene: str
    scene_label: str
    n_valid: int
    n_total: int
    stability_ratio: float
    mean_rmse1: float
    mean_rmse2: float
    mean_max_dev1: float
    mean_max_dev2: float
    rmse_pair_str: str
    max_dev_pair_str: str
    stability_str: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a compact summary table for the current method (3.2.3)")
    parser.add_argument("--src", type=str, default="sim2d_mvp_3.2.3.py", help="Path to sim2d_mvp_3.2.3.py")
    parser.add_argument("--out-dir", type=str, default="figs/summary_table_3_2_3", help="Output directory")
    parser.add_argument("--scenes", nargs="+", default=DEFAULT_SCENES, help="Scenes to evaluate")
    parser.add_argument("--num-seeds", type=int, default=20, help="Number of repeated runs per scene")
    parser.add_argument("--seed-start", type=int, default=42, help="Base seed for the first run")
    parser.add_argument("--seed-step", type=int, default=97, help="Step between consecutive master seeds")
    parser.add_argument("--rmse-threshold", type=float, default=1.0, help="Validity threshold for RMSE_R1 and RMSE_R2")
    parser.add_argument("--stage0-nfev", type=int, default=None, help="Override STAGE0_MAX_NFEV")
    parser.add_argument("--stage2-nfev", type=int, default=None, help="Override STAGE2_MAX_NFEV")
    parser.add_argument("--no-png", action="store_true", help="Do not render PNG table")
    parser.add_argument("--quiet", action="store_true", help="Suppress most run_case console output")
    return parser.parse_args()


def load_module(py_path: Path):
    if not py_path.exists():
        raise FileNotFoundError(f"Cannot find source script: {py_path}")

    spec = importlib.util.spec_from_file_location("sim2d_mvp_3_2_3_mod_summary", str(py_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {py_path}")

    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def apply_seed_bundle(mod, master_seed: int) -> None:
    """为一次运行配置一整套可重复随机种子。"""
    mod.SEED_MAIN = int(master_seed)
    mod.SEED_VIS_R1 = int(master_seed + 1001)
    mod.SEED_VIS_R2 = int(master_seed + 1002)
    mod.SEED_UWB_LOS_R1 = int(master_seed + 2001)
    mod.SEED_UWB_LOS_R2 = int(master_seed + 2002)
    mod.SEED_UWB_NLOS_R1 = int(master_seed + 3001)
    mod.SEED_UWB_NLOS_R2 = int(master_seed + 3002)


def set_runtime_options(mod, stage0_nfev: int | None, stage2_nfev: int | None) -> None:
    if hasattr(mod, "PRINT_STAGE0_RMSE"):
        mod.PRINT_STAGE0_RMSE = False
    if hasattr(mod, "PRINT_STAGE2_STATE_STATS"):
        mod.PRINT_STAGE2_STATE_STATS = False
    mod.plt.show = lambda *a, **k: None

    if stage0_nfev is not None and hasattr(mod, "STAGE0_MAX_NFEV"):
        mod.STAGE0_MAX_NFEV = stage0_nfev
    if stage2_nfev is not None and hasattr(mod, "STAGE2_MAX_NFEV"):
        mod.STAGE2_MAX_NFEV = stage2_nfev


def compute_max_deviation(gt: np.ndarray, est: np.ndarray) -> float:
    err = np.linalg.norm(est[:, :2] - gt[:, :2], axis=1)
    return float(np.max(err))


def is_finite_array(x: np.ndarray) -> bool:
    return bool(np.all(np.isfinite(x)))


def run_one(mod, scene: str, seed_index: int, master_seed: int, rmse_threshold: float, quiet: bool) -> RunRecord:
    scene_label = SCENE_LABELS.get(scene, scene)
    apply_seed_bundle(mod, master_seed)

    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()

    try:
        if quiet:
            with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
                result = mod.run_case(
                    case_name=scene,
                    show=False,
                    save_fig=False,
                    return_dict=True,
                    solver_verbose=0,
                )
        else:
            result = mod.run_case(
                case_name=scene,
                show=False,
                save_fig=False,
                return_dict=True,
                solver_verbose=0,
            )

        gt1 = result["gt1"]
        gt2 = result["gt2"]
        est1 = result["est1"]
        est2 = result["est2"]
        rmse1 = float(result["metrics"]["est_rmse1"])
        rmse2 = float(result["metrics"]["est_rmse2"])
        max_dev1 = compute_max_deviation(gt1, est1)
        max_dev2 = compute_max_deviation(gt2, est2)

        valid = (
            is_finite_array(est1)
            and is_finite_array(est2)
            and math.isfinite(rmse1)
            and math.isfinite(rmse2)
            and rmse1 < rmse_threshold
            and rmse2 < rmse_threshold
        )

        note = "ok" if valid else f"invalid: rmse threshold exceeded or non-finite result (thr={rmse_threshold})"
        return RunRecord(
            scene=scene,
            scene_label=scene_label,
            seed_index=seed_index,
            seed_main=master_seed,
            valid=int(valid),
            rmse1=rmse1,
            rmse2=rmse2,
            max_dev1=max_dev1,
            max_dev2=max_dev2,
            note=note,
        )
    except Exception as exc:  # noqa: BLE001
        return RunRecord(
            scene=scene,
            scene_label=scene_label,
            seed_index=seed_index,
            seed_main=master_seed,
            valid=0,
            rmse1=float("nan"),
            rmse2=float("nan"),
            max_dev1=float("nan"),
            max_dev2=float("nan"),
            note=f"exception: {type(exc).__name__}: {exc}",
        )


def aggregate_records(records: List[RunRecord], num_seeds: int) -> List[AggregateRecord]:
    scene_to_records: Dict[str, List[RunRecord]] = {}
    for rec in records:
        scene_to_records.setdefault(rec.scene, []).append(rec)

    aggregates: List[AggregateRecord] = []
    for scene, recs in scene_to_records.items():
        scene_label = recs[0].scene_label if recs else SCENE_LABELS.get(scene, scene)
        valid_recs = [r for r in recs if r.valid == 1]
        n_valid = len(valid_recs)
        n_total = num_seeds
        stability_ratio = float(n_valid / n_total) if n_total > 0 else 0.0

        if n_valid > 0:
            mean_rmse1 = float(np.mean([r.rmse1 for r in valid_recs]))
            mean_rmse2 = float(np.mean([r.rmse2 for r in valid_recs]))
            mean_max_dev1 = float(np.mean([r.max_dev1 for r in valid_recs]))
            mean_max_dev2 = float(np.mean([r.max_dev2 for r in valid_recs]))
            rmse_pair_str = f"{mean_rmse1:.3f} / {mean_rmse2:.3f} m"
            max_dev_pair_str = f"{mean_max_dev1:.3f} / {mean_max_dev2:.3f} m"
        else:
            mean_rmse1 = mean_rmse2 = float("nan")
            mean_max_dev1 = mean_max_dev2 = float("nan")
            rmse_pair_str = "N/A"
            max_dev_pair_str = "N/A"

        stability_str = f"{n_valid}/{n_total} ({100.0 * stability_ratio:.0f}%)"
        aggregates.append(
            AggregateRecord(
                scene=scene,
                scene_label=scene_label,
                n_valid=n_valid,
                n_total=n_total,
                stability_ratio=stability_ratio,
                mean_rmse1=mean_rmse1,
                mean_rmse2=mean_rmse2,
                mean_max_dev1=mean_max_dev1,
                mean_max_dev2=mean_max_dev2,
                rmse_pair_str=rmse_pair_str,
                max_dev_pair_str=max_dev_pair_str,
                stability_str=stability_str,
            )
        )

    # 保持输入场景顺序
    order_map = {scene: idx for idx, scene in enumerate(DEFAULT_SCENES)}
    aggregates.sort(key=lambda x: order_map.get(x.scene, 999))
    return aggregates


def write_csv(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, aggregates: List[AggregateRecord]) -> None:
    lines = []
    lines.append("# Compact Summary Table (Current Method: 3.2.3)")
    lines.append("")
    lines.append("| Scene | Dual-Robot RMSE (R1 / R2) | Max Deviation (R1 / R2) | Stability |")
    lines.append("|---|---:|---:|---:|")
    for agg in aggregates:
        lines.append(
            f"| {agg.scene_label} | {agg.rmse_pair_str} | {agg.max_dev_pair_str} | {agg.stability_str} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_png_table(path: Path, aggregates: List[AggregateRecord]) -> None:
    headers = [
        "Scene",
        "Dual-Robot RMSE\n(R1 / R2)",
        "Max Deviation\n(R1 / R2)",
        "Stability",
    ]
    rows = [[agg.scene_label, agg.rmse_pair_str, agg.max_dev_pair_str, agg.stability_str] for agg in aggregates]

    fig_h = 1.8 + 0.7 * max(len(rows), 1)
    fig, ax = plt.subplots(figsize=(9.5, fig_h))
    ax.axis("off")

    table = ax.table(
        cellText=rows,
        colLabels=headers,
        cellLoc="center",
        colLoc="center",
        loc="center",
        colWidths=[0.28, 0.24, 0.24, 0.16],
    )

    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.0, 1.8)

    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor("#444444")
        if r == 0:
            cell.set_facecolor("#e9eef7")
            cell.set_text_props(weight="bold")
        else:
            if r % 2 == 1:
                cell.set_facecolor("#f8f8f8")
            else:
                cell.set_facecolor("white")

    fig.suptitle("Compact Summary Table: Current Method (3.2.3)", y=0.96, fontsize=14)
    fig.text(
        0.5,
        0.92,
        "Rows = scenes only; columns = dual-robot RMSE / max deviation / stability",
        ha="center",
        va="center",
        fontsize=10.5,
    )
    fig.subplots_adjust(top=0.80, bottom=0.08, left=0.03, right=0.97)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    args = parse_args()
    src = Path(args.src).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    mod = load_module(src)
    set_runtime_options(mod, args.stage0_nfev, args.stage2_nfev)

    old_cwd = Path.cwd()
    try:
        os.chdir(src.parent)

        records: List[RunRecord] = []
        for scene in args.scenes:
            label = SCENE_LABELS.get(scene, scene)
            print(f"[Summary] Scene: {scene} ({label})")
            for seed_index in range(args.num_seeds):
                master_seed = int(args.seed_start + seed_index * args.seed_step)
                rec = run_one(
                    mod=mod,
                    scene=scene,
                    seed_index=seed_index,
                    master_seed=master_seed,
                    rmse_threshold=args.rmse_threshold,
                    quiet=args.quiet,
                )
                records.append(rec)
                status = "valid" if rec.valid else "invalid"
                print(
                    f"  - seed[{seed_index:02d}] main={master_seed:6d} -> {status} | "
                    f"R1={rec.rmse1:.4f} | R2={rec.rmse2:.4f} | "
                    f"Max1={rec.max_dev1:.4f} | Max2={rec.max_dev2:.4f}"
                )

        aggregates = aggregate_records(records, num_seeds=args.num_seeds)

        detailed_csv = out_dir / "summary_detailed_runs.csv"
        aggregate_csv = out_dir / "summary_aggregated.csv"
        markdown_path = out_dir / "summary_table.md"
        png_path = out_dir / "summary_table.png"

        write_csv(detailed_csv, [asdict(r) for r in records])
        write_csv(aggregate_csv, [asdict(r) for r in aggregates])
        write_markdown(markdown_path, aggregates)
        if not args.no_png:
            render_png_table(png_path, aggregates)

        print("\n[Summary] Aggregated table")
        for agg in aggregates:
            print(
                f"  * {agg.scene_label:<26s} | RMSE={agg.rmse_pair_str:<20s} | "
                f"MaxDev={agg.max_dev_pair_str:<20s} | Stability={agg.stability_str}"
            )

        print(f"\n[Summary] Detailed CSV : {detailed_csv}")
        print(f"[Summary] Aggregate CSV: {aggregate_csv}")
        print(f"[Summary] Markdown     : {markdown_path}")
        if not args.no_png:
            print(f"[Summary] PNG table    : {png_path}")
    finally:
        os.chdir(old_cwd)

    return 0


if __name__ == "__main__":
    sys.exit(main())
