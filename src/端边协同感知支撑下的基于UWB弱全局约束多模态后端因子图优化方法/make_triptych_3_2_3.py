#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为 sim2d_mvp_3.2.3.py 生成论文级干净版三联轨迹图。

设计原则：
1. 直接调用 sim2d_mvp_3.2.3.py 中的 run_case()；
2. 不拼接单场景 PNG，而是直接拿轨迹数据重画；
3. 三个子图共享坐标范围、总图例和统一标题；
4. 默认输出适合论文/汇报插图的干净版版式。

默认三联场景：
- normal_occ
- lio_only
- mixed_all

使用示例：
python3 make_triptych_3_2_3.py \
    --src ./sim2d_mvp_3.2.3.py \
    --out ./figs/triptych_3.2.3_clean_normal_lio_mixed.png
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


DEFAULT_CASES = ["normal_occ", "lio_only", "mixed_all"]
CASE_TITLES: Dict[str, str] = {
    "normal_occ": "(a) Normal occlusion",
    "uwb_only": "(b) UWB-only degradation",
    "lio_only": "(b) Single-modal degradation",
    "rtab_only": "(b) RTAB-only degradation",
    "dual_lio_uwb": "(c) LIO + UWB degradation",
    "dual_rtab_uwb": "(c) RTAB + UWB degradation",
    "mixed_all": "(c) Mixed degradation",
}

LINE_STYLES = {
    "anchors": dict(marker="s", linestyle="None", s=70, color="black", label="Anchors"),
    "gt1": dict(color="#1b7f3b", linestyle="-", linewidth=2.0, label="GT Robot1"),
    "gt2": dict(color="#1f4e8c", linestyle="-", linewidth=2.0, label="GT Robot2"),
    "init1": dict(color="#1b7f3b", linestyle="--", linewidth=1.6, alpha=0.75, label="Init Robot1"),
    "init2": dict(color="#1f4e8c", linestyle="--", linewidth=1.6, alpha=0.75, label="Init Robot2"),
    "est1": dict(color="#d62728", linestyle="-", linewidth=2.3, label="Optimized Robot1"),
    "est2": dict(color="#c2185b", linestyle="-", linewidth=2.3, label="Optimized Robot2"),
}


def configure_matplotlib() -> None:
    plt.rcParams["font.size"] = 11
    plt.rcParams["axes.titlesize"] = 12
    plt.rcParams["axes.labelsize"] = 11
    plt.rcParams["legend.fontsize"] = 10
    plt.rcParams["xtick.labelsize"] = 10
    plt.rcParams["ytick.labelsize"] = 10
    plt.rcParams["figure.titlesize"] = 14
    plt.rcParams["axes.unicode_minus"] = False


def load_module(py_path: Path):
    if not py_path.exists():
        raise FileNotFoundError(f"找不到源脚本: {py_path}")

    spec = importlib.util.spec_from_file_location("sim2d_mvp_3_2_3_mod", str(py_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载模块: {py_path}")

    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_single_case(mod, case_name: str, quiet: bool = True):
    if not hasattr(mod, "run_case"):
        raise AttributeError("源脚本未提供 run_case() 接口，请确认 sim2d_mvp_3.2.3.py 已正确重构。")

    kwargs = dict(
        case_name=case_name,
        show=False,
        save_fig=False,
        return_dict=True,
        solver_verbose=0,
    )

    if quiet:
        with contextlib.redirect_stdout(io.StringIO()):
            return mod.run_case(**kwargs)
    return mod.run_case(**kwargs)


def collect_bounds(results: List[dict]) -> Tuple[float, float, float, float]:
    xs, ys = [], []
    for result in results:
        for key in ["anchors", "gt1", "gt2", "init1", "init2", "est1", "est2"]:
            arr = np.asarray(result[key])
            if arr.ndim != 2 or arr.shape[1] < 2:
                continue
            xs.append(arr[:, 0])
            ys.append(arr[:, 1])

    x_all = np.concatenate(xs)
    y_all = np.concatenate(ys)
    x_min, x_max = float(np.min(x_all)), float(np.max(x_all))
    y_min, y_max = float(np.min(y_all)), float(np.max(y_all))

    dx = max(x_max - x_min, 1.0)
    dy = max(y_max - y_min, 1.0)
    pad_x = 0.08 * dx
    pad_y = 0.08 * dy
    return x_min - pad_x, x_max + pad_x, y_min - pad_y, y_max + pad_y


def plot_case(ax, result: dict, title: str, show_ylabel: bool = False):
    anchors = np.asarray(result["anchors"])
    gt1 = np.asarray(result["gt1"])
    gt2 = np.asarray(result["gt2"])
    init1 = np.asarray(result["init1"])
    init2 = np.asarray(result["init2"])
    est1 = np.asarray(result["est1"])
    est2 = np.asarray(result["est2"])

    handles = []
    labels = []

    h = ax.scatter(anchors[:, 0], anchors[:, 1], **LINE_STYLES["anchors"])
    handles.append(h); labels.append(LINE_STYLES["anchors"]["label"])

    for key, arr in [("gt1", gt1), ("gt2", gt2), ("init1", init1), ("init2", init2), ("est1", est1), ("est2", est2)]:
        (line,) = ax.plot(arr[:, 0], arr[:, 1], **LINE_STYLES[key])
        handles.append(line)
        labels.append(LINE_STYLES[key]["label"])

    ax.set_title(title)
    ax.set_xlabel("x [m]")
    if show_ylabel:
        ax.set_ylabel("y [m]")
    ax.grid(True, alpha=0.28)
    ax.set_aspect("equal", adjustable="box")

    metrics = result.get("metrics", {})
    text = (
        f"RMSE R1: {metrics.get('est_rmse1', float('nan')):.3f} m\n"
        f"RMSE R2: {metrics.get('est_rmse2', float('nan')):.3f} m"
    )
    ax.text(
        0.03,
        0.03,
        text,
        transform=ax.transAxes,
        fontsize=9,
        ha="left",
        va="bottom",
        bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#b0b0b0", alpha=0.9),
    )
    return handles, labels


def dedup_legend(handles, labels):
    seen = set()
    new_h, new_l = [], []
    for h, l in zip(handles, labels):
        if l in seen:
            continue
        seen.add(l)
        new_h.append(h)
        new_l.append(l)
    return new_h, new_l


def compose_clean_triptych(results: List[dict], case_names: List[str], out_path: Path, dpi: int, title: str):
    configure_matplotlib()

    n = len(results)
    fig, axes = plt.subplots(1, n, figsize=(5.4 * n, 4.8), sharex=True, sharey=True)
    if n == 1:
        axes = [axes]

    x0, x1, y0, y1 = collect_bounds(results)

    all_handles, all_labels = [], []
    for idx, (ax, result, case_name) in enumerate(zip(axes, results, case_names)):
        panel_title = CASE_TITLES.get(case_name, case_name)
        handles, labels = plot_case(ax, result, panel_title, show_ylabel=(idx == 0))
        all_handles.extend(handles)
        all_labels.extend(labels)
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)

    legend_handles, legend_labels = dedup_legend(all_handles, all_labels)
    fig.legend(
        legend_handles,
        legend_labels,
        loc="upper center",
        ncol=4,
        frameon=False,
        bbox_to_anchor=(0.5, 0.98),
    )
    fig.suptitle(title, y=1.05)
    fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.90])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return out_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="为 sim2d_mvp_3.2.3.py 生成论文级干净版三联轨迹图")
    parser.add_argument("--src", type=str, default="sim2d_mvp_3.2.3.py", help="3.2.3 主脚本路径")
    parser.add_argument("--cases", nargs="+", default=DEFAULT_CASES, help="场景列表，默认: normal_occ lio_only mixed_all")
    parser.add_argument(
        "--out",
        type=str,
        default="figs/triptych_3.2.3_clean_normal_lio_mixed.png",
        help="输出路径",
    )
    parser.add_argument(
        "--title",
        type=str,
        default="Trajectory comparison under progressive degradation scenarios (v3.2.3)",
        help="统一总标题",
    )
    parser.add_argument("--dpi", type=int, default=300, help="输出 DPI")
    parser.add_argument("--no-quiet", action="store_true", help="保留 run_case() 内部打印")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    src = Path(args.src).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()
    case_names = args.cases

    if len(case_names) < 2:
        raise ValueError("至少提供 2 个场景；论文级三联图建议正好 3 个。")

    mod = load_module(src)

    old_cwd = Path.cwd()
    try:
        os.chdir(src.parent)
        results = []
        for case in case_names:
            print(f"[Triptych 3.2.3] 运行场景: {case}")
            result = run_single_case(mod, case_name=case, quiet=(not args.no_quiet))
            results.append(result)

        save_path = compose_clean_triptych(
            results=results,
            case_names=case_names,
            out_path=out,
            dpi=args.dpi,
            title=args.title,
        )
        print(f"[Triptych 3.2.3] 三联图已保存: {save_path}")
    finally:
        os.chdir(old_cwd)

    return 0


if __name__ == "__main__":
    sys.exit(main())
