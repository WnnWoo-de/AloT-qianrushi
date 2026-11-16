#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate patent Fig. 4-7 for a controlled long-corridor supplemental case.

This script is intentionally patent-figure specific. It does not add a new
DEGRADATION_CASE to sim2d_mvp_3.2.3.py and does not alter the 3.2.3 entrypoint.

Fig. 4/6: odometry-only baseline in the long-corridor degradation case.
Fig. 5/7: the 3.2.1 method implemented by the 3.2.3 reusable optimizer APIs.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import least_squares


FIGURE_FILES: Dict[int, str] = {
    4: "fig04_long_corridor_odom_baseline_trajectory.png",
    5: "fig05_long_corridor_proposed_trajectory.png",
    6: "fig06_long_corridor_odom_baseline_relative_error.png",
    7: "fig07_long_corridor_proposed_relative_error.png",
}

SCENE_NAME = "long_corridor_patent"
SEED_LONG_CORRIDOR = 4242
SEED_VIS_R1 = 5101
SEED_VIS_R2 = 5102
SEED_UWB_LOS_R1 = 6101
SEED_UWB_LOS_R2 = 6102

NUM_STEPS = 36
LIO_DEGRADE_WINDOWS: List[Tuple[int, int]] = [(13, 25)]
BASELINE_MAX_NFEV = 50
STAGE0_MAX_NFEV_LONG = 60
STAGE2_MAX_NFEV_LONG = 80

ROBOT2_LONG_CORRIDOR_INIT_OFFSET = np.array([-1.20, 0.75, 0.18], dtype=float)


@dataclass
class LongCorridorData:
    gt1: np.ndarray
    gt2: np.ndarray
    anchors: np.ndarray
    odom1: np.ndarray
    odom2: np.ndarray
    uwb1: list
    uwb2: list
    init1: np.ndarray
    init2: np.ndarray
    visibility_counts1: np.ndarray
    visibility_counts2: np.ndarray


@dataclass
class MethodResult:
    name: str
    est1: np.ndarray
    est2: np.ndarray
    relative_error: np.ndarray
    metrics: Dict[str, float]
    stage0_est1: np.ndarray | None = None
    stage0_est2: np.ndarray | None = None
    s_hat_lio: np.ndarray | None = None
    s_hat_rtab: np.ndarray | None = None
    s_hat_uwb1: np.ndarray | None = None
    s_hat_uwb2: np.ndarray | None = None
    s_lio_opt: np.ndarray | None = None
    s_rtab_opt: np.ndarray | None = None
    s_uwb1_opt: np.ndarray | None = None
    s_uwb2_opt: np.ndarray | None = None


def configure_matplotlib() -> None:
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
    plt.rcParams["legend.fontsize"] = 9.5
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


def make_pose_from_xy(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    dx = np.gradient(x)
    dy = np.gradient(y)
    yaw = np.arctan2(dy, dx)
    return np.column_stack([x, y, yaw])


def build_long_corridor_truth(num_steps: int = NUM_STEPS) -> tuple[np.ndarray, np.ndarray]:
    x = np.linspace(0.0, 22.0, num_steps)
    y1 = 1.35 + 0.06 * np.sin(0.45 * x)
    y2 = 2.65 + 0.05 * np.cos(0.38 * x + 0.25)

    gt1 = make_pose_from_xy(x, y1)
    gt2 = make_pose_from_xy(x + 0.45, y2)
    return gt1, gt2


def build_long_corridor_anchors() -> np.ndarray:
    return np.array(
        [
            [-1.0, 0.15],
            [3.5, 3.85],
            [8.0, 0.15],
            [12.5, 3.85],
            [17.0, 0.15],
            [23.0, 3.85],
        ],
        dtype=float,
    )


def make_window_scale(length: int, windows: Sequence[Tuple[int, int]], normal: float, degraded: float) -> np.ndarray:
    scale = np.full(length, normal, dtype=float)
    for a, b in windows:
        scale[max(0, a) : min(length, b)] = degraded
    return scale


def build_corridor_visibility(
    traj: np.ndarray,
    anchors: np.ndarray,
    seed: int,
    min_visible: int = 3,
    max_visible: int = 4,
) -> list[np.ndarray]:
    rng = np.random.default_rng(seed)
    schedule: list[np.ndarray] = []
    for pose in traj:
        p = pose[:2]
        order = np.argsort(np.linalg.norm(anchors - p, axis=1))
        n_visible = int(rng.integers(min_visible, max_visible + 1))
        schedule.append(np.array(order[:n_visible], dtype=int))
    return schedule


def count_visibility(schedule: Sequence[np.ndarray]) -> np.ndarray:
    return np.array([len(ids) for ids in schedule], dtype=int)


def generate_long_corridor_data(mod) -> LongCorridorData:
    np.random.seed(SEED_LONG_CORRIDOR)

    gt1, gt2 = build_long_corridor_truth(NUM_STEPS)
    anchors = build_long_corridor_anchors()

    lio_sigma_scale = make_window_scale(NUM_STEPS - 1, LIO_DEGRADE_WINDOWS, 1.0, 4.5)
    lio_bias_scale = make_window_scale(NUM_STEPS - 1, LIO_DEGRADE_WINDOWS, 1.0, 7.0)
    normal_scale = np.ones(NUM_STEPS - 1, dtype=float)

    odom1 = mod.simulate_odom(
        gt1,
        sigma_xy=0.025,
        sigma_yaw=0.008,
        bias_xy=(0.003, 0.010),
        bias_yaw=0.0025,
        sigma_scale_series=lio_sigma_scale,
        bias_scale_series=lio_bias_scale,
    )
    odom2 = mod.simulate_odom(
        gt2,
        sigma_xy=0.028,
        sigma_yaw=0.010,
        bias_xy=(0.002, -0.001),
        bias_yaw=-0.0008,
        sigma_scale_series=normal_scale,
        bias_scale_series=normal_scale,
    )

    vis1 = build_corridor_visibility(gt1, anchors, SEED_VIS_R1)
    vis2 = build_corridor_visibility(gt2, anchors, SEED_VIS_R2)

    uwb1 = mod.simulate_uwb(
        gt1,
        anchors,
        sigma_r=mod.UWB_SIGMA_R,
        error_mode="los",
        nlos_prob=0.0,
        visible_ids_per_step=vis1,
        rng_los=np.random.default_rng(SEED_UWB_LOS_R1),
        rng_nlos=np.random.default_rng(SEED_UWB_LOS_R1 + 100),
    )
    uwb2 = mod.simulate_uwb(
        gt2,
        anchors,
        sigma_r=mod.UWB_SIGMA_R,
        error_mode="los",
        nlos_prob=0.0,
        visible_ids_per_step=vis2,
        rng_los=np.random.default_rng(SEED_UWB_LOS_R2),
        rng_nlos=np.random.default_rng(SEED_UWB_LOS_R2 + 100),
    )

    init1 = mod.integrate_odom(odom1, gt1[0].copy())
    robot2_init = gt2[0].copy() + ROBOT2_LONG_CORRIDOR_INIT_OFFSET
    robot2_init[2] = mod.wrap_angle(robot2_init[2])
    init2 = mod.integrate_odom(odom2, robot2_init)

    return LongCorridorData(
        gt1=gt1,
        gt2=gt2,
        anchors=anchors,
        odom1=odom1,
        odom2=odom2,
        uwb1=uwb1,
        uwb2=uwb2,
        init1=init1,
        init2=init2,
        visibility_counts1=count_visibility(vis1),
        visibility_counts2=count_visibility(vis2),
    )


def relative_translation_error(est1: np.ndarray, est2: np.ndarray, gt1: np.ndarray, gt2: np.ndarray) -> np.ndarray:
    rel_est = est2[:, :2] - est1[:, :2]
    rel_gt = gt2[:, :2] - gt1[:, :2]
    return np.linalg.norm(rel_est - rel_gt, axis=1)


def position_rmse(est: np.ndarray, gt: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.sum((est[:, :2] - gt[:, :2]) ** 2, axis=1))))


def make_metrics(data: LongCorridorData, est1: np.ndarray, est2: np.ndarray, rel_err: np.ndarray) -> Dict[str, float]:
    return {
        "robot1_rmse_m": position_rmse(est1, data.gt1),
        "robot2_rmse_m": position_rmse(est2, data.gt2),
        "relative_rmse_m": float(np.sqrt(np.mean(rel_err**2))),
        "relative_mean_m": float(np.mean(rel_err)),
        "relative_max_m": float(np.max(rel_err)),
    }


def solve_odom_baseline(mod, data: LongCorridorData, solver_verbose: int) -> MethodResult:
    n1 = len(data.gt1)
    n2 = len(data.gt2)
    x0 = mod.pack_states(data.init1, data.init2)

    residual_fn = mod.build_residual_function(
        N1=n1,
        N2=n2,
        odom1=data.odom1,
        odom2=data.odom2,
        uwb1=[],
        uwb2=[],
        anchors=data.anchors,
        prior1=data.gt1[0],
        prior2=None,
        use_robot2_prior=False,
        use_uwb=False,
        sigma_prior_xy=mod.SIGMA_PRIOR_XY,
        sigma_prior_yaw=mod.SIGMA_PRIOR_YAW,
        sigma_odom_xy=mod.SIGMA_ODOM_XY,
        sigma_odom_yaw=mod.SIGMA_ODOM_YAW,
        sigma_uwb=mod.SIGMA_UWB,
        use_reliability_weighting=False,
        reliability_floor=mod.RELIABILITY_FLOOR,
    )

    result = least_squares(
        residual_fn,
        x0,
        verbose=solver_verbose,
        max_nfev=BASELINE_MAX_NFEV,
        loss="linear",
    )
    est1, est2 = mod.unpack_states(result.x, n1, n2)
    rel_err = relative_translation_error(est1, est2, data.gt1, data.gt2)
    return MethodResult(
        name="odom_only_baseline",
        est1=est1,
        est2=est2,
        relative_error=rel_err,
        metrics=make_metrics(data, est1, est2, rel_err),
    )


def solve_proposed_method(mod, data: LongCorridorData, solver_verbose: int) -> MethodResult:
    n1 = len(data.gt1)
    n2 = len(data.gt2)

    x0_stage0 = mod.pack_states(data.init1, data.init2)
    residual_stage0 = mod.build_residual_function(
        N1=n1,
        N2=n2,
        odom1=data.odom1,
        odom2=data.odom2,
        uwb1=data.uwb1,
        uwb2=data.uwb2,
        anchors=data.anchors,
        prior1=data.gt1[0],
        prior2=None,
        use_robot2_prior=False,
        use_uwb=True,
        sigma_prior_xy=mod.SIGMA_PRIOR_XY,
        sigma_prior_yaw=mod.SIGMA_PRIOR_YAW,
        sigma_odom_xy=mod.SIGMA_ODOM_XY,
        sigma_odom_yaw=mod.SIGMA_ODOM_YAW,
        sigma_uwb=mod.SIGMA_UWB,
        use_reliability_weighting=False,
        reliability_floor=mod.RELIABILITY_FLOOR,
    )
    stage0 = least_squares(
        residual_stage0,
        x0_stage0,
        verbose=solver_verbose,
        max_nfev=STAGE0_MAX_NFEV_LONG,
        loss="linear",
    )
    stage0_est1, stage0_est2 = mod.unpack_states(stage0.x, n1, n2)

    s_lio, s_rtab, s_uwb1, s_uwb2, _, _, _, _ = mod.build_diagnostic_reliability_series(
        traj1=stage0_est1,
        traj2=stage0_est2,
        odom1=data.odom1,
        odom2=data.odom2,
        uwb1=data.uwb1,
        uwb2=data.uwb2,
        anchors=data.anchors,
        sigma_odom_xy=mod.SIGMA_ODOM_XY,
        sigma_odom_yaw=mod.SIGMA_ODOM_YAW,
        sigma_uwb=mod.SIGMA_UWB,
        reliability_floor=mod.RELIABILITY_FLOOR,
        mad_scale_uwb=mod.DIAG_MAD_SCALE_UWB,
        smooth_win=mod.DIAG_SMOOTH_WIN,
        uwb_geom_blend=mod.UWB_GEOM_BLEND,
        odom_ref_prefix_len=mod.ODOM_REF_PREFIX_LEN,
        odom_var_half_window=mod.ODOM_VAR_HALF_WINDOW,
        odom_var_ratio_yaw_weight=mod.ODOM_VAR_RATIO_YAW_WEIGHT,
        odom_var_deadzone=mod.ODOM_VAR_DEADZONE,
        odom_var_drop_power=mod.ODOM_VAR_DROP_POWER,
        uwb_deadzone_z=mod.UWB_DEADZONE_Z,
        uwb_drop_sharpness=mod.UWB_DROP_SHARPNESS,
        use_uwb_geom_penalty=False,
    )

    raw_lio0 = mod.reliability_to_raw(s_lio, floor=mod.RELIABILITY_FLOOR)
    raw_rtab0 = mod.reliability_to_raw(s_rtab, floor=mod.RELIABILITY_FLOOR)
    raw_uwb10 = mod.reliability_to_raw(s_uwb1, floor=mod.RELIABILITY_FLOOR)
    raw_uwb20 = mod.reliability_to_raw(s_uwb2, floor=mod.RELIABILITY_FLOOR)
    x0_joint = mod.pack_joint_states(stage0_est1, stage0_est2, raw_lio0, raw_rtab0, raw_uwb10, raw_uwb20)

    residual_joint = mod.build_joint_reliability_residual_function(
        N1=n1,
        N2=n2,
        odom1=data.odom1,
        odom2=data.odom2,
        uwb1=data.uwb1,
        uwb2=data.uwb2,
        anchors=data.anchors,
        prior1=data.gt1[0],
        prior2=None,
        use_robot2_prior=False,
        use_uwb=True,
        sigma_prior_xy=mod.SIGMA_PRIOR_XY,
        sigma_prior_yaw=mod.SIGMA_PRIOR_YAW,
        sigma_odom_xy=mod.SIGMA_ODOM_XY,
        sigma_odom_yaw=mod.SIGMA_ODOM_YAW,
        sigma_uwb=mod.SIGMA_UWB,
        s_hat_lio=s_lio,
        s_hat_rtab=s_rtab,
        s_hat_uwb1=s_uwb1,
        s_hat_uwb2=s_uwb2,
        sigma_s_prior_lio=mod.SIGMA_S_PRIOR_LIO,
        sigma_s_prior_rtab=mod.SIGMA_S_PRIOR_RTAB,
        sigma_s_prior_uwb=mod.SIGMA_S_PRIOR_UWB,
        sigma_s_smooth_lio=mod.SIGMA_S_SMOOTH_LIO,
        sigma_s_smooth_rtab=mod.SIGMA_S_SMOOTH_RTAB,
        sigma_s_smooth_uwb=mod.SIGMA_S_SMOOTH_UWB,
        reliability_floor=mod.RELIABILITY_FLOOR,
        uwb_prior_balance_mode=mod.UWB_PRIOR_BALANCE_MODE,
    )

    joint = least_squares(
        residual_joint,
        x0_joint,
        verbose=solver_verbose,
        max_nfev=STAGE2_MAX_NFEV_LONG,
        loss="linear",
    )
    est1, est2, raw_lio, raw_rtab, raw_uwb1, raw_uwb2 = mod.unpack_joint_states(joint.x, n1, n2)

    s_lio_opt = mod.raw_to_reliability(raw_lio, floor=mod.RELIABILITY_FLOOR)
    s_rtab_opt = mod.raw_to_reliability(raw_rtab, floor=mod.RELIABILITY_FLOOR)
    s_uwb1_opt = mod.raw_to_reliability(raw_uwb1, floor=mod.RELIABILITY_FLOOR)
    s_uwb2_opt = mod.raw_to_reliability(raw_uwb2, floor=mod.RELIABILITY_FLOOR)

    rel_err = relative_translation_error(est1, est2, data.gt1, data.gt2)
    return MethodResult(
        name="proposed_graph_internal_reliability",
        est1=est1,
        est2=est2,
        relative_error=rel_err,
        metrics=make_metrics(data, est1, est2, rel_err),
        stage0_est1=stage0_est1,
        stage0_est2=stage0_est2,
        s_hat_lio=s_lio,
        s_hat_rtab=s_rtab,
        s_hat_uwb1=s_uwb1,
        s_hat_uwb2=s_uwb2,
        s_lio_opt=s_lio_opt,
        s_rtab_opt=s_rtab_opt,
        s_uwb1_opt=s_uwb1_opt,
        s_uwb2_opt=s_uwb2_opt,
    )


def set_equal_corridor_bounds(ax, data: LongCorridorData, *trajs: np.ndarray) -> None:
    arrays = [data.gt1, data.gt2, data.anchors, *trajs]
    x = np.concatenate([arr[:, 0] for arr in arrays])
    y = np.concatenate([arr[:, 1] for arr in arrays])
    dx = max(float(np.max(x) - np.min(x)), 1.0)
    dy = max(float(np.max(y) - np.min(y)), 1.0)
    ax.set_xlim(float(np.min(x) - 0.04 * dx), float(np.max(x) + 0.04 * dx))
    ax.set_ylim(float(np.min(y) - 0.18 * dy), float(np.max(y) + 0.18 * dy))
    ax.set_aspect("equal", adjustable="box")


def add_degradation_band(ax, data: LongCorridorData) -> None:
    for a, b in LIO_DEGRADE_WINDOWS:
        x0 = data.gt1[max(0, a), 0]
        x1 = data.gt1[min(len(data.gt1) - 1, b), 0]
        ax.axvspan(x0, x1, color="#f4a261", alpha=0.16, label="Robot1里程计退化窗口")


def draw_trajectory_figure(
    fig_no: int,
    data: LongCorridorData,
    result: MethodResult,
    out_dir: Path,
    dpi: int,
) -> Path:
    title = {
        4: "图4  仅依赖里程计约束方法在长走廊退化场景下的轨迹对比图（数值仿真）",
        5: "图5  本方法在长走廊退化场景下的轨迹对比图（数值仿真）",
    }[fig_no]

    fig, ax = plt.subplots(figsize=(10.8, 5.0))
    add_degradation_band(ax, data)
    ax.scatter(
        data.anchors[:, 0],
        data.anchors[:, 1],
        marker="s",
        s=85,
        color="#222222",
        label="UWB锚点（基线未使用）" if fig_no == 4 else "UWB锚点",
        zorder=6,
    )
    ax.plot(data.gt1[:, 0], data.gt1[:, 1], color="#1b7f3b", linewidth=2.1, label="车辆1真实轨迹")
    ax.plot(data.gt2[:, 0], data.gt2[:, 1], color="#1f4e8c", linewidth=2.1, label="车辆2真实轨迹")
    ax.plot(result.est1[:, 0], result.est1[:, 1], color="#d62728", linewidth=2.0, linestyle="-", label="车辆1估计轨迹")
    ax.plot(result.est2[:, 0], result.est2[:, 1], color="#c2185b", linewidth=2.0, linestyle="-", label="车辆2估计轨迹")

    set_equal_corridor_bounds(ax, data, result.est1, result.est2)
    ax.grid(True, alpha=0.30)
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_title(title, fontweight="bold")
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), ncol=1, frameon=True)
    fig.tight_layout(rect=[0.0, 0.0, 0.82, 1.0])

    out_path = out_dir / FIGURE_FILES[fig_no]
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return out_path


def draw_error_figure(fig_no: int, result: MethodResult, out_dir: Path, dpi: int) -> Path:
    title = {
        6: "图6  对应图4的双车轨迹相对误差随时间变化曲线（数值仿真）",
        7: "图7  对应图5的双车轨迹相对误差随时间变化曲线（数值仿真）",
    }[fig_no]
    color = "#a23b72" if fig_no == 6 else "#2a9d8f"
    label = "仅里程计基线" if fig_no == 6 else "本方法"

    t = np.arange(len(result.relative_error))
    fig, ax = plt.subplots(figsize=(9.6, 5.0))
    for a, b in LIO_DEGRADE_WINDOWS:
        ax.axvspan(a, b, color="#f4a261", alpha=0.16, label="Robot1里程计退化窗口")
    ax.plot(t, result.relative_error, color=color, linewidth=2.2, label=label)
    ax.grid(True, alpha=0.30)
    ax.set_xlabel("时间步 k")
    ax.set_ylabel("双车相对位移误差 [m]")
    ax.set_title(title, fontweight="bold")
    ax.set_xlim(0, len(result.relative_error) - 1)
    ax.set_ylim(0, max(0.5, float(np.max(result.relative_error)) * 1.12))
    ax.text(
        0.02,
        0.95,
        "e_rel(k)=||(p2_est-p1_est)-(p2_gt-p1_gt)||_2\n"
        f"RMSE={result.metrics['relative_rmse_m']:.3f} m, Max={result.metrics['relative_max_m']:.3f} m",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9.5,
        bbox=dict(boxstyle="round,pad=0.30", facecolor="white", edgecolor="#bbbbbb", alpha=0.93),
    )
    ax.legend(loc="upper right", frameon=True)
    fig.tight_layout()

    out_path = out_dir / FIGURE_FILES[fig_no]
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return out_path


def format_anchor_table(anchors: np.ndarray) -> str:
    return "\n".join([f"  - A{i}: ({x:.2f}, {y:.2f})" for i, (x, y) in enumerate(anchors)])


def format_metrics(name: str, metrics: Dict[str, float]) -> str:
    lines = [f"### {name}"]
    for key, value in metrics.items():
        lines.append(f"- `{key}`: {value:.6f}")
    return "\n".join(lines)


def write_run_info(
    out_dir: Path,
    src: Path,
    data: LongCorridorData,
    baseline: MethodResult,
    proposed: MethodResult,
    generated: Sequence[Path],
) -> Path:
    info_path = out_dir / "long_corridor_run_info.md"
    lines = [
        "# Long Corridor Patent Figures Run Info",
        "",
        f"- Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"- Source optimizer script: `{src}`",
        f"- Supplemental scene: `{SCENE_NAME}`",
        f"- Version source: `sim2d_mvp_3.2.3.py` reusable optimizer APIs",
        f"- Main random seed: `{SEED_LONG_CORRIDOR}`",
        f"- Visibility seeds: Robot1 `{SEED_VIS_R1}`, Robot2 `{SEED_VIS_R2}`",
        f"- UWB LOS seeds: Robot1 `{SEED_UWB_LOS_R1}`, Robot2 `{SEED_UWB_LOS_R2}`",
        f"- Number of steps: `{NUM_STEPS}`",
        f"- Long-corridor solver budgets: baseline `{BASELINE_MAX_NFEV}`, stage-0 `{STAGE0_MAX_NFEV_LONG}`, stage-2 `{STAGE2_MAX_NFEV_LONG}`",
        f"- Robot1 odometry degradation windows: `{LIO_DEGRADE_WINDOWS}`",
        "- UWB mode: LOS, partial visible anchors, no NLOS injection",
        "- Baseline: odometry-only, no UWB factors, no Robot2 prior, no reliability state",
        "- Proposed: Stage-0 + diagnostic reliability + graph-internal reliability state + sqrt-count UWB prior balance",
        "- Relative error definition: `e_rel(k)=||(p2_est(k)-p1_est(k))-(p2_gt(k)-p1_gt(k))||_2`",
        "",
        "## Anchors",
        "",
        format_anchor_table(data.anchors),
        "",
        "## Visibility Counts",
        "",
        f"- Robot1 min/mean/max: {np.min(data.visibility_counts1):.0f}/{np.mean(data.visibility_counts1):.2f}/{np.max(data.visibility_counts1):.0f}",
        f"- Robot2 min/mean/max: {np.min(data.visibility_counts2):.0f}/{np.mean(data.visibility_counts2):.2f}/{np.max(data.visibility_counts2):.0f}",
        "",
        "## Metrics",
        "",
        format_metrics("Fig. 4/6 odometry-only baseline", baseline.metrics),
        "",
        format_metrics("Fig. 5/7 proposed method", proposed.metrics),
        "",
        "## Generated Files",
        "",
    ]
    for path in generated:
        lines.append(f"- `{path}`")

    info_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return info_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成专利长走廊补充仿真图4-图7")
    parser.add_argument("--src", type=str, default="sim2d_mvp_3.2.3.py", help="3.2.3 主脚本路径")
    parser.add_argument("--out-dir", type=str, default="figs/patent_figures", help="专利附图输出目录")
    parser.add_argument("--dpi", type=int, default=300, help="输出 DPI")
    parser.add_argument("--quiet", action="store_true", help="隐藏求解器详细输出")
    parser.add_argument("--solver-verbose", type=int, default=None, help="覆盖 scipy least_squares verbose 参数")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_matplotlib()

    src = Path(args.src).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    mod = load_module(src)
    solver_verbose = 0 if args.quiet else 1
    if args.solver_verbose is not None:
        solver_verbose = args.solver_verbose

    data = generate_long_corridor_data(mod)
    baseline = solve_odom_baseline(mod, data, solver_verbose=solver_verbose)
    proposed = solve_proposed_method(mod, data, solver_verbose=solver_verbose)

    generated: List[Path] = []
    generated.append(draw_trajectory_figure(4, data, baseline, out_dir, args.dpi))
    generated.append(draw_trajectory_figure(5, data, proposed, out_dir, args.dpi))
    generated.append(draw_error_figure(6, baseline, out_dir, args.dpi))
    generated.append(draw_error_figure(7, proposed, out_dir, args.dpi))
    info_path = write_run_info(out_dir, src, data, baseline, proposed, generated)

    print("[Long Corridor Patent Figures] 已生成:")
    for path in generated:
        print(f"  {path}")
    print(f"  {info_path}")
    print("[Long Corridor Patent Figures] 图4-图7使用同一长走廊真值、锚点、随机种子和退化窗口。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
