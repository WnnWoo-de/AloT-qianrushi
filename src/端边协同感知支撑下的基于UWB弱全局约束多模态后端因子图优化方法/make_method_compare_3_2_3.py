#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于 sim2d_mvp_3.2.3.py 生成“单场景三方案对照图”。

设计目标：
1. 固定单一场景（默认 mixed_all）；
2. 固定同一条真值轨迹、同一套 visibility realization、同一套 NLOS realization；
3. 仅改变后端方法：
   - 基础：2.0（NLOS，无鲁棒）
   - 常规鲁棒：2.1（UWB Huber）
   - 当前方案：3.2.3（方法学对应 3.2.1 正式版的工程重构版）
4. 直接输出论文/汇报可用的 1×3 对照图，共用总图例和统一标题。

默认用法：
python3 make_method_compare_3_2_3.py \
    --src ./sim2d_mvp_3.2.3.py \
    --out ./figs/method_compare_mixed_all_2_0_2_1_3_2_3.png
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from scipy.optimize import least_squares


DEFAULT_SCENE = "mixed_all"


@dataclass
class SharedProblem:
    scene: str
    anchors: np.ndarray
    gt1: np.ndarray
    gt2: np.ndarray
    init1: np.ndarray
    init2: np.ndarray
    odom1: np.ndarray
    odom2: np.ndarray
    uwb1: list
    uwb2: list
    N1: int
    N2: int
    use_uwb: bool
    use_robot2_prior: bool
    prior2_for_opt: np.ndarray | None
    sigma_prior2_xy: float
    sigma_prior2_yaw: float
    baseline_mode: str
    effective_uwb_error_mode: str
    anchor_visibility_mode: str


@dataclass
class MethodResult:
    method_key: str
    method_title: str
    est1: np.ndarray
    est2: np.ndarray
    metrics: Dict[str, float]


def load_module(py_path: Path):
    if not py_path.exists():
        raise FileNotFoundError(f"找不到源脚本: {py_path}")

    spec = importlib.util.spec_from_file_location("sim2d_mvp_3_2_3_mod", str(py_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载模块: {py_path}")

    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成单场景三方案对照图（2.0 / 2.1 / 3.2.3）")
    parser.add_argument("--src", type=str, default="sim2d_mvp_3.2.3.py", help="3.2.3 主脚本路径")
    parser.add_argument("--scene", type=str, default=DEFAULT_SCENE, help="固定场景，默认 mixed_all")
    parser.add_argument(
        "--out",
        type=str,
        default="figs/method_compare_mixed_all_2_0_2_1_3_2_3.png",
        help="输出图片路径",
    )
    parser.add_argument(
        "--huber-delta",
        type=float,
        default=1.0,
        help="2.1 中 UWB Huber 的阈值 delta，默认 1.0（白化残差尺度）",
    )
    parser.add_argument(
        "--no-metrics-box",
        action="store_true",
        help="不显示每个子图右下角的 RMSE 文本框",
    )
    parser.add_argument("--nfev-20", type=int, default=4, help="2.0 最大函数评估次数，默认 4")
    parser.add_argument("--nfev-21", type=int, default=4, help="2.1 最大函数评估次数，默认 4")
    parser.add_argument("--stage0-nfev-cur", type=int, default=4, help="当前方案 stage-0 最大函数评估次数，默认 4")
    parser.add_argument("--stage2-nfev-cur", type=int, default=6, help="当前方案 stage-2 最大函数评估次数，默认 6")
    return parser.parse_args()


def setup_baseline_mode(mod) -> Tuple[bool, bool, np.ndarray | None, float, float, str]:
    if mod.BASELINE_MODE == "odom_only":
        use_uwb = False
        use_robot2_prior = False
        prior2_for_opt = None
        sigma_prior2_xy = mod.SIGMA_WEAK_PRIOR2_XY
        sigma_prior2_yaw = mod.SIGMA_WEAK_PRIOR2_YAW
        anchor_visibility_mode = "all"

    elif mod.BASELINE_MODE == "dual_prior_all_anchors":
        use_uwb = True
        use_robot2_prior = True
        prior2_for_opt = None
        sigma_prior2_xy = mod.SIGMA_PRIOR_XY
        sigma_prior2_yaw = mod.SIGMA_PRIOR_YAW
        anchor_visibility_mode = "all"

    elif mod.BASELINE_MODE == "single_prior_all_anchors":
        use_uwb = True
        use_robot2_prior = mod.USE_ROBOT2_WEAK_PRIOR
        prior2_for_opt = mod.ROBOT2_INIT_GUESS if mod.USE_ROBOT2_WEAK_PRIOR else None
        sigma_prior2_xy = mod.SIGMA_WEAK_PRIOR2_XY
        sigma_prior2_yaw = mod.SIGMA_WEAK_PRIOR2_YAW
        anchor_visibility_mode = "all"

    elif mod.BASELINE_MODE == "single_prior_partial_anchors":
        use_uwb = True
        use_robot2_prior = mod.USE_ROBOT2_WEAK_PRIOR
        prior2_for_opt = mod.ROBOT2_INIT_GUESS if mod.USE_ROBOT2_WEAK_PRIOR else None
        sigma_prior2_xy = mod.SIGMA_WEAK_PRIOR2_XY
        sigma_prior2_yaw = mod.SIGMA_WEAK_PRIOR2_YAW
        anchor_visibility_mode = "partial_random"

    else:
        raise ValueError(f"Unknown BASELINE_MODE: {mod.BASELINE_MODE}")

    if mod.FORCE_USE_UWB is not None:
        use_uwb = mod.FORCE_USE_UWB

    return (
        use_uwb,
        use_robot2_prior,
        prior2_for_opt,
        sigma_prior2_xy,
        sigma_prior2_yaw,
        anchor_visibility_mode,
    )


def generate_shared_problem(mod, scene: str) -> SharedProblem:
    original_case = mod.DEGRADATION_CASE
    try:
        mod.DEGRADATION_CASE = scene
        np.random.seed(mod.SEED_MAIN)

        (
            use_uwb,
            use_robot2_prior,
            prior2_for_opt,
            sigma_prior2_xy,
            sigma_prior2_yaw,
            anchor_visibility_mode,
        ) = setup_baseline_mode(mod)

        effective_uwb_error_mode, lio_windows, rtab_windows = mod.configure_degradation_case()

        anchors = mod.ANCHORS.copy()
        N1 = mod.NUM_STEPS_1
        N2 = mod.NUM_STEPS_2

        gt1 = mod.generate_truth_traj(
            center_x=mod.GT1_CENTER_X,
            center_y=mod.GT1_CENTER_Y,
            radius_x=mod.GT1_RADIUS_X,
            radius_y=mod.GT1_RADIUS_Y,
            phase=mod.GT1_PHASE,
            N=N1,
        )
        gt2 = mod.generate_truth_traj(
            center_x=mod.GT2_CENTER_X,
            center_y=mod.GT2_CENTER_Y,
            radius_x=mod.GT2_RADIUS_X,
            radius_y=mod.GT2_RADIUS_Y,
            phase=mod.GT2_PHASE,
            N=N2,
        )

        lio_sigma_scale = mod.fill_windows_scale(N1 - 1, lio_windows, 1.0, mod.LIO_SIGMA_SCALE_DEG)
        lio_bias_scale = mod.fill_windows_scale(N1 - 1, lio_windows, 1.0, mod.LIO_BIAS_SCALE_DEG)
        rtab_sigma_scale = mod.fill_windows_scale(N2 - 1, rtab_windows, 1.0, mod.RTAB_SIGMA_SCALE_DEG)
        rtab_bias_scale = mod.fill_windows_scale(N2 - 1, rtab_windows, 1.0, mod.RTAB_BIAS_SCALE_DEG)

        odom1 = mod.simulate_odom(
            gt1,
            sigma_xy=mod.ODOM1_SIGMA_XY,
            sigma_yaw=mod.ODOM1_SIGMA_YAW,
            bias_xy=mod.ODOM1_BIAS_XY,
            bias_yaw=mod.ODOM1_BIAS_YAW,
            sigma_scale_series=lio_sigma_scale,
            bias_scale_series=lio_bias_scale,
        )
        odom2 = mod.simulate_odom(
            gt2,
            sigma_xy=mod.ODOM2_SIGMA_XY,
            sigma_yaw=mod.ODOM2_SIGMA_YAW,
            bias_xy=mod.ODOM2_BIAS_XY,
            bias_yaw=mod.ODOM2_BIAS_YAW,
            sigma_scale_series=rtab_sigma_scale,
            bias_scale_series=rtab_bias_scale,
        )

        if use_uwb:
            vis_sched1 = mod.generate_visibility_schedule(
                num_steps=len(gt1),
                num_anchors=len(anchors),
                visibility_mode=anchor_visibility_mode,
                min_visible=mod.MIN_VISIBLE_ANCHORS,
                max_visible=mod.MAX_VISIBLE_ANCHORS,
                rng_vis=np.random.default_rng(mod.SEED_VIS_R1),
            )
            vis_sched2 = mod.generate_visibility_schedule(
                num_steps=len(gt2),
                num_anchors=len(anchors),
                visibility_mode=anchor_visibility_mode,
                min_visible=mod.MIN_VISIBLE_ANCHORS,
                max_visible=mod.MAX_VISIBLE_ANCHORS,
                rng_vis=np.random.default_rng(mod.SEED_VIS_R2),
            )

            uwb1 = mod.simulate_uwb(
                gt1,
                anchors,
                sigma_r=mod.UWB_SIGMA_R,
                error_mode=effective_uwb_error_mode,
                nlos_prob=mod.NLOS_PROB,
                nlos_bias_mean=mod.NLOS_BIAS_MEAN,
                nlos_bias_std=mod.NLOS_BIAS_STD,
                nlos_bias_min=mod.NLOS_BIAS_MIN,
                nlos_bias_max=mod.NLOS_BIAS_MAX,
                visible_ids_per_step=vis_sched1,
                rng_los=np.random.default_rng(mod.SEED_UWB_LOS_R1),
                rng_nlos=np.random.default_rng(mod.SEED_UWB_NLOS_R1),
            )
            uwb2 = mod.simulate_uwb(
                gt2,
                anchors,
                sigma_r=mod.UWB_SIGMA_R,
                error_mode=effective_uwb_error_mode,
                nlos_prob=mod.NLOS_PROB,
                nlos_bias_mean=mod.NLOS_BIAS_MEAN,
                nlos_bias_std=mod.NLOS_BIAS_STD,
                nlos_bias_min=mod.NLOS_BIAS_MIN,
                nlos_bias_max=mod.NLOS_BIAS_MAX,
                visible_ids_per_step=vis_sched2,
                rng_los=np.random.default_rng(mod.SEED_UWB_LOS_R2),
                rng_nlos=np.random.default_rng(mod.SEED_UWB_NLOS_R2),
            )
        else:
            uwb1, uwb2 = [], []

        init1 = mod.integrate_odom(odom1, gt1[0].copy())
        if mod.BASELINE_MODE == "dual_prior_all_anchors":
            init2 = mod.integrate_odom(odom2, gt2[0].copy())
        else:
            init2 = mod.integrate_odom(odom2, mod.ROBOT2_INIT_GUESS.copy())

        return SharedProblem(
            scene=scene,
            anchors=anchors,
            gt1=gt1,
            gt2=gt2,
            init1=init1,
            init2=init2,
            odom1=odom1,
            odom2=odom2,
            uwb1=uwb1,
            uwb2=uwb2,
            N1=N1,
            N2=N2,
            use_uwb=use_uwb,
            use_robot2_prior=use_robot2_prior,
            prior2_for_opt=prior2_for_opt,
            sigma_prior2_xy=sigma_prior2_xy,
            sigma_prior2_yaw=sigma_prior2_yaw,
            baseline_mode=mod.BASELINE_MODE,
            effective_uwb_error_mode=effective_uwb_error_mode,
            anchor_visibility_mode=anchor_visibility_mode,
        )
    finally:
        mod.DEGRADATION_CASE = original_case


def compute_metrics(gt1: np.ndarray, gt2: np.ndarray, est1: np.ndarray, est2: np.ndarray) -> Dict[str, float]:
    rmse1 = float(np.sqrt(np.mean(np.sum((est1[:, :2] - gt1[:, :2]) ** 2, axis=1))))
    rmse2 = float(np.sqrt(np.mean(np.sum((est2[:, :2] - gt2[:, :2]) ** 2, axis=1))))
    return {"est_rmse1": rmse1, "est_rmse2": rmse2}


def build_problem_residual_linear(mod, problem: SharedProblem):
    prior2 = problem.prior2_for_opt
    if problem.baseline_mode == "dual_prior_all_anchors":
        prior2 = problem.gt2[0]

    return mod.build_residual_function(
        N1=problem.N1,
        N2=problem.N2,
        odom1=problem.odom1,
        odom2=problem.odom2,
        uwb1=problem.uwb1,
        uwb2=problem.uwb2,
        anchors=problem.anchors,
        prior1=problem.gt1[0],
        prior2=prior2,
        use_robot2_prior=problem.use_robot2_prior,
        use_uwb=problem.use_uwb,
        sigma_prior_xy=mod.SIGMA_PRIOR_XY,
        sigma_prior_yaw=mod.SIGMA_PRIOR_YAW,
        sigma_prior2_xy=problem.sigma_prior2_xy,
        sigma_prior2_yaw=problem.sigma_prior2_yaw,
        sigma_odom_xy=mod.SIGMA_ODOM_XY,
        sigma_odom_yaw=mod.SIGMA_ODOM_YAW,
        sigma_uwb=mod.SIGMA_UWB,
        s_lio=np.ones(problem.N1 - 1),
        s_rtab=np.ones(problem.N2 - 1),
        s_uwb1=np.ones(problem.N1),
        s_uwb2=np.ones(problem.N2),
        use_reliability_weighting=False,
        reliability_floor=mod.RELIABILITY_FLOOR,
    )


def huber_equivalent_residual_scalar(r: float, delta: float) -> float:
    a = abs(r)
    if a <= delta:
        return r
    return float(np.sign(r) * np.sqrt(2.0 * delta * (a - 0.5 * delta)))


def build_problem_residual_huber_uwb(mod, problem: SharedProblem, delta: float):
    w_prior_xy = 1.0 / mod.SIGMA_PRIOR_XY
    w_prior_yaw = 1.0 / mod.SIGMA_PRIOR_YAW
    w_prior2_xy = 1.0 / problem.sigma_prior2_xy
    w_prior2_yaw = 1.0 / problem.sigma_prior2_yaw
    w_odom_xy = 1.0 / mod.SIGMA_ODOM_XY
    w_odom_yaw = 1.0 / mod.SIGMA_ODOM_YAW
    w_uwb = 1.0 / mod.SIGMA_UWB

    prior2 = problem.prior2_for_opt
    if problem.baseline_mode == "dual_prior_all_anchors":
        prior2 = problem.gt2[0]

    def residual(x):
        traj1, traj2 = mod.unpack_states(x, problem.N1, problem.N2)
        res = []

        e1 = traj1[0] - problem.gt1[0]
        e1[2] = mod.wrap_angle(e1[2])
        res.extend([w_prior_xy * e1[0], w_prior_xy * e1[1], w_prior_yaw * e1[2]])

        if problem.use_robot2_prior and (prior2 is not None):
            e2 = traj2[0] - prior2
            e2[2] = mod.wrap_angle(e2[2])
            res.extend([w_prior2_xy * e2[0], w_prior2_xy * e2[1], w_prior2_yaw * e2[2]])

        for k in range(problem.N1 - 1):
            pred = mod.relative_pose(traj1[k], traj1[k + 1])
            err = pred - problem.odom1[k]
            err[2] = mod.wrap_angle(err[2])
            res.extend([w_odom_xy * err[0], w_odom_xy * err[1], w_odom_yaw * err[2]])

        for k in range(problem.N2 - 1):
            pred = mod.relative_pose(traj2[k], traj2[k + 1])
            err = pred - problem.odom2[k]
            err[2] = mod.wrap_angle(err[2])
            res.extend([w_odom_xy * err[0], w_odom_xy * err[1], w_odom_yaw * err[2]])

        if problem.use_uwb:
            for meas in problem.uwb1:
                k, m, r_meas = meas[:3]
                px, py, _ = traj1[k]
                r_pred = np.linalg.norm(np.array([px, py]) - problem.anchors[m])
                e = w_uwb * (r_pred - r_meas)
                res.append(huber_equivalent_residual_scalar(float(e), delta))

            for meas in problem.uwb2:
                k, m, r_meas = meas[:3]
                px, py, _ = traj2[k]
                r_pred = np.linalg.norm(np.array([px, py]) - problem.anchors[m])
                e = w_uwb * (r_pred - r_meas)
                res.append(huber_equivalent_residual_scalar(float(e), delta))

        return np.array(res, dtype=float)

    return residual


def solve_method_2_0(mod, problem: SharedProblem, max_nfev: int) -> MethodResult:
    x0 = mod.pack_states(problem.init1, problem.init2)
    residual_fn = build_problem_residual_linear(mod, problem)
    result = least_squares(
        residual_fn,
        x0,
        verbose=0,
        max_nfev=max_nfev,
        loss="linear",
    )
    est1, est2 = mod.unpack_states(result.x, problem.N1, problem.N2)
    return MethodResult(
        method_key="2.0",
        method_title="Baseline: 2.0",
        est1=est1,
        est2=est2,
        metrics=compute_metrics(problem.gt1, problem.gt2, est1, est2),
    )


def solve_method_2_1(mod, problem: SharedProblem, huber_delta: float, max_nfev: int) -> MethodResult:
    x0 = mod.pack_states(problem.init1, problem.init2)
    residual_fn = build_problem_residual_huber_uwb(mod, problem, delta=huber_delta)
    result = least_squares(
        residual_fn,
        x0,
        verbose=0,
        max_nfev=max_nfev,
        loss="linear",
    )
    est1, est2 = mod.unpack_states(result.x, problem.N1, problem.N2)
    return MethodResult(
        method_key="2.1",
        method_title="Conventional Robust: 2.1 Huber",
        est1=est1,
        est2=est2,
        metrics=compute_metrics(problem.gt1, problem.gt2, est1, est2),
    )


def solve_method_3_2_3(mod, scene: str, stage0_max_nfev: int, stage2_max_nfev: int) -> MethodResult:
    old_stage0 = getattr(mod, "STAGE0_MAX_NFEV", None)
    old_stage2 = getattr(mod, "STAGE2_MAX_NFEV", None)
    try:
        mod.STAGE0_MAX_NFEV = stage0_max_nfev
        mod.STAGE2_MAX_NFEV = stage2_max_nfev
        result = mod.run_case(
        case_name=scene,
        show=False,
        save_fig=False,
        return_dict=True,
        solver_verbose=0,
    )
        return MethodResult(
        method_key="3.2.3",
        method_title="Current Method: 3.2.3",
        est1=result["est1"],
        est2=result["est2"],
        metrics=result["metrics"],
    )
    finally:
        if old_stage0 is not None:
            mod.STAGE0_MAX_NFEV = old_stage0
        if old_stage2 is not None:
            mod.STAGE2_MAX_NFEV = old_stage2


def compute_axis_limits(problem: SharedProblem, method_results: Dict[str, MethodResult]):
    xs = [problem.anchors[:, 0], problem.gt1[:, 0], problem.gt2[:, 0], problem.init1[:, 0], problem.init2[:, 0]]
    ys = [problem.anchors[:, 1], problem.gt1[:, 1], problem.gt2[:, 1], problem.init1[:, 1], problem.init2[:, 1]]
    for res in method_results.values():
        xs.extend([res.est1[:, 0], res.est2[:, 0]])
        ys.extend([res.est1[:, 1], res.est2[:, 1]])

    xmin = min(np.min(v) for v in xs)
    xmax = max(np.max(v) for v in xs)
    ymin = min(np.min(v) for v in ys)
    ymax = max(np.max(v) for v in ys)

    dx = xmax - xmin
    dy = ymax - ymin
    pad_x = max(0.5, 0.08 * dx)
    pad_y = max(0.5, 0.08 * dy)
    return (xmin - pad_x, xmax + pad_x), (ymin - pad_y, ymax + pad_y)


def add_metrics_box(ax, res: MethodResult):
    text = f"R1 RMSE = {res.metrics['est_rmse1']:.3f} m\nR2 RMSE = {res.metrics['est_rmse2']:.3f} m"
    ax.text(
        0.98,
        0.03,
        text,
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=10,
        bbox=dict(boxstyle="round,pad=0.25", facecolor="white", alpha=0.88, edgecolor="0.6"),
    )


def make_figure(
    problem: SharedProblem,
    method_results: Dict[str, MethodResult],
    out_path: Path,
    show_metrics_box: bool,
):
    fig, axes = plt.subplots(1, 3, figsize=(16.5, 5.6), constrained_layout=False)
    method_order = ["2.0", "2.1", "3.2.3"]
    (xlim_l, xlim_r), (ylim_l, ylim_r) = compute_axis_limits(problem, method_results)

    for idx, method_key in enumerate(method_order):
        ax = axes[idx]
        res = method_results[method_key]

        ax.scatter(problem.anchors[:, 0], problem.anchors[:, 1], marker="s", s=60, c="k", alpha=0.85)
        ax.plot(problem.gt1[:, 0], problem.gt1[:, 1], "g-", linewidth=1.8)
        ax.plot(problem.gt2[:, 0], problem.gt2[:, 1], "b-", linewidth=1.8)
        ax.plot(problem.init1[:, 0], problem.init1[:, 1], "g--", linewidth=1.3, alpha=0.75)
        ax.plot(problem.init2[:, 0], problem.init2[:, 1], "b--", linewidth=1.3, alpha=0.75)
        ax.plot(res.est1[:, 0], res.est1[:, 1], "r-", linewidth=2.2)
        ax.plot(res.est2[:, 0], res.est2[:, 1], "m-", linewidth=2.2)

        ax.set_title(res.method_title, fontsize=13)
        ax.set_xlim(xlim_l, xlim_r)
        ax.set_ylim(ylim_l, ylim_r)
        ax.set_aspect("equal", adjustable="box")
        ax.grid(True, alpha=0.3)
        ax.set_xlabel("x [m]")
        if idx == 0:
            ax.set_ylabel("y [m]")
        else:
            ax.set_ylabel("")

        if show_metrics_box:
            add_metrics_box(ax, res)

    legend_handles = [
        Line2D([0], [0], marker="s", color="k", linestyle="None", markersize=8, label="Anchors"),
        Line2D([0], [0], color="g", linewidth=1.8, label="GT Robot1"),
        Line2D([0], [0], color="b", linewidth=1.8, label="GT Robot2"),
        Line2D([0], [0], color="g", linestyle="--", linewidth=1.3, label="Init Robot1"),
        Line2D([0], [0], color="b", linestyle="--", linewidth=1.3, label="Init Robot2"),
        Line2D([0], [0], color="r", linewidth=2.2, label="Estimated Robot1"),
        Line2D([0], [0], color="m", linewidth=2.2, label="Estimated Robot2"),
    ]

    fig.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.99),
        ncol=7,
        frameon=False,
        fontsize=10,
    )

    fig.suptitle(
        "Single-Scene Comparison: fixed scene = {problem.scene}, only method changes",
        y=0.890,
        fontsize=15,
    )
    fig.text(
        0.5,
        0.925,
        "Same ground-truth trajectories / same visibility realization / same NLOS realization",
        ha="center",
        va="center",
        fontsize=11,
    )

    fig.subplots_adjust(top=0.82, wspace=0.18, left=0.055, right=0.99, bottom=0.11)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    args = parse_args()
    src = Path(args.src).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()

    mod = load_module(src)

    # 减少内部冗余打印，避免 run_case 输出过多中间统计
    if hasattr(mod, "PRINT_STAGE0_RMSE"):
        mod.PRINT_STAGE0_RMSE = False
    if hasattr(mod, "PRINT_STAGE2_STATE_STATS"):
        mod.PRINT_STAGE2_STATE_STATS = False
    mod.plt.show = lambda *a, **k: None

    old_cwd = Path.cwd()
    try:
        os.chdir(src.parent)

        problem = generate_shared_problem(mod, args.scene)
        if args.scene != "mixed_all":
            print(f"[Warning] 你当前固定场景不是 mixed_all，而是 {args.scene}")

        print(f"[Compare] 生成共享问题实例: scene = {problem.scene}")
        print(f"[Compare] visibility_mode = {problem.anchor_visibility_mode}, uwb_error_mode = {problem.effective_uwb_error_mode}")

        res_20 = solve_method_2_0(mod, problem, max_nfev=args.nfev_20)
        print(f"[Compare] 2.0 done: R1={res_20.metrics['est_rmse1']:.4f}, R2={res_20.metrics['est_rmse2']:.4f}")

        res_21 = solve_method_2_1(mod, problem, huber_delta=args.huber_delta, max_nfev=args.nfev_21)
        print(f"[Compare] 2.1 done: R1={res_21.metrics['est_rmse1']:.4f}, R2={res_21.metrics['est_rmse2']:.4f}")

        res_323 = solve_method_3_2_3(mod, args.scene, stage0_max_nfev=args.stage0_nfev_cur, stage2_max_nfev=args.stage2_nfev_cur)
        print(f"[Compare] 3.2.3 done: R1={res_323.metrics['est_rmse1']:.4f}, R2={res_323.metrics['est_rmse2']:.4f}")

        method_results = {"2.0": res_20, "2.1": res_21, "3.2.3": res_323}
        make_figure(problem, method_results, out, show_metrics_box=(not args.no_metrics_box))
        print(f"[Compare] 图已保存: {out}")
    finally:
        os.chdir(old_cwd)

    return 0


if __name__ == "__main__":
    sys.exit(main())
