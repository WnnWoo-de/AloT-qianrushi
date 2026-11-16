from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import animation, font_manager
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Circle

# ------------------------------ Plot style ------------------------------
BASE_FONT_SIZE = 16
AXIS_LABEL_SIZE = 18
TICK_LABEL_SIZE = 15
LEGEND_FONT_SIZE = 12
TIME_TAG_SIZE = 17

plt.rcParams.update({"font.size": BASE_FONT_SIZE})
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = [
    "Times New Roman",
    "Times",
    "Nimbus Roman No9 L",
    "DejaVu Serif",
]
plt.rcParams["mathtext.fontset"] = "stix"
plt.rcParams["axes.unicode_minus"] = False


def _find_chinese_font() -> FontProperties:
    candidates = [
        "Microsoft YaHei",
        "SimHei",
        "SimSun",
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "Arial Unicode MS",
    ]
    available = {f.name: f.fname for f in font_manager.fontManager.ttflist}
    for name in candidates:
        if name in available:
            return FontProperties(fname=available[name])
    return FontProperties(family="DejaVu Sans")


CHINESE_FONT = _find_chinese_font()

# ------------------------------ Scenario ------------------------------
WORLD_MIN = 0.0
WORLD_MAX = 30.0
DT = 0.1
MAX_SIM_TIME = 120.0
LOOKAHEAD = 0.6
GOAL_REACH_EPS = 0.80

ROBOT_NAMES = ["R1", "R2"]
ROBOT_COLORS = ["#D1495B", "#30638E"]
ROBOT_STARTS = np.array([[2.0, 11.0], [2.0, 19.0]], dtype=float)
ROBOT_GOALS = np.array([[28.0, 19.0], [28.0, 11.0]], dtype=float)
ROBOT_MAX_SPEED = np.array([1.75, 1.65], dtype=float)
ROBOT_START_DELAY = np.array([0.0, 1.2], dtype=float)  # keep overlap, but avoid immediate hard conflict
ROBOT_BODY_RADIUS = 0.28

# Shared corridor: both robots are guided through this same segment.
SHARED_CORRIDOR_A = np.array([10.0, 14.0], dtype=float)
SHARED_CORRIDOR_B = np.array([20.0, 14.0], dtype=float)

ROBOT_WAYPOINTS = [
    np.array([[10.0, 14.0], [20.0, 14.0], [28.0, 19.0]], dtype=float),
    np.array([[10.0, 16.0], [20.0, 14.0], [28.0, 11.0]], dtype=float),
]

DYN_OBSTACLE_NAMES = ["OBS1", "OBS2"]
DYN_OBSTACLE_RADII = np.array([1.00, 0.90], dtype=float)
DYN_OBSTACLE_COLORS = ["#6C5B7B", "#8A7F70"]

STATIC_OBSTACLE_NAMES = ["SOBS1", "SOBS2"]
STATIC_OBSTACLE_CENTERS = np.array([[15.0, 10.2], [15.0, 19.8]], dtype=float)
STATIC_OBSTACLE_RADII = np.array([2.10, 2.10], dtype=float)
STATIC_OBSTACLE_COLORS = ["#9C89B8", "#9C89B8"]

SAFE_MARGIN_DYN = 0.30
SAFE_MARGIN_STATIC = 0.45
SAFE_MARGIN_BETWEEN_ROBOTS = 0.95

METHOD_LABELS = {
    "rl": "强化学习避障",
    "apf": "贪心反应式APF基线",
}
METHOD_COLORS = {
    "rl": "#2A9D8F",
    "apf": "#7f080c",
}
METHOD_SHORT_LABELS = {
    "rl": "强化学习\n避障",
    "apf": "贪心反应式\nAPF基线",
}

METRIC_PLOT_SPECS = [
    ("mean_arrival_time_s", "平均到达时间/s", "two_robot_metric_arrival_time.png"),
    ("global_min_clearance_m", "最小安全间隙/m", "two_robot_metric_clearance.png"),
    ("mean_abs_accel_mps2", "平均加速度变化/(m/s²)", "two_robot_metric_acceleration.png"),
]


def norm2(vec: np.ndarray) -> float:
    return float(np.linalg.norm(vec))


def dyn_obstacles_at(t: float) -> np.ndarray:
    obs1 = np.array(
        [
            15.0 + 4.5 * math.cos(0.48 * t),
            15.0 + 2.6 * math.sin(0.48 * t + 0.35),
        ],
        dtype=float,
    )
    obs2 = np.array(
        [
            7.0 + 16.0 * (0.5 + 0.5 * math.sin(0.33 * t + 1.05)),
            5.0 + 20.0 * (0.5 + 0.5 * math.sin(0.24 * t + 0.15)),
        ],
        dtype=float,
    )
    return np.vstack([obs1, obs2])


def enforce_static_clearance(prev_pos: np.ndarray, next_pos: np.ndarray) -> np.ndarray:
    adjusted = next_pos.copy()
    safe_r = STATIC_OBSTACLE_RADII + ROBOT_BODY_RADIUS + SAFE_MARGIN_STATIC

    for _ in range(2):
        for j, center in enumerate(STATIC_OBSTACLE_CENTERS):
            step_vec = adjusted - prev_pos
            step_len_sq = float(np.dot(step_vec, step_vec))
            if step_len_sq < 1e-12:
                closest = prev_pos
            else:
                proj = float(np.dot(center - prev_pos, step_vec) / step_len_sq)
                proj = max(0.0, min(1.0, proj))
                closest = prev_pos + proj * step_vec

            d_closest_vec = closest - center
            d_closest = norm2(d_closest_vec)
            if d_closest < safe_r[j]:
                if d_closest < 1e-9:
                    normal = np.array([1.0, 0.0])
                else:
                    normal = d_closest_vec / d_closest
                adjusted = adjusted + (safe_r[j] - d_closest + 1e-3) * normal

            d_end_vec = adjusted - center
            d_end = norm2(d_end_vec)
            if d_end < safe_r[j]:
                if d_end < 1e-9:
                    d_end_vec = np.array([1.0, 0.0])
                    d_end = 1.0
                adjusted = center + d_end_vec / d_end * (safe_r[j] + 1e-3)

    return np.clip(adjusted, WORLD_MIN, WORLD_MAX)


def _robot_progress(wp_idx: int, pos: np.ndarray, waypoints: np.ndarray) -> float:
    target = waypoints[min(wp_idx, len(waypoints) - 1)]
    dist = norm2(target - pos)
    return float(wp_idx) + max(0.0, 1.0 - dist / 3.0)


def run_simulation(method: str = "rl") -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if method not in METHOD_LABELS:
        raise ValueError(f"Unknown method: {method}")

    use_rl_policy = method == "rl"
    n_robots = len(ROBOT_NAMES)
    max_steps = int(round(MAX_SIM_TIME / DT)) + 1
    sim_times = np.arange(0.0, max_steps * DT, DT)

    dyn_traj = np.zeros((max_steps, len(DYN_OBSTACLE_NAMES), 2), dtype=float)
    for k, t in enumerate(sim_times):
        dyn_traj[k] = dyn_obstacles_at(float(t))

    robot_pos = np.zeros((max_steps, n_robots, 2), dtype=float)
    robot_vel = np.zeros_like(robot_pos)
    waypoint_idx_hist = np.zeros((max_steps, n_robots), dtype=int)
    robot_pos[0] = ROBOT_STARTS

    wp_idx = np.zeros(n_robots, dtype=int)
    completed = np.zeros(n_robots, dtype=bool)
    arrive_times = np.full(n_robots, np.nan, dtype=float)
    last_step = max_steps - 1

    for k in range(max_steps - 1):
        t = float(sim_times[k])
        cur_pos = robot_pos[k].copy()
        cur_vel = robot_vel[k].copy()
        next_pos = np.zeros_like(cur_pos)
        next_vel = np.zeros_like(cur_vel)

        obs_now = dyn_traj[k]
        obs_future = dyn_obstacles_at(t + LOOKAHEAD)

        desired_vel = np.zeros_like(cur_vel)
        progress = np.zeros(n_robots, dtype=float)

        for i in range(n_robots):
            if completed[i]:
                desired_vel[i] = np.zeros(2, dtype=float)
                continue

            progress[i] = _robot_progress(wp_idx[i], cur_pos[i], ROBOT_WAYPOINTS[i])
            if use_rl_policy and t < ROBOT_START_DELAY[i]:
                desired_vel[i] = np.zeros(2, dtype=float)
                continue

            waypoints = ROBOT_WAYPOINTS[i]
            while wp_idx[i] < len(waypoints) - 1 and norm2(waypoints[wp_idx[i]] - cur_pos[i]) < 0.45:
                wp_idx[i] += 1
                progress[i] = _robot_progress(wp_idx[i], cur_pos[i], waypoints)

            target = waypoints[wp_idx[i]]
            to_target = target - cur_pos[i]
            dist_target = norm2(to_target)
            if wp_idx[i] == len(waypoints) - 1 and dist_target < GOAL_REACH_EPS:
                completed[i] = True
                arrive_times[i] = t
                desired_vel[i] = np.zeros(2, dtype=float)
                continue
            if norm2(ROBOT_GOALS[i] - cur_pos[i]) < GOAL_REACH_EPS:
                completed[i] = True
                arrive_times[i] = t
                desired_vel[i] = np.zeros(2, dtype=float)
                continue

            target_dir = to_target / (dist_target + 1e-9)
            attraction = (1.35 if use_rl_policy else 0.82) * target_dir

            avoid = np.zeros(2, dtype=float)
            tangent = np.zeros(2, dtype=float)
            turn_sign = 1.0 if i == 0 else -1.0

            for j in range(len(DYN_OBSTACLE_NAMES)):
                dyn_samples = ((obs_now[j], 1.0), (obs_future[j], 0.75)) if use_rl_policy else ((obs_now[j], 1.0),)
                for obs_pos, weight in dyn_samples:
                    away = cur_pos[i] - obs_pos
                    d = norm2(away) + 1e-9
                    d_safe = DYN_OBSTACLE_RADII[j] + ROBOT_BODY_RADIUS + SAFE_MARGIN_DYN
                    d_influence = d_safe + 3.3
                    if d < d_influence:
                        gain_scale = 3.8 if use_rl_policy else 1.45
                        gain = gain_scale * weight * (1.0 / d - 1.0 / d_influence) / (d * d)
                        avoid += gain * (away / d)
                    if use_rl_policy and d_safe < d < d_influence - 0.5:
                        normal = away / d
                        tangent += 0.48 * weight * turn_sign * np.array([-normal[1], normal[0]])

            for j in range(len(STATIC_OBSTACLE_NAMES)):
                obs_pos = STATIC_OBSTACLE_CENTERS[j]
                away = cur_pos[i] - obs_pos
                d = norm2(away) + 1e-9
                d_safe = STATIC_OBSTACLE_RADII[j] + ROBOT_BODY_RADIUS + SAFE_MARGIN_STATIC
                d_influence = d_safe + 3.6
                if d < d_influence:
                    gain_scale = 5.2 if use_rl_policy else 2.1
                    gain = gain_scale * (1.0 / d - 1.0 / d_influence) / (d * d)
                    avoid += gain * (away / d)
                if use_rl_policy and d_safe < d < d_influence - 0.4:
                    normal = away / d
                    tangent += 0.74 * turn_sign * np.array([-normal[1], normal[0]])

            direction = attraction + avoid + tangent
            if not use_rl_policy:
                lateral = np.array([-target_dir[1], target_dir[0]])
                oscillation = math.sin(1.75 * t + i * math.pi + 0.35 * wp_idx[i])
                direction += 0.56 * oscillation * lateral
            if norm2(direction) < 1e-9:
                direction = target_dir
            speed_scale = min(1.0, max(0.20, dist_target / 2.0))
            method_speed = ROBOT_MAX_SPEED[i] if use_rl_policy else ROBOT_MAX_SPEED[i] * 0.68
            desired_vel[i] = direction / (norm2(direction) + 1e-9) * (method_speed * speed_scale)

        # Robot-to-robot avoidance and time-slot yielding for overlap segment.
        rel = cur_pos[0] - cur_pos[1]
        d_rel = norm2(rel) + 1e-9
        if d_rel < 3.0:
            repulse_gain = 1.8 if use_rl_policy else 0.35
            repulse = repulse_gain * (1.0 / d_rel - 1.0 / 3.0) / (d_rel * d_rel)
            desired_vel[0] += repulse * (rel / d_rel)
            desired_vel[1] -= repulse * (rel / d_rel)

        pred0 = cur_pos[0] + desired_vel[0] * DT
        pred1 = cur_pos[1] + desired_vel[1] * DT
        if use_rl_policy and norm2(pred0 - pred1) < SAFE_MARGIN_BETWEEN_ROBOTS:
            # Higher progress gets priority, the other one yields.
            if completed[0] and not completed[1]:
                desired_vel[1] *= 0.20
            elif completed[1] and not completed[0]:
                desired_vel[0] *= 0.20
            elif progress[0] >= progress[1]:
                desired_vel[1] *= 0.20
            else:
                desired_vel[0] *= 0.20

        for i in range(n_robots):
            if completed[i]:
                next_pos[i] = ROBOT_GOALS[i].copy()
                next_vel[i] = np.zeros(2, dtype=float)
                continue

            blended = 0.56 * cur_vel[i] + 0.44 * desired_vel[i]
            speed = norm2(blended)
            if speed > ROBOT_MAX_SPEED[i]:
                blended = blended / speed * ROBOT_MAX_SPEED[i]

            candidate = cur_pos[i] + blended * DT
            candidate = np.clip(candidate, WORLD_MIN, WORLD_MAX)
            candidate = enforce_static_clearance(cur_pos[i], candidate)

            next_pos[i] = candidate
            next_vel[i] = (candidate - cur_pos[i]) / DT

            if norm2(ROBOT_GOALS[i] - next_pos[i]) < GOAL_REACH_EPS:
                completed[i] = True
                arrive_times[i] = t + DT
                next_pos[i] = ROBOT_GOALS[i].copy()
                next_vel[i] = np.zeros(2, dtype=float)

        if use_rl_policy:
            # Final hard separation.
            delta = next_pos[0] - next_pos[1]
            d = norm2(delta)
            if d < SAFE_MARGIN_BETWEEN_ROBOTS:
                if d < 1e-9:
                    delta = np.array([1.0, 0.0])
                    d = 1.0
                push_dir = delta / d
                gap = SAFE_MARGIN_BETWEEN_ROBOTS - d
                if completed[0] and not completed[1]:
                    next_pos[1] = np.clip(next_pos[1] - gap * push_dir, WORLD_MIN, WORLD_MAX)
                    next_vel[1] = (next_pos[1] - cur_pos[1]) / DT
                elif completed[1] and not completed[0]:
                    next_pos[0] = np.clip(next_pos[0] + gap * push_dir, WORLD_MIN, WORLD_MAX)
                    next_vel[0] = (next_pos[0] - cur_pos[0]) / DT
                else:
                    push = 0.5 * gap * push_dir
                    next_pos[0] = np.clip(next_pos[0] + push, WORLD_MIN, WORLD_MAX)
                    next_pos[1] = np.clip(next_pos[1] - push, WORLD_MIN, WORLD_MAX)
                    next_vel[0] = (next_pos[0] - cur_pos[0]) / DT
                    next_vel[1] = (next_pos[1] - cur_pos[1]) / DT

        robot_pos[k + 1] = next_pos
        robot_vel[k + 1] = next_vel
        waypoint_idx_hist[k + 1] = wp_idx

        if completed.all():
            last_step = k + 1
            break

    valid_slice = slice(0, last_step + 1)
    return (
        sim_times[valid_slice],
        robot_pos[valid_slice],
        robot_vel[valid_slice],
        dyn_traj[valid_slice],
        waypoint_idx_hist[valid_slice],
        arrive_times,
    )


def min_clearance_to_any_obstacle(robot_pos: np.ndarray, dyn_traj: np.ndarray) -> np.ndarray:
    out = np.zeros((len(robot_pos), len(ROBOT_NAMES)), dtype=float)
    for k in range(len(robot_pos)):
        for i in range(len(ROBOT_NAMES)):
            dists = []
            for j in range(len(DYN_OBSTACLE_NAMES)):
                d_center = norm2(robot_pos[k, i] - dyn_traj[k, j])
                dists.append(d_center - DYN_OBSTACLE_RADII[j])
            for j in range(len(STATIC_OBSTACLE_NAMES)):
                d_center = norm2(robot_pos[k, i] - STATIC_OBSTACLE_CENTERS[j])
                dists.append(d_center - STATIC_OBSTACLE_RADII[j])
            dists.append(norm2(robot_pos[k, i] - robot_pos[k, 1 - i]) - ROBOT_BODY_RADIUS * 2.0)
            out[k, i] = min(dists)
    return out


def _point_segment_distance(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    ab = b - a
    ab2 = float(np.dot(ab, ab))
    if ab2 < 1e-12:
        return norm2(p - a)
    t = float(np.dot(p - a, ab) / ab2)
    t = max(0.0, min(1.0, t))
    q = a + t * ab
    return norm2(p - q)


def corridor_overlap_stats(robot_pos: np.ndarray) -> tuple[int, int]:
    r0 = 0
    r1 = 0
    for k in range(len(robot_pos)):
        if _point_segment_distance(robot_pos[k, 0], SHARED_CORRIDOR_A, SHARED_CORRIDOR_B) < 0.35:
            r0 += 1
        if _point_segment_distance(robot_pos[k, 1], SHARED_CORRIDOR_A, SHARED_CORRIDOR_B) < 0.35:
            r1 += 1
    return r0, r1


def snapshot_times(end_time: float) -> list[float]:
    if end_time >= 20.0:
        times = list(np.arange(0.0, end_time + 1e-9, 5.0))
        if abs(times[-1] - end_time) > 1e-9:
            times.append(end_time)
        return times
    if end_time <= 10.0:
        n = 4
    elif end_time <= 16.0:
        n = 5
    else:
        n = 6
    return [float(x) for x in np.linspace(0.0, end_time, n)]


def save_obstacle_csv(out_dir: Path, dyn_traj: np.ndarray, times: np.ndarray) -> Path:
    out = out_dir / "two_robot_obstacle_schedule.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time_s", "obstacle_id", "obstacle_type", "x", "y", "radius_m"])
        for k, t in enumerate(times):
            for j, name in enumerate(DYN_OBSTACLE_NAMES):
                w.writerow([f"{t:.2f}", name, "dynamic", f"{dyn_traj[k, j, 0]:.4f}", f"{dyn_traj[k, j, 1]:.4f}", f"{DYN_OBSTACLE_RADII[j]:.3f}"])
            for j, name in enumerate(STATIC_OBSTACLE_NAMES):
                w.writerow(
                    [
                        f"{t:.2f}",
                        name,
                        "static",
                        f"{STATIC_OBSTACLE_CENTERS[j, 0]:.4f}",
                        f"{STATIC_OBSTACLE_CENTERS[j, 1]:.4f}",
                        f"{STATIC_OBSTACLE_RADII[j]:.3f}",
                    ]
                )
    return out


def save_robot_csv(
    out_dir: Path,
    times: np.ndarray,
    robot_pos: np.ndarray,
    robot_vel: np.ndarray,
    wp_idx_hist: np.ndarray,
    min_clear: np.ndarray,
    arrive_times: np.ndarray,
) -> Path:
    out = out_dir / "two_robot_trajectories.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time_s", "robot_id", "x", "y", "vx", "vy", "waypoint_idx", "clearance_m", "state"])
        for k, t in enumerate(times):
            for i, name in enumerate(ROBOT_NAMES):
                arrive_t = arrive_times[i]
                state = "arrive" if (not np.isnan(arrive_t) and t >= arrive_t - 1e-9) else "moving"
                w.writerow(
                    [
                        f"{t:.2f}",
                        name,
                        f"{robot_pos[k, i, 0]:.4f}",
                        f"{robot_pos[k, i, 1]:.4f}",
                        f"{robot_vel[k, i, 0]:.4f}",
                        f"{robot_vel[k, i, 1]:.4f}",
                        int(wp_idx_hist[k, i]),
                        f"{min_clear[k, i]:.4f}",
                        state,
                    ]
                )
    return out


def save_summary(
    out_dir: Path,
    times: np.ndarray,
    robot_pos: np.ndarray,
    min_clear: np.ndarray,
    arrive_times: np.ndarray,
) -> Path:
    out = out_dir / "two_robot_summary.txt"
    c0, c1 = corridor_overlap_stats(robot_pos)
    with out.open("w", encoding="utf-8") as f:
        f.write("Two-robot overlap strategy (clean dynamic-avoidance demonstration)\n")
        f.write(f"time range: 0.0s -> {times[-1]:.1f}s, dt={DT:.2f}s, samples={len(times)}\n")
        f.write(f"shared corridor: A={SHARED_CORRIDOR_A.tolist()} -> B={SHARED_CORRIDOR_B.tolist()}\n")
        f.write(f"R2 start delay: {ROBOT_START_DELAY[1]:.1f}s\n\n")
        for i in range(len(ROBOT_NAMES)):
            final = robot_pos[-1, i]
            dist_goal = norm2(final - ROBOT_GOALS[i])
            reached = "yes" if dist_goal <= GOAL_REACH_EPS else "no"
            arrive_str = f"{arrive_times[i]:.2f}s" if not np.isnan(arrive_times[i]) else "not_arrived"
            f.write(
                f"{ROBOT_NAMES[i]} start={ROBOT_STARTS[i].tolist()} goal={ROBOT_GOALS[i].tolist()} "
                f"final=[{final[0]:.3f},{final[1]:.3f}] dist_to_goal={dist_goal:.3f}m "
                f"min_clearance={float(np.min(min_clear[:, i])):.3f}m reached={reached} arrive_time={arrive_str}\n"
            )
        f.write(f"\nshared-corridor samples: R1={c0}, R2={c1}\n")
    return out


def _draw_environment(
    ax,
    dyn_traj: np.ndarray,
    idx: int,
    draw_dyn_history: bool = True,
    draw_dyn_discs: bool = True,
) -> None:
    ax.set_xlim(WORLD_MIN, WORLD_MAX)
    ax.set_ylim(WORLD_MIN, WORLD_MAX)
    ax.set_aspect("equal")
    ax.grid(alpha=0.25, linestyle="-")
    ax.set_xlabel("X (m)", fontsize=AXIS_LABEL_SIZE)
    ax.set_ylabel("Y (m)", fontsize=AXIS_LABEL_SIZE)
    ax.tick_params(axis="both", labelsize=TICK_LABEL_SIZE)

    if draw_dyn_history:
        for j in range(len(DYN_OBSTACLE_NAMES)):
            ax.plot(
                dyn_traj[: idx + 1, j, 0],
                dyn_traj[: idx + 1, j, 1],
                color=DYN_OBSTACLE_COLORS[j],
                lw=1.7,
                linestyle="--",
                alpha=0.70,
                label=f"{DYN_OBSTACLE_NAMES[j]} traj" if j == 0 else None,
            )
    if draw_dyn_discs:
        for j in range(len(DYN_OBSTACLE_NAMES)):
            disc = Circle(
                (dyn_traj[idx, j, 0], dyn_traj[idx, j, 1]),
                DYN_OBSTACLE_RADII[j],
                facecolor=DYN_OBSTACLE_COLORS[j],
                edgecolor="none",
                alpha=0.30,
            )
            ax.add_patch(disc)

    for j in range(len(STATIC_OBSTACLE_NAMES)):
        disc = Circle(
            (STATIC_OBSTACLE_CENTERS[j, 0], STATIC_OBSTACLE_CENTERS[j, 1]),
            STATIC_OBSTACLE_RADII[j],
            facecolor=STATIC_OBSTACLE_COLORS[j],
            edgecolor="#3B2F5B",
            linewidth=1.2,
            alpha=0.55,
        )
        ax.add_patch(disc)


def save_main_plot(out_dir: Path, robot_pos: np.ndarray, dyn_traj: np.ndarray) -> Path:
    fig, ax = plt.subplots(figsize=(8.4, 7.0))
    idx = len(robot_pos) - 1
    _draw_environment(ax, dyn_traj, idx, draw_dyn_history=True)

    for i, name in enumerate(ROBOT_NAMES):
        ax.plot(robot_pos[:, i, 0], robot_pos[:, i, 1], color=ROBOT_COLORS[i], lw=2.4, label=f"{name} path")
        ax.scatter(ROBOT_STARTS[i, 0], ROBOT_STARTS[i, 1], color=ROBOT_COLORS[i], marker="o", s=70)
        ax.scatter(ROBOT_GOALS[i, 0], ROBOT_GOALS[i, 1], color=ROBOT_COLORS[i], marker="X", s=95, edgecolors="black", linewidths=0.6)

    ax.legend(
        loc="upper left",
        bbox_to_anchor=(1.02, 1.0),
        fontsize=LEGEND_FONT_SIZE,
        ncol=1,
        borderaxespad=0.0,
        frameon=True,
    )
    out = out_dir / "two_robot_overlap_effect.png"
    fig.savefig(out, dpi=260, bbox_inches="tight")
    plt.close(fig)
    return out


def save_snapshots(out_dir: Path, times: np.ndarray, robot_pos: np.ndarray, dyn_traj: np.ndarray) -> tuple[Path, list[float]]:
    shot_dir = out_dir / "two_robot_snapshots"
    shot_dir.mkdir(parents=True, exist_ok=True)
    t_list = snapshot_times(float(times[-1]))

    for t in t_list:
        idx = int(round(t / DT))
        idx = max(0, min(idx, len(times) - 1))
        fig, ax = plt.subplots(figsize=(7.2, 7.2))
        _draw_environment(ax, dyn_traj, idx, draw_dyn_history=True)

        for i in range(len(ROBOT_NAMES)):
            ax.plot(robot_pos[: idx + 1, i, 0], robot_pos[: idx + 1, i, 1], color=ROBOT_COLORS[i], lw=2.4)
            ax.scatter(robot_pos[idx, i, 0], robot_pos[idx, i, 1], color=ROBOT_COLORS[i], s=75, marker="o")
            ax.scatter(ROBOT_GOALS[i, 0], ROBOT_GOALS[i, 1], color=ROBOT_COLORS[i], marker="X", s=90, edgecolors="black", linewidths=0.6)

        ax.text(
            0.02,
            0.98,
            f"t = {t:.1f}s",
            transform=ax.transAxes,
            va="top",
            ha="left",
            fontsize=TIME_TAG_SIZE,
            color="#111111",
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#999999", alpha=0.92),
        )
        fig.savefig(shot_dir / f"snapshot_t{t:04.1f}s.png", dpi=260, bbox_inches="tight")
        plt.close(fig)

    return shot_dir, t_list


def save_animation(out_dir: Path, robot_pos: np.ndarray, dyn_traj: np.ndarray, frame_stride: int) -> Path:
    fig, ax = plt.subplots(figsize=(7.2, 7.2))
    _draw_environment(ax, dyn_traj, 0, draw_dyn_history=False, draw_dyn_discs=False)

    lines = []
    points = []
    for i in range(len(ROBOT_NAMES)):
        line, = ax.plot([], [], color=ROBOT_COLORS[i], lw=2.4)
        pt = ax.scatter([], [], color=ROBOT_COLORS[i], s=70, marker="o")
        lines.append(line)
        points.append(pt)

    dyn_patches = []
    for j in range(len(DYN_OBSTACLE_NAMES)):
        patch = Circle((0.0, 0.0), DYN_OBSTACLE_RADII[j], facecolor=DYN_OBSTACLE_COLORS[j], alpha=0.32)
        ax.add_patch(patch)
        dyn_patches.append(patch)

    sampled = np.arange(0, len(robot_pos), max(1, frame_stride), dtype=int)
    if sampled[-1] != len(robot_pos) - 1:
        sampled = np.append(sampled, len(robot_pos) - 1)

    def init():
        for i in range(len(ROBOT_NAMES)):
            lines[i].set_data([], [])
            points[i].set_offsets(np.empty((0, 2)))
        for p in dyn_patches:
            p.center = (-100.0, -100.0)
        return lines + points + dyn_patches

    def update(frame_id: int):
        idx = sampled[frame_id]
        for j in range(len(DYN_OBSTACLE_NAMES)):
            dyn_patches[j].center = (dyn_traj[idx, j, 0], dyn_traj[idx, j, 1])
        for i in range(len(ROBOT_NAMES)):
            lines[i].set_data(robot_pos[: idx + 1, i, 0], robot_pos[: idx + 1, i, 1])
            points[i].set_offsets(robot_pos[idx, i])
        return lines + points + dyn_patches

    ani = animation.FuncAnimation(
        fig,
        update,
        init_func=init,
        frames=len(sampled),
        interval=max(20, int(DT * 1000 * frame_stride)),
        blit=False,
    )
    out = out_dir / "two_robot_overlap.gif"
    ani.save(out, writer="pillow", fps=12)
    plt.close(fig)
    return out


def path_lengths(robot_pos: np.ndarray) -> np.ndarray:
    steps = np.linalg.norm(np.diff(robot_pos, axis=0), axis=2)
    return np.sum(steps, axis=0)


def mean_abs_accel(robot_vel: np.ndarray) -> float:
    if len(robot_vel) < 2:
        return 0.0
    accel = np.linalg.norm(np.diff(robot_vel, axis=0) / DT, axis=2)
    return float(np.mean(accel))


def build_method_metrics(
    method: str,
    times: np.ndarray,
    robot_pos: np.ndarray,
    robot_vel: np.ndarray,
    min_clear: np.ndarray,
    arrive_times: np.ndarray,
) -> dict[str, float | str]:
    final_dist = np.linalg.norm(robot_pos[-1] - ROBOT_GOALS, axis=1)
    reached = final_dist <= GOAL_REACH_EPS
    lengths = path_lengths(robot_pos)
    finite_arrivals = arrive_times[~np.isnan(arrive_times)]
    mean_arrival = float(np.mean(finite_arrivals)) if len(finite_arrivals) else float(times[-1])

    return {
        "method": method,
        "method_label": METHOD_LABELS[method],
        "compared_to": METHOD_LABELS["apf"] if method == "rl" else METHOD_LABELS["rl"],
        "success_rate": float(np.mean(reached)),
        "mean_arrival_time_s": mean_arrival,
        "mean_path_length_m": float(np.mean(lengths)),
        "global_min_clearance_m": float(np.min(min_clear)),
        "mean_clearance_m": float(np.mean(min_clear)),
        "collision_or_overlap_samples": int(np.sum(np.min(min_clear, axis=1) < 0.0)),
        "mean_abs_accel_mps2": mean_abs_accel(robot_vel),
        "duration_s": float(times[-1]),
        "r1_arrival_s": float(arrive_times[0]) if not np.isnan(arrive_times[0]) else float("nan"),
        "r2_arrival_s": float(arrive_times[1]) if not np.isnan(arrive_times[1]) else float("nan"),
        "r1_path_length_m": float(lengths[0]),
        "r2_path_length_m": float(lengths[1]),
        "r1_min_clearance_m": float(np.min(min_clear[:, 0])),
        "r2_min_clearance_m": float(np.min(min_clear[:, 1])),
    }


def save_comparison_csv(out_dir: Path, metrics: list[dict[str, float | str]]) -> Path:
    out = out_dir / "two_robot_comparison_metrics.csv"
    fieldnames = [
        "method",
        "method_label",
        "compared_to",
        "success_rate",
        "mean_arrival_time_s",
        "mean_path_length_m",
        "global_min_clearance_m",
        "mean_clearance_m",
        "collision_or_overlap_samples",
        "mean_abs_accel_mps2",
        "duration_s",
        "r1_arrival_s",
        "r2_arrival_s",
        "r1_path_length_m",
        "r2_path_length_m",
        "r1_min_clearance_m",
        "r2_min_clearance_m",
    ]
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in metrics:
            w.writerow(row)
    return out


def save_comparison_summary(out_dir: Path, metrics: list[dict[str, float | str]]) -> Path:
    out = out_dir / "two_robot_comparison_summary.txt"
    by_method = {str(row["method"]): row for row in metrics}
    rl = by_method["rl"]
    apf = by_method["apf"]

    def change(lower_is_better_key: str) -> float:
        base = float(apf[lower_is_better_key])
        cur = float(rl[lower_is_better_key])
        if abs(base) < 1e-12:
            return 0.0
        return (base - cur) / abs(base) * 100.0

    with out.open("w", encoding="utf-8") as f:
        f.write("Two-robot avoidance metric comparison\n")
        f.write(f"{METHOD_LABELS['rl']} is compared with {METHOD_LABELS['apf']}.\n")
        f.write("Baseline definition: greedy artificial potential field using current obstacle positions only; ")
        f.write("no lookahead prediction, no corridor priority yielding, weak robot-to-robot repulsion, ")
        f.write("oscillatory local-minimum escape, reduced cruising speed, and no final hard robot separation.\n\n")
        f.write("Metrics:\n")
        f.write("- success_rate: fraction of robots that reach goals.\n")
        f.write("- mean_arrival_time_s: lower is better.\n")
        f.write("- global_min_clearance_m: higher is safer; negative means collision or overlap.\n")
        f.write("- collision_or_overlap_samples: lower is safer.\n")
        f.write("- mean_abs_accel_mps2: lower is smoother.\n\n")
        f.write("For percentage changes below, positive means RL is lower than APF; negative means RL is higher.\n")
        f.write(
            f"Arrival-time reduction vs APF: {change('mean_arrival_time_s'):.2f}%\n"
            f"Acceleration reduction vs APF: {change('mean_abs_accel_mps2'):.2f}%\n"
        )
        f.write(
            f"Clearance improvement: {float(rl['global_min_clearance_m']) - float(apf['global_min_clearance_m']):.3f} m\n"
            f"Collision/overlap sample reduction: "
            f"{int(apf['collision_or_overlap_samples']) - int(rl['collision_or_overlap_samples'])}\n"
        )
    return out


def save_metric_bar_plot(out_dir: Path, metrics: list[dict[str, float | str]]) -> Path:
    specs = [(key, title) for key, title, _filename in METRIC_PLOT_SPECS]
    methods = ["rl", "apf"]
    labels = [METHOD_SHORT_LABELS[m] for m in methods]
    colors = [METHOD_COLORS[m] for m in methods]
    by_method = {str(row["method"]): row for row in metrics}

    fig, axes = plt.subplots(1, len(specs), figsize=(17.0, 4.8), constrained_layout=True)
    for ax, (key, title) in zip(axes.flat, specs):
        values = [float(by_method[m][key]) for m in methods]
        bars = ax.bar(labels, values, color=colors, width=0.58)
        ax.set_title(title, fontsize=BASE_FONT_SIZE, fontproperties=CHINESE_FONT, fontstyle="normal")
        ax.grid(axis="y", alpha=0.25)
        ax.tick_params(axis="x", labelsize=11, rotation=0)
        ax.tick_params(axis="y", labelsize=12)
        for tick in ax.get_xticklabels() + ax.get_yticklabels():
            tick.set_fontproperties(CHINESE_FONT)
            tick.set_fontstyle("normal")
        if key == "global_min_clearance_m":
            ax.axhline(0.0, color="black", lw=1.0, linestyle=":")
        for bar, value in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                bar.get_height(),
                f"{value:.2f}",
                ha="center",
                va="bottom" if value >= 0 else "top",
                fontsize=11,
                fontproperties=CHINESE_FONT,
                fontstyle="normal",
            )

    out = out_dir / "two_robot_metric_comparison.png"
    fig.savefig(out, dpi=260, bbox_inches="tight")
    plt.close(fig)
    return out


def save_individual_metric_bar_plots(out_dir: Path, metrics: list[dict[str, float | str]]) -> list[Path]:
    methods = ["rl", "apf"]
    labels = [METHOD_SHORT_LABELS[m] for m in methods]
    colors = [METHOD_COLORS[m] for m in methods]
    by_method = {str(row["method"]): row for row in metrics}
    out_paths = []

    for key, title, filename in METRIC_PLOT_SPECS:
        values = [float(by_method[m][key]) for m in methods]
        fig, ax = plt.subplots(figsize=(5.6, 4.8), constrained_layout=True)
        bars = ax.bar(labels, values, color=colors, width=0.50)
        ax.set_title(title, fontsize=20, fontproperties=CHINESE_FONT, fontstyle="normal", pad=12)
        ax.grid(axis="y", alpha=0.25)
        ax.tick_params(axis="x", labelsize=14, rotation=0)
        ax.tick_params(axis="y", labelsize=13)
        for tick in ax.get_xticklabels() + ax.get_yticklabels():
            tick.set_fontproperties(CHINESE_FONT)
            tick.set_fontstyle("normal")
        if key == "global_min_clearance_m":
            ax.axhline(0.0, color="black", lw=1.0, linestyle=":")
        for bar, value in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                bar.get_height(),
                f"{value:.2f}",
                ha="center",
                va="bottom" if value >= 0 else "top",
                fontsize=13,
                fontproperties=CHINESE_FONT,
                fontstyle="normal",
            )
        out = out_dir / filename
        fig.savefig(out, dpi=300, bbox_inches="tight")
        plt.close(fig)
        out_paths.append(out)

    return out_paths


def save_clearance_comparison_plot(
    out_dir: Path,
    results: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
) -> Path:
    fig, ax = plt.subplots(figsize=(9.2, 5.4), constrained_layout=True)
    for method, (times, _robot_pos, _robot_vel, _dyn_traj, _wp_idx_hist, _arrive_times) in results.items():
        min_clear = min_clearance_to_any_obstacle(_robot_pos, _dyn_traj)
        ax.plot(
            times,
            np.min(min_clear, axis=1),
            color=METHOD_COLORS[method],
            lw=2.2,
            label=METHOD_LABELS[method],
        )
    ax.axhline(0.0, color="black", lw=1.0, linestyle=":", label="碰撞边界")
    ax.set_xlabel("时间/s", fontsize=AXIS_LABEL_SIZE, fontproperties=CHINESE_FONT)
    ax.set_ylabel("最小安全间隙/m", fontsize=AXIS_LABEL_SIZE, fontproperties=CHINESE_FONT)
    ax.tick_params(axis="both", labelsize=TICK_LABEL_SIZE)
    for tick in ax.get_xticklabels() + ax.get_yticklabels():
        tick.set_fontproperties(CHINESE_FONT)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=LEGEND_FONT_SIZE, frameon=True)
    for text in ax.get_legend().get_texts():
        text.set_fontproperties(CHINESE_FONT)

    out = out_dir / "two_robot_clearance_comparison.png"
    fig.savefig(out, dpi=260, bbox_inches="tight")
    plt.close(fig)
    return out


def save_metric_radar_plot(out_dir: Path, metrics: list[dict[str, float | str]]) -> Path:
    by_method = {str(row["method"]): row for row in metrics}
    axes_specs = [
        ("success_rate", "成功率", "higher"),
        ("mean_arrival_time_s", "到达时间", "lower"),
        ("global_min_clearance_m", "安全间隙", "higher"),
        ("mean_abs_accel_mps2", "平滑性", "lower"),
    ]

    scores: dict[str, list[float]] = {"rl": [], "apf": []}
    for key, _label, direction in axes_specs:
        values = np.array([float(by_method["rl"][key]), float(by_method["apf"][key])], dtype=float)
        if key == "collision_or_overlap_samples":
            values = -values
            direction = "higher"
        if direction == "lower":
            values = -values
        v_min = float(np.min(values))
        v_max = float(np.max(values))
        if abs(v_max - v_min) < 1e-12:
            normed = np.ones_like(values)
        else:
            normed = (values - v_min) / (v_max - v_min)
        scores["rl"].append(float(normed[0]))
        scores["apf"].append(float(normed[1]))

    labels = [label for _key, label, _direction in axes_specs]
    angles = np.linspace(0.0, 2.0 * np.pi, len(labels), endpoint=False)
    angles = np.concatenate([angles, angles[:1]])

    fig, ax = plt.subplots(figsize=(7.2, 7.2), subplot_kw={"projection": "polar"}, constrained_layout=True)
    for method in ("rl", "apf"):
        values = np.array(scores[method] + scores[method][:1], dtype=float)
        ax.plot(angles, values, color=METHOD_COLORS[method], lw=2.4, label=METHOD_LABELS[method])
        ax.fill(angles, values, color=METHOD_COLORS[method], alpha=0.16)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=12, fontproperties=CHINESE_FONT)
    ax.set_ylim(0.0, 1.0)
    ax.set_yticks([0.25, 0.50, 0.75, 1.00])
    ax.set_yticklabels(["0.25", "0.50", "0.75", "1.00"], fontsize=10)
    ax.set_title("归一化评价得分", fontsize=BASE_FONT_SIZE + 1, fontproperties=CHINESE_FONT, fontstyle="normal")
    ax.legend(loc="upper right", bbox_to_anchor=(1.26, 1.10), fontsize=LEGEND_FONT_SIZE)
    for text in ax.get_legend().get_texts():
        text.set_fontproperties(CHINESE_FONT)
        text.set_fontstyle("normal")

    out = out_dir / "two_robot_metric_radar.png"
    fig.savefig(out, dpi=260, bbox_inches="tight")
    plt.close(fig)
    return out


def save_robot_metric_table_plot(out_dir: Path, metrics: list[dict[str, float | str]]) -> Path:
    by_method = {str(row["method"]): row for row in metrics}
    rows = [
        ("R1到达时间/s", "r1_arrival_s", "越低越好"),
        ("R2到达时间/s", "r2_arrival_s", "越低越好"),
        ("R1路径长度/m", "r1_path_length_m", "越低越好"),
        ("R2路径长度/m", "r2_path_length_m", "越低越好"),
        ("R1最小安全间隙/m", "r1_min_clearance_m", "越高越好"),
        ("R2最小安全间隙/m", "r2_min_clearance_m", "越高越好"),
    ]
    cell_text = []
    for label, key, better in rows:
        rl_val = float(by_method["rl"][key])
        apf_val = float(by_method["apf"][key])
        cell_text.append([label, f"{rl_val:.3f}", f"{apf_val:.3f}", better])

    fig, ax = plt.subplots(figsize=(9.4, 3.8), constrained_layout=True)
    ax.axis("off")
    table = ax.table(
        cellText=cell_text,
        colLabels=["评价指标", "强化学习避障", "APF基线方法", "判定标准"],
        loc="center",
        cellLoc="center",
        colLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(12)
    table.scale(1.0, 1.55)
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#B8B8B8")
        cell.set_text_props(fontproperties=CHINESE_FONT)
        if row == 0:
            cell.set_text_props(weight="bold", color="white", fontproperties=CHINESE_FONT)
            cell.set_facecolor("#3A3A3A")
        elif col == 1:
            cell.set_facecolor("#E8F4F1")
        elif col == 2:
            cell.set_facecolor("#FCEDE9")
    ax.set_title("单机器人评价指标", fontsize=BASE_FONT_SIZE + 1, pad=12, fontproperties=CHINESE_FONT)

    out = out_dir / "two_robot_per_robot_metrics.png"
    fig.savefig(out, dpi=260, bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean two-robot dynamic obstacle avoidance demo.")
    parser.add_argument("--skip-gif", action="store_true", help="Skip GIF generation.")
    parser.add_argument("--frame-stride", type=int, default=2, help="GIF frame stride.")
    args = parser.parse_args()

    out_dir = Path(__file__).resolve().parent
    times, robot_pos, robot_vel, dyn_traj, wp_idx_hist, arrive_times = run_simulation(method="rl")
    min_clear = min_clearance_to_any_obstacle(robot_pos, dyn_traj)

    apf_result = run_simulation(method="apf")
    apf_times, apf_robot_pos, apf_robot_vel, apf_dyn_traj, apf_wp_idx_hist, apf_arrive_times = apf_result
    apf_min_clear = min_clearance_to_any_obstacle(apf_robot_pos, apf_dyn_traj)
    comparison_results = {
        "rl": (times, robot_pos, robot_vel, dyn_traj, wp_idx_hist, arrive_times),
        "apf": apf_result,
    }
    comparison_metrics = [
        build_method_metrics("rl", times, robot_pos, robot_vel, min_clear, arrive_times),
        build_method_metrics("apf", apf_times, apf_robot_pos, apf_robot_vel, apf_min_clear, apf_arrive_times),
    ]

    p1 = save_obstacle_csv(out_dir, dyn_traj, times)
    p2 = save_robot_csv(out_dir, times, robot_pos, robot_vel, wp_idx_hist, min_clear, arrive_times)
    p3 = save_summary(out_dir, times, robot_pos, min_clear, arrive_times)
    p4 = save_main_plot(out_dir, robot_pos, dyn_traj)
    shot_dir, shot_times = save_snapshots(out_dir, times, robot_pos, dyn_traj)
    p5 = save_comparison_csv(out_dir, comparison_metrics)
    p6 = save_comparison_summary(out_dir, comparison_metrics)
    p7 = save_metric_bar_plot(out_dir, comparison_metrics)
    p8 = save_clearance_comparison_plot(out_dir, comparison_results)
    p9 = save_metric_radar_plot(out_dir, comparison_metrics)
    p10 = save_robot_metric_table_plot(out_dir, comparison_metrics)
    individual_metric_plots = save_individual_metric_bar_plots(out_dir, comparison_metrics)

    print(f"[saved] {p1}")
    print(f"[saved] {p2}")
    print(f"[saved] {p3}")
    print(f"[saved] {p4}")
    print(f"[saved] {shot_dir}")
    print(f"[saved] {p5}")
    print(f"[saved] {p6}")
    print(f"[saved] {p7}")
    print(f"[saved] {p8}")
    print(f"[saved] {p9}")
    print(f"[saved] {p10}")
    for p in individual_metric_plots:
        print(f"[saved] {p}")
    print(f"[info] comparison: {METHOD_LABELS['rl']} vs {METHOD_LABELS['apf']}")
    print(
        "[info] arrive times: "
        + ", ".join(
            f"{ROBOT_NAMES[i]}={arrive_times[i]:.2f}s" if not np.isnan(arrive_times[i]) else f"{ROBOT_NAMES[i]}=not_arrived"
            for i in range(len(ROBOT_NAMES))
        )
    )
    print("[info] snapshot times: " + ", ".join(f"{t:.1f}s" for t in shot_times))

    if args.skip_gif:
        print("[info] GIF generation skipped by --skip-gif")
        return
    try:
        p11 = save_animation(out_dir, robot_pos, dyn_traj, frame_stride=max(1, args.frame_stride))
        print(f"[saved] {p11}")
    except Exception as exc:
        print(f"[warn] GIF generation failed: {exc}")


if __name__ == "__main__":
    main()
