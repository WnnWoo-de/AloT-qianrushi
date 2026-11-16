#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate first-stage patent figures for the 3.2.3 engineering implementation.

This script is intentionally patent-figure specific:
- Fig. 1-3 are method/model/mapping schematics.
- Fig. 8-9 are redrawn from one shared run_case("uwb_only") result.
- Fig. 4-7 are not generated because the repository has no long-corridor case yet.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import os
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle


DEFAULT_FIGURES = [1, 2, 3, 8, 9]
VALID_FIGURES = {1, 2, 3, 8, 9}

FIGURE_FILES: Dict[int, str] = {
    1: "fig01_method_flow.png",
    2: "fig02_factor_graph_model.png",
    3: "fig03_reliability_mapping.png",
    8: "fig08_uwb_nlos_trajectory.png",
    9: "fig09_uwb_reliability_state.png",
}


def configure_matplotlib() -> None:
    """Configure Matplotlib for Chinese patent labels when a CJK font is available."""
    preferred_fonts = [
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    plt.rcParams["font.sans-serif"] = preferred_fonts
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["font.size"] = 11
    plt.rcParams["axes.titlesize"] = 14
    plt.rcParams["axes.labelsize"] = 11
    plt.rcParams["legend.fontsize"] = 10
    plt.rcParams["xtick.labelsize"] = 10
    plt.rcParams["ytick.labelsize"] = 10


def load_module(py_path: Path):
    if not py_path.exists():
        raise FileNotFoundError(f"找不到源脚本: {py_path}")

    spec = importlib.util.spec_from_file_location("sim2d_mvp_3_2_3_mod", str(py_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载模块: {py_path}")

    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def parse_figures(figures: Iterable[int]) -> List[int]:
    selected: List[int] = []
    for fig_no in figures:
        if fig_no not in VALID_FIGURES:
            raise ValueError(f"不支持的图号: {fig_no}; 可选图号为 1 2 3 8 9")
        if fig_no not in selected:
            selected.append(fig_no)
    return selected


def save_figure(fig, out_path: Path, dpi: int) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return out_path


def add_box(
    ax,
    xy,
    width: float,
    height: float,
    text: str,
    facecolor: str = "#f8fbff",
    edgecolor: str = "#2f5f8f",
    fontsize: float = 10.5,
    linewidth: float = 1.4,
    zorder: int = 2,
):
    x, y = xy
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=linewidth,
        zorder=zorder,
    )
    ax.add_patch(patch)
    ax.text(
        x + width / 2,
        y + height / 2,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        linespacing=1.18,
        zorder=zorder + 1,
    )
    return patch


def add_arrow(ax, start, end, color: str = "#555555", rad: float = 0.0, linewidth: float = 1.5):
    arrow = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=15,
        linewidth=linewidth,
        color=color,
        connectionstyle=f"arc3,rad={rad}",
        zorder=6,
    )
    ax.add_patch(arrow)
    return arrow


def draw_fig01_method_flow(out_dir: Path, dpi: int) -> Path:
    fig, ax = plt.subplots(figsize=(9.5, 12.0))
    ax.set_axis_off()
    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(0.0, 1.0)

    ax.text(
        0.5,
        0.975,
        "图1  基于UWB弱全局约束与可靠性感知鲁棒融合的双车异构协同建图方法流程图",
        ha="center",
        va="top",
        fontsize=14,
        fontweight="bold",
    )

    steps = [
        "S1  获取第一车辆里程计、第二车辆里程计、\nUWB锚点坐标和UWB测距数据，构建基础观测集合",
        "S2  构建统一后端因子图，包含双车里程计因子、\nUWB测距因子和位姿先验因子；执行Stage-0基础优化",
        "S3  基于Stage-0初始轨迹和观测数据，\n生成里程计模态与UWB模态的诊断可靠性序列",
        "S4  将诊断可靠性序列作为先验观测，\n引入图内显式可靠性状态并映射到[s_min, 1]",
        "S5  构建联合优化代价函数，包含观测残差项、\n诊断可靠性先验项和可靠性状态时间平滑项",
        "S6  对同一时刻共享UWB可靠性状态的多条测距边，\n按测距边数量的平方根增强诊断先验权重",
        "S7  对双车轨迹状态和各模态可靠性状态\n执行Stage-2联合优化",
        "S8  输出优化后的双车统一轨迹和时变可靠性状态，\n为局部地图或局部点云拼接提供位姿基准",
    ]

    x0, width = 0.10, 0.80
    height, step = 0.068, 0.100
    y0 = 0.850
    colors = ["#eef6ff", "#f4f8ff", "#eefaf3", "#f7fbef"] * 2

    centers = []
    for idx, text in enumerate(steps):
        y = y0 - idx * step
        add_box(ax, (x0, y), width, height, text, facecolor=colors[idx], fontsize=10.4)
        centers.append((0.5, y + height / 2))

    for idx in range(len(centers) - 1):
        add_arrow(
            ax,
            (centers[idx][0], centers[idx][1] - height / 2 - 0.002),
            (centers[idx + 1][0], centers[idx + 1][1] + height / 2 + 0.002),
            linewidth=1.8,
        )

    ax.text(
        0.5,
        0.035,
        "注：图1为方法流程示意，编号按权利要求和摘要中的S1-S8主线统一。",
        ha="center",
        va="center",
        fontsize=10,
        color="#555555",
    )
    return save_figure(fig, out_dir / FIGURE_FILES[1], dpi)


def draw_pose_node(ax, x: float, y: float, label: str, color: str):
    node = Circle((x, y), 0.043, facecolor=color, edgecolor="#333333", linewidth=1.3, zorder=3)
    ax.add_patch(node)
    ax.text(x, y, label, ha="center", va="center", fontsize=10, zorder=4)
    return node


def draw_factor(ax, x: float, y: float, label: str, color: str = "#f5f5f5"):
    size = 0.052
    patch = Rectangle(
        (x - size / 2, y - size / 2),
        size,
        size,
        facecolor=color,
        edgecolor="#333333",
        linewidth=1.2,
        zorder=4,
    )
    ax.add_patch(patch)
    ax.text(x, y - 0.065, label, ha="center", va="top", fontsize=8.8, linespacing=1.05)
    return patch


def draw_anchor(ax, x: float, y: float, label: str):
    size = 0.055
    patch = Rectangle(
        (x - size / 2, y - size / 2),
        size,
        size,
        facecolor="#fff4df",
        edgecolor="#9a6b00",
        linewidth=1.3,
        zorder=3,
    )
    ax.add_patch(patch)
    ax.text(x, y, label, ha="center", va="center", fontsize=10, fontweight="bold", zorder=4)
    return patch


def draw_fig02_factor_graph(out_dir: Path, dpi: int) -> Path:
    fig, ax = plt.subplots(figsize=(12.5, 7.4))
    ax.set_axis_off()
    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(0.0, 1.0)

    ax.text(
        0.5,
        0.965,
        "图2  统一后端因子图模型结构示意图",
        ha="center",
        va="top",
        fontsize=14,
        fontweight="bold",
    )

    time_x = [0.22, 0.50, 0.78]
    y_r1, y_r2 = 0.66, 0.42
    r1_labels = ["x1,k-1", "x1,k", "x1,k+1"]
    r2_labels = ["x2,k-1", "x2,k", "x2,k+1"]

    ax.text(0.065, y_r1, "第一车辆\n位姿节点", ha="center", va="center", fontsize=10)
    ax.text(0.065, y_r2, "第二车辆\n位姿节点", ha="center", va="center", fontsize=10)

    for x, label in zip(time_x, r1_labels):
        draw_pose_node(ax, x, y_r1, label, "#dff3e6")
    for x, label in zip(time_x, r2_labels):
        draw_pose_node(ax, x, y_r2, label, "#dceaff")

    for row_y, factor_label, factor_color in [
        (y_r1, "第一车辆\n里程计因子", "#e8f7ed"),
        (y_r2, "第二车辆\n里程计因子", "#e7efff"),
    ]:
        for left, right in zip(time_x[:-1], time_x[1:]):
            mid = (left + right) / 2
            ax.plot([left + 0.043, mid - 0.026], [row_y, row_y], color="#555555", linewidth=1.3)
            ax.plot([mid + 0.026, right - 0.043], [row_y, row_y], color="#555555", linewidth=1.3)
            draw_factor(ax, mid, row_y, factor_label, factor_color)

    draw_factor(ax, 0.115, y_r1, "首帧\n位姿先验", "#fff0f0")
    ax.plot([0.141, time_x[0] - 0.043], [y_r1, y_r1], color="#555555", linewidth=1.3)

    anchors = [(0.11, 0.84, "A1"), (0.89, 0.84, "A2"), (0.11, 0.20, "A3"), (0.89, 0.20, "A4")]
    for x, y, label in anchors:
        draw_anchor(ax, x, y, label)

    uwb_targets = [
        (time_x[1], y_r1, 0.11, 0.84),
        (time_x[1], y_r1, 0.89, 0.84),
        (time_x[1], y_r2, 0.11, 0.20),
        (time_x[1], y_r2, 0.89, 0.20),
    ]
    for px, py, ax_x, ax_y in uwb_targets:
        ax.plot(
            [px, ax_x],
            [py, ax_y],
            color="#d28a00",
            linewidth=1.3,
            linestyle="--",
            alpha=0.85,
            zorder=1,
        )
    ax.text(0.50, 0.825, "Anchor-UWB测距因子", ha="center", va="center", fontsize=10, color="#8a5b00")

    add_box(
        ax,
        (0.30, 0.065),
        0.40,
        0.105,
        "图内可靠性状态变量\ns_lio(k), s_rtab(k), s_uwb1(k), s_uwb2(k)",
        facecolor="#f4ecff",
        edgecolor="#6b46a3",
        fontsize=10,
    )
    add_box(
        ax,
        (0.045, 0.065),
        0.20,
        0.105,
        "诊断可靠性先验\ns_hat_lio / s_hat_rtab / s_hat_uwb",
        facecolor="#f4fbf2",
        edgecolor="#4c7a38",
        fontsize=9.4,
    )
    add_box(
        ax,
        (0.755, 0.065),
        0.20,
        0.105,
        "可靠性状态\n时间平滑项",
        facecolor="#f2f5ff",
        edgecolor="#3c5a9a",
        fontsize=10,
    )
    add_box(
        ax,
        (0.725, 0.515),
        0.23,
        0.105,
        "UWB先验平衡加权\nsqrt(n_uwb(k))",
        facecolor="#fff7e8",
        edgecolor="#a56b00",
        fontsize=9.8,
    )

    add_arrow(ax, (0.245, 0.118), (0.30, 0.118), color="#4c7a38")
    add_arrow(ax, (0.755, 0.118), (0.70, 0.118), color="#3c5a9a")
    add_arrow(ax, (0.50, 0.170), (0.36, y_r1 - 0.035), color="#6b46a3", rad=-0.20)
    add_arrow(ax, (0.50, 0.170), (0.36, y_r2 + 0.035), color="#6b46a3", rad=0.15)
    add_arrow(ax, (0.57, 0.170), (0.50, 0.49), color="#6b46a3", rad=0.05)
    add_arrow(ax, (0.835, 0.515), (0.62, 0.155), color="#a56b00", rad=-0.20)

    ax.text(
        0.5,
        0.015,
        "注：图2为模型结构示意，显示位姿节点、观测因子、图内可靠性状态、诊断先验、时间平滑与UWB先验平衡加权关系。",
        ha="center",
        va="bottom",
        fontsize=9.5,
        color="#555555",
    )
    return save_figure(fig, out_dir / FIGURE_FILES[2], dpi)


def draw_fig03_reliability_mapping(mod, out_dir: Path, dpi: int) -> Path:
    floor = float(getattr(mod, "RELIABILITY_FLOOR", 0.10))

    odom_errors = np.linspace(0.0, 3.0, 260)
    s_odom = mod.map_odom_error_series_to_reliability(
        odom_errors,
        floor=floor,
        smooth_win=1,
    )

    uwb_baseline = np.linspace(0.05, 0.25, 220)
    uwb_sweep = np.linspace(0.05, 2.0, 260)
    uwb_errors = np.concatenate([uwb_baseline, uwb_sweep])
    s_uwb_all = mod.map_uwb_error_series_to_reliability(
        uwb_errors,
        floor=floor,
        smooth_win=1,
    )
    s_uwb = s_uwb_all[len(uwb_baseline) :]

    raw = np.linspace(-6.0, 6.0, 260)
    s_raw = mod.raw_to_reliability(raw, floor=floor)

    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.8))
    fig.suptitle("图3  诊断可靠性映射函数曲线示意图", fontsize=14, fontweight="bold", y=1.03)

    axes[0].plot(odom_errors, s_odom, color="#1b7f3b", linewidth=2.2, label="里程计方差比诊断映射")
    axes[0].plot(uwb_sweep, s_uwb, color="#d28a00", linewidth=2.2, label="UWB残差诊断映射")
    axes[0].axhline(floor, color="#777777", linewidth=1.2, linestyle="--", label="可靠性下限 s_min")
    axes[0].set_xlabel("诊断误差 / 残差强度（示意尺度）")
    axes[0].set_ylabel("可靠性 s")
    axes[0].set_ylim(floor - 0.04, 1.04)
    axes[0].grid(True, alpha=0.28)
    axes[0].legend(loc="upper right")
    axes[0].set_title("(a) 诊断量到可靠性的映射")

    axes[1].plot(raw, s_raw, color="#6b46a3", linewidth=2.3, label="raw_to_reliability(raw)")
    axes[1].axhline(floor, color="#777777", linewidth=1.2, linestyle="--", label="可靠性下限 s_min")
    axes[1].set_xlabel("无界可靠性原始变量 raw")
    axes[1].set_ylabel("图内可靠性状态 s")
    axes[1].set_ylim(floor - 0.04, 1.04)
    axes[1].grid(True, alpha=0.28)
    axes[1].legend(loc="lower right")
    axes[1].set_title("(b) 有界状态映射到 [s_min, 1]")

    fig.text(
        0.5,
        -0.02,
        "注：图3为映射关系示意，曲线由 sim2d_mvp_3.2.3.py 中的映射函数采样得到，不作为实验结果曲线。",
        ha="center",
        va="top",
        fontsize=9.5,
        color="#555555",
    )
    fig.tight_layout()
    return save_figure(fig, out_dir / FIGURE_FILES[3], dpi)


def run_uwb_only_case(mod, src_dir: Path, quiet: bool):
    if not hasattr(mod, "run_case"):
        raise AttributeError("源脚本未提供 run_case() 接口。")

    kwargs = dict(
        case_name="uwb_only",
        show=False,
        save_fig=False,
        return_dict=True,
        solver_verbose=0,
    )

    old_cwd = Path.cwd()
    try:
        os.chdir(src_dir)
        if quiet:
            with contextlib.redirect_stdout(io.StringIO()):
                return mod.run_case(**kwargs)
        return mod.run_case(**kwargs)
    finally:
        os.chdir(old_cwd)


def collect_xy_bounds(result: dict, keys: Sequence[str]) -> tuple[float, float, float, float]:
    xs, ys = [], []
    for key in keys:
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
    return x_min - 0.08 * dx, x_max + 0.08 * dx, y_min - 0.08 * dy, y_max + 0.08 * dy


def draw_fig08_uwb_trajectory(result: dict, out_dir: Path, dpi: int) -> Path:
    anchors = np.asarray(result["anchors"])
    gt1 = np.asarray(result["gt1"])
    gt2 = np.asarray(result["gt2"])
    init1 = np.asarray(result["init1"])
    init2 = np.asarray(result["init2"])
    est1 = np.asarray(result["est1"])
    est2 = np.asarray(result["est2"])

    fig, ax = plt.subplots(figsize=(9.2, 7.2))
    ax.scatter(anchors[:, 0], anchors[:, 1], marker="s", s=105, color="#222222", label="UWB锚点", zorder=5)
    ax.plot(gt1[:, 0], gt1[:, 1], color="#1b7f3b", linestyle="-", linewidth=2.0, label="车辆1真实轨迹")
    ax.plot(gt2[:, 0], gt2[:, 1], color="#1f4e8c", linestyle="-", linewidth=2.0, label="车辆2真实轨迹")
    ax.plot(init1[:, 0], init1[:, 1], color="#1b7f3b", linestyle="--", linewidth=1.6, alpha=0.75, label="车辆1初始轨迹")
    ax.plot(init2[:, 0], init2[:, 1], color="#1f4e8c", linestyle="--", linewidth=1.6, alpha=0.75, label="车辆2初始轨迹")
    ax.plot(est1[:, 0], est1[:, 1], color="#d62728", linestyle="-", linewidth=2.2, label="车辆1优化轨迹")
    ax.plot(est2[:, 0], est2[:, 1], color="#c2185b", linestyle="-", linewidth=2.2, label="车辆2优化轨迹")

    x0, x1, y0, y1 = collect_xy_bounds(result, ["anchors", "gt1", "gt2", "init1", "init2", "est1", "est2"])
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.28)
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_title("图8  UWB部分锚点可见且存在NLOS干扰场景轨迹对比图（数值仿真）", fontweight="bold")
    ax.legend(loc="best", frameon=True)

    ax.text(
        0.02,
        0.02,
        f"场景: {result.get('degradation_case', 'uwb_only')}；版本: {result.get('version', '3.2.3')}",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=9.5,
        bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#bbbbbb", alpha=0.92),
    )
    fig.tight_layout()
    return save_figure(fig, out_dir / FIGURE_FILES[8], dpi)


def draw_fig09_uwb_reliability(result: dict, out_dir: Path, dpi: int) -> Path:
    s_hat_uwb1 = np.asarray(result["s_hat_uwb1"])
    s_hat_uwb2 = np.asarray(result["s_hat_uwb2"])
    s_uwb1_opt = np.asarray(result["s_uwb1_opt"])
    s_uwb2_opt = np.asarray(result["s_uwb2_opt"])

    floor = 0.10
    for key in ["s_hat_uwb1", "s_hat_uwb2", "s_uwb1_opt", "s_uwb2_opt"]:
        arr = np.asarray(result[key])
        if arr.size:
            floor = min(floor, float(np.nanmin(arr)))

    t1 = np.arange(len(s_hat_uwb1))
    t2 = np.arange(len(s_hat_uwb2))

    fig, ax = plt.subplots(figsize=(10.4, 6.2))
    ax.plot(t1, s_hat_uwb1, color="#1b7f3b", linestyle="--", linewidth=1.9, label="车辆1诊断可靠性")
    ax.plot(t1, s_uwb1_opt, color="#d62728", linestyle="-", linewidth=2.2, label="车辆1图内可靠性")
    ax.plot(t2, s_hat_uwb2, color="#1f4e8c", linestyle="--", linewidth=1.9, label="车辆2诊断可靠性")
    ax.plot(t2, s_uwb2_opt, color="#c2185b", linestyle="-", linewidth=2.2, label="车辆2图内可靠性")
    ax.axhline(floor, color="#777777", linestyle=":", linewidth=1.2, label="可靠性下限")

    ax.set_xlabel("时间步 k")
    ax.set_ylabel("UWB可靠性状态")
    ax.set_ylim(max(0.0, floor - 0.05), 1.04)
    ax.grid(True, alpha=0.28)
    ax.set_title("图9  对应图8仿真过程的UWB可靠性状态随时间变化曲线（数值仿真）", fontweight="bold")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3, frameon=True)
    fig.text(
        0.5,
        0.02,
        "注：图9与图8来自同一次 run_case(\"uwb_only\") 运行结果。",
        ha="center",
        va="bottom",
        fontsize=9.5,
        color="#555555",
    )
    fig.tight_layout(rect=[0.0, 0.11, 1.0, 1.0])
    return save_figure(fig, out_dir / FIGURE_FILES[9], dpi)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成专利附图第一阶段图1、图2、图3、图8、图9")
    parser.add_argument("--src", type=str, default="sim2d_mvp_3.2.3.py", help="3.2.3 主脚本路径")
    parser.add_argument("--out-dir", type=str, default="figs/patent_figures", help="专利附图输出目录")
    parser.add_argument("--dpi", type=int, default=300, help="输出 DPI")
    parser.add_argument(
        "--figures",
        nargs="+",
        type=int,
        default=DEFAULT_FIGURES,
        help="选择要生成的图号，可选: 1 2 3 8 9；默认全部生成",
    )
    parser.add_argument("--quiet", dest="quiet", action="store_true", default=True, help="静默 run_case() 内部输出（默认）")
    parser.add_argument("--verbose", dest="quiet", action="store_false", help="显示 run_case() 内部输出")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_matplotlib()

    src = Path(args.src).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    figures = parse_figures(args.figures)

    mod = load_module(src)

    generated: List[Path] = []
    if 1 in figures:
        generated.append(draw_fig01_method_flow(out_dir, args.dpi))
    if 2 in figures:
        generated.append(draw_fig02_factor_graph(out_dir, args.dpi))
    if 3 in figures:
        generated.append(draw_fig03_reliability_mapping(mod, out_dir, args.dpi))

    uwb_result = None
    if 8 in figures or 9 in figures:
        print("[Patent Figures] 运行一次 uwb_only 场景，用于图8和图9...")
        uwb_result = run_uwb_only_case(mod, src.parent, quiet=args.quiet)

    if 8 in figures:
        if uwb_result is None:
            raise RuntimeError("图8需要 uwb_only 运行结果。")
        generated.append(draw_fig08_uwb_trajectory(uwb_result, out_dir, args.dpi))
    if 9 in figures:
        if uwb_result is None:
            raise RuntimeError("图9需要 uwb_only 运行结果。")
        generated.append(draw_fig09_uwb_reliability(uwb_result, out_dir, args.dpi))

    print("[Patent Figures] 已生成:")
    for path in generated:
        print(f"  {path}")
    print("[Patent Figures] 图4-图7未生成：当前仓库尚未实现长走廊仿真场景。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
