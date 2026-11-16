from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import animation
from matplotlib.patches import Circle

BASE_FONT_SIZE = 16
AXIS_LABEL_SIZE = 18
TICK_LABEL_SIZE = 15
LEGEND_FONT_SIZE = 12
TIME_TAG_SIZE = 18

plt.rcParams.update({"font.size": BASE_FONT_SIZE})
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = [
    "Times New Roman",
    "Times",
    "Nimbus Roman No9 L",
    "DejaVu Serif",
]
plt.rcParams["mathtext.fontset"] = "stix"

WORLD_MIN = 0.0
WORLD_MAX = 30.0
DT = 0.2
TOTAL_TIME = 45.0
LOOKAHEAD = 0.8
TIMES = np.arange(0.0, TOTAL_TIME + 1e-9, DT)
ROBOT_BODY_RADIUS = 0.28
DYNAMIC_CLEARANCE_MARGIN = 0.30
STATIC_CLEARANCE_MARGIN = 0.45

ROBOT_NAMES = ["R1", "R2", "R3", "R4"]
ROBOT_COLORS = ["#D1495B", "#00798C", "#30638E", "#EDAe49"]
ROBOT_STARTS = np.array(
    [
        [2.0, 2.0],
        [28.0, 2.0],
        [2.0, 28.0],
        [28.0, 28.0],
    ],
    dtype=float,
)
ROBOT_GOALS = np.array(
    [
        [28.0, 28.0],
        [2.0, 28.0],
        [28.0, 2.0],
        [2.0, 2.0],
    ],
    dtype=float,
)
ROBOT_MAX_SPEED = np.array([1.15, 1.10, 1.10, 1.05], dtype=float)

DYN_OBSTACLE_NAMES = ["OBS1", "OBS2"]
DYN_OBSTACLE_RADII = np.array([1.20, 1.00], dtype=float)
DYN_OBSTACLE_COLORS = ["#5C4D7D", "#7A6C5D"]

STATIC_OBSTACLE_NAMES = ["SOBS1", "SOBS2"]
STATIC_OBSTACLE_CENTERS = np.array([[12.0, 12.0], [18.0, 18.0]], dtype=float)
STATIC_OBSTACLE_RADII = np.array([1.30, 1.30], dtype=float)
STATIC_OBSTACLE_COLORS = ["#8D6A9F", "#8D6A9F"]


def obstacle_positions_at(t: float) -> np.ndarray:
    obs1 = np.array(
        [
            15.0 + 6.0 * math.cos(0.28 * t),
            15.0 + 4.0 * math.sin(0.28 * t + 0.35),
        ]
    )
    obs2 = np.array(
        [
            5.0 + 20.0 * (0.5 + 0.5 * math.sin(0.22 * t + 1.10)),
            6.0 + 18.0 * (0.5 + 0.5 * math.sin(0.37 * t)),
        ]
    )
    return np.vstack([obs1, obs2])


def norm2(vec: np.ndarray) -> float:
    return float(np.linalg.norm(vec))


def enforce_static_clearance(prev_pos: np.ndarray, next_pos: np.ndarray) -> np.ndarray:
    """Keep one robot step segment outside static-obstacle safety circles."""
    adjusted = next_pos.copy()
    safe_radii = STATIC_OBSTACLE_RADII + ROBOT_BODY_RADIUS + STATIC_CLEARANCE_MARGIN

    for _ in range(2):
        for j, center in enumerate(STATIC_OBSTACLE_CENTERS):
            safe_r = safe_radii[j]

            step_vec = adjusted - prev_pos
            step_len_sq = float(np.dot(step_vec, step_vec))
            if step_len_sq < 1e-12:
                closest = prev_pos
            else:
                t = float(np.dot(center - prev_pos, step_vec) / step_len_sq)
                t = max(0.0, min(1.0, t))
                closest = prev_pos + t * step_vec

            d_closest_vec = closest - center
            d_closest = norm2(d_closest_vec)
            if d_closest < safe_r:
                if d_closest < 1e-9:
                    if step_len_sq > 1e-12:
                        step_dir = step_vec / math.sqrt(step_len_sq)
                        normal = np.array([-step_dir[1], step_dir[0]])
                    else:
                        normal = np.array([1.0, 0.0])
                else:
                    normal = d_closest_vec / d_closest
                adjusted = adjusted + (safe_r - d_closest + 1e-3) * normal

            d_end_vec = adjusted - center
            d_end = norm2(d_end_vec)
            if d_end < safe_r:
                if d_end < 1e-9:
                    d_end_vec = np.array([1.0, 0.0])
                    d_end = 1.0
                adjusted = center + d_end_vec / d_end * (safe_r + 1e-3)

    return np.clip(adjusted, WORLD_MIN, WORLD_MAX)


def run_simulation() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n_steps = len(TIMES)
    n_robots = len(ROBOT_NAMES)

    obstacle_traj = np.array([obstacle_positions_at(t) for t in TIMES], dtype=float)
    robot_pos = np.zeros((n_steps, n_robots, 2), dtype=float)
    robot_vel = np.zeros_like(robot_pos)
    robot_pos[0] = ROBOT_STARTS

    for k, t in enumerate(TIMES[:-1]):
        cur_pos = robot_pos[k].copy()
        cur_vel = robot_vel[k].copy()
        next_pos = np.zeros_like(cur_pos)
        next_vel = np.zeros_like(cur_vel)

        obs_now = obstacle_traj[k]
        obs_future = obstacle_positions_at(t + LOOKAHEAD)

        for i in range(n_robots):
            to_goal = ROBOT_GOALS[i] - cur_pos[i]
            dist_goal = norm2(to_goal)
            if dist_goal < 0.30:
                desired_vel = np.zeros(2, dtype=float)
            else:
                goal_dir = to_goal / (dist_goal + 1e-9)
                attraction = 1.30 * goal_dir

                avoid = np.zeros(2, dtype=float)
                tangent = np.zeros(2, dtype=float)
                turn_sign = 1.0 if (i % 2 == 0) else -1.0

                for j in range(len(DYN_OBSTACLE_NAMES)):
                    for obs_pos, weight in ((obs_now[j], 1.0), (obs_future[j], 0.75)):
                        away = cur_pos[i] - obs_pos
                        d = norm2(away) + 1e-9
                        d_safe = DYN_OBSTACLE_RADII[j] + ROBOT_BODY_RADIUS + DYNAMIC_CLEARANCE_MARGIN
                        d_influence = DYN_OBSTACLE_RADII[j] + 3.8
                        if d < d_influence:
                            gain = 3.4 * weight * (1.0 / d - 1.0 / d_influence) / (d * d)
                            avoid += gain * (away / d)
                        if d_safe < d < d_influence - 0.4:
                            normal = away / d
                            tangent += 0.45 * weight * turn_sign * np.array([-normal[1], normal[0]])

                for j in range(len(STATIC_OBSTACLE_NAMES)):
                    obs_pos = STATIC_OBSTACLE_CENTERS[j]
                    away = cur_pos[i] - obs_pos
                    d = norm2(away) + 1e-9
                    d_safe = STATIC_OBSTACLE_RADII[j] + ROBOT_BODY_RADIUS + STATIC_CLEARANCE_MARGIN
                    d_influence = d_safe + 4.0
                    if d < d_influence:
                        gain = 5.6 * (1.0 / d - 1.0 / d_influence) / (d * d)
                        avoid += gain * (away / d)
                    if d_safe < d < d_influence - 0.4:
                        normal = away / d
                        tangent += 0.72 * turn_sign * np.array([-normal[1], normal[0]])

                for m in range(n_robots):
                    if m == i:
                        continue
                    away_robot = cur_pos[i] - cur_pos[m]
                    d_robot = norm2(away_robot) + 1e-9
                    influence = 2.3
                    if d_robot < influence:
                        gain = 2.0 * (1.0 / d_robot - 1.0 / influence) / (d_robot * d_robot)
                        avoid += gain * (away_robot / d_robot)

                direction = attraction + avoid + tangent
                if norm2(direction) < 1e-6:
                    direction = goal_dir

                speed_scale = min(1.0, max(0.18, dist_goal / 2.0))
                target_speed = ROBOT_MAX_SPEED[i] * speed_scale
                desired_vel = (direction / (norm2(direction) + 1e-9)) * target_speed

            blended = 0.58 * cur_vel[i] + 0.42 * desired_vel
            speed = norm2(blended)
            max_speed = ROBOT_MAX_SPEED[i]
            if speed > max_speed:
                blended = blended / speed * max_speed

            candidate = cur_pos[i] + blended * DT
            candidate = np.clip(candidate, WORLD_MIN, WORLD_MAX)
            candidate = enforce_static_clearance(cur_pos[i], candidate)
            next_pos[i] = candidate
            next_vel[i] = (candidate - cur_pos[i]) / DT

        # Soft collision handling among robots after synchronous move.
        min_sep = 0.80
        for _ in range(2):
            for i in range(n_robots):
                for j in range(i + 1, n_robots):
                    delta = next_pos[i] - next_pos[j]
                    d = norm2(delta)
                    if d >= min_sep:
                        continue
                    if d < 1e-8:
                        delta = np.array([1.0, 0.0]) if (i + j) % 2 == 0 else np.array([0.0, 1.0])
                        d = 1.0
                    push = (min_sep - d) * 0.5 * (delta / d)
                    next_pos[i] = np.clip(next_pos[i] + push, WORLD_MIN, WORLD_MAX)
                    next_pos[j] = np.clip(next_pos[j] - push, WORLD_MIN, WORLD_MAX)

        robot_pos[k + 1] = next_pos
        robot_vel[k + 1] = next_vel

    return robot_pos, robot_vel, obstacle_traj


def compute_min_clearance(robot_pos: np.ndarray, obstacle_traj: np.ndarray) -> np.ndarray:
    n_steps, n_robots, _ = robot_pos.shape
    min_clear = np.zeros((n_steps, n_robots), dtype=float)
    for k in range(n_steps):
        for i in range(n_robots):
            dists = []
            for j in range(len(DYN_OBSTACLE_NAMES)):
                center_dist = norm2(robot_pos[k, i] - obstacle_traj[k, j])
                dists.append(center_dist - DYN_OBSTACLE_RADII[j])
            for j in range(len(STATIC_OBSTACLE_NAMES)):
                center_dist = norm2(robot_pos[k, i] - STATIC_OBSTACLE_CENTERS[j])
                dists.append(center_dist - STATIC_OBSTACLE_RADII[j])
            min_clear[k, i] = min(dists)
    return min_clear


def save_obstacle_csv(out_dir: Path, obstacle_traj: np.ndarray) -> Path:
    out_path = out_dir / "dynamic_obstacle_schedule.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["time_s", "obstacle_id", "obstacle_type", "x", "y", "radius_m"])
        for k, t in enumerate(TIMES):
            for j, name in enumerate(DYN_OBSTACLE_NAMES):
                writer.writerow(
                    [
                        f"{t:.2f}",
                        name,
                        "dynamic",
                        f"{obstacle_traj[k, j, 0]:.4f}",
                        f"{obstacle_traj[k, j, 1]:.4f}",
                        f"{DYN_OBSTACLE_RADII[j]:.3f}",
                    ]
                )
            for j, name in enumerate(STATIC_OBSTACLE_NAMES):
                writer.writerow(
                    [
                        f"{t:.2f}",
                        name,
                        "static",
                        f"{STATIC_OBSTACLE_CENTERS[j, 0]:.4f}",
                        f"{STATIC_OBSTACLE_CENTERS[j, 1]:.4f}",
                        f"{STATIC_OBSTACLE_RADII[j]:.3f}",
                    ]
                )
    return out_path


def save_robot_csv(
    out_dir: Path, robot_pos: np.ndarray, robot_vel: np.ndarray, min_clearance: np.ndarray
) -> Path:
    out_path = out_dir / "robot_avoidance_trajectories.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "time_s",
                "robot_id",
                "x",
                "y",
                "vx",
                "vy",
                "dist_to_goal",
                "min_dist_to_obstacle_boundary",
            ]
        )
        for k, t in enumerate(TIMES):
            for i, name in enumerate(ROBOT_NAMES):
                writer.writerow(
                    [
                        f"{t:.2f}",
                        name,
                        f"{robot_pos[k, i, 0]:.4f}",
                        f"{robot_pos[k, i, 1]:.4f}",
                        f"{robot_vel[k, i, 0]:.4f}",
                        f"{robot_vel[k, i, 1]:.4f}",
                        f"{norm2(ROBOT_GOALS[i] - robot_pos[k, i]):.4f}",
                        f"{min_clearance[k, i]:.4f}",
                    ]
                )
    return out_path


def save_summary(out_dir: Path, min_clearance: np.ndarray, robot_pos: np.ndarray) -> Path:
    out_path = out_dir / "summary.txt"
    with out_path.open("w", encoding="utf-8") as f:
        f.write("Dynamic obstacle trajectories:\n")
        f.write("OBS1(t) = [15 + 6*cos(0.28*t), 15 + 4*sin(0.28*t + 0.35)]\n")
        f.write("OBS2(t) = [5 + 20*(0.5 + 0.5*sin(0.22*t + 1.10)), 6 + 18*(0.5 + 0.5*sin(0.37*t))]\n")
        f.write("\nStatic obstacles:\n")
        f.write("SOBS1 center = [12.0, 12.0], radius = 1.30\n")
        f.write("SOBS2 center = [18.0, 18.0], radius = 1.30\n")
        f.write(f"time range: 0.0s -> {TOTAL_TIME:.1f}s, dt = {DT:.1f}s, samples = {len(TIMES)}\n\n")
        f.write("Robot start -> goal:\n")
        for i in range(len(ROBOT_NAMES)):
            f.write(
                f"{ROBOT_NAMES[i]}: {ROBOT_STARTS[i].tolist()} -> {ROBOT_GOALS[i].tolist()}, "
                f"min obstacle clearance = {float(np.min(min_clearance[:, i])):.3f} m\n"
            )

        f.write("\nRobot final positions:\n")
        for i in range(len(ROBOT_NAMES)):
            final = robot_pos[-1, i]
            dist_goal = norm2(ROBOT_GOALS[i] - final)
            f.write(
                f"{ROBOT_NAMES[i]} final = [{final[0]:.3f}, {final[1]:.3f}], "
                f"distance to goal = {dist_goal:.3f} m\n"
            )
    return out_path


def save_static_plot(
    out_dir: Path, robot_pos: np.ndarray, obstacle_traj: np.ndarray, min_clearance: np.ndarray
) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(15, 6), constrained_layout=True)
    ax_xy, ax_clear = axes

    ax_xy.set_xlim(WORLD_MIN, WORLD_MAX)
    ax_xy.set_ylim(WORLD_MIN, WORLD_MAX)
    ax_xy.set_aspect("equal")
    ax_xy.grid(alpha=0.25, linestyle="-")
    ax_xy.set_xlabel("X (m)", fontsize=AXIS_LABEL_SIZE)
    ax_xy.set_ylabel("Y (m)", fontsize=AXIS_LABEL_SIZE)
    ax_xy.tick_params(axis="both", labelsize=TICK_LABEL_SIZE)

    for j, obs_name in enumerate(DYN_OBSTACLE_NAMES):
        ax_xy.plot(
            obstacle_traj[:, j, 0],
            obstacle_traj[:, j, 1],
            color=DYN_OBSTACLE_COLORS[j],
            lw=2.0,
            linestyle="--",
            label=f"{obs_name} trajectory",
            alpha=0.85,
        )
        for snapshot_t in (0.0, 15.0, 30.0, 45.0):
            idx = int(round(snapshot_t / DT))
            c = obstacle_traj[idx, j]
            disc = Circle(
                (c[0], c[1]),
                DYN_OBSTACLE_RADII[j],
                facecolor=DYN_OBSTACLE_COLORS[j],
                edgecolor="none",
                alpha=0.18,
            )
            ax_xy.add_patch(disc)

    for j, obs_name in enumerate(STATIC_OBSTACLE_NAMES):
        disc = Circle(
            (STATIC_OBSTACLE_CENTERS[j, 0], STATIC_OBSTACLE_CENTERS[j, 1]),
            STATIC_OBSTACLE_RADII[j],
            facecolor=STATIC_OBSTACLE_COLORS[j],
            edgecolor="#3B2F5B",
            linewidth=1.2,
            alpha=0.55,
            label=f"{obs_name} static",
        )
        ax_xy.add_patch(disc)

    for i, name in enumerate(ROBOT_NAMES):
        ax_xy.plot(
            robot_pos[:, i, 0],
            robot_pos[:, i, 1],
            color=ROBOT_COLORS[i],
            lw=2.0,
            label=f"{name} path",
        )
        ax_xy.scatter(
            ROBOT_STARTS[i, 0],
            ROBOT_STARTS[i, 1],
            color=ROBOT_COLORS[i],
            marker="o",
            s=48,
        )
        ax_xy.scatter(
            ROBOT_GOALS[i, 0],
            ROBOT_GOALS[i, 1],
            color=ROBOT_COLORS[i],
            marker="X",
            s=58,
            edgecolors="black",
            linewidths=0.5,
        )

    ax_xy.legend(
        loc="upper left",
        bbox_to_anchor=(1.02, 1.0),
        fontsize=LEGEND_FONT_SIZE,
        ncol=1,
        borderaxespad=0.0,
        frameon=True,
    )

    ax_clear.set_xlim(0.0, TOTAL_TIME)
    ax_clear.set_xlabel("Time (s)", fontsize=AXIS_LABEL_SIZE)
    ax_clear.set_ylabel("Clearance (m)", fontsize=AXIS_LABEL_SIZE)
    ax_clear.grid(alpha=0.25, linestyle="-")
    ax_clear.axhline(0.0, color="black", lw=1.0, linestyle=":")
    ax_clear.tick_params(axis="both", labelsize=TICK_LABEL_SIZE)

    for i, name in enumerate(ROBOT_NAMES):
        ax_clear.plot(TIMES, min_clearance[:, i], color=ROBOT_COLORS[i], lw=2.0, label=name)
    ax_clear.legend(
        loc="upper left",
        bbox_to_anchor=(1.02, 1.0),
        fontsize=LEGEND_FONT_SIZE,
        borderaxespad=0.0,
        frameon=True,
    )

    out_path = out_dir / "dynamic_avoidance_effect.png"
    fig.savefig(out_path, dpi=260)
    plt.close(fig)
    return out_path


def save_animation(
    out_dir: Path,
    robot_pos: np.ndarray,
    obstacle_traj: np.ndarray,
    frame_stride: int = 1,
) -> Path:
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.set_xlim(WORLD_MIN, WORLD_MAX)
    ax.set_ylim(WORLD_MIN, WORLD_MAX)
    ax.set_aspect("equal")
    ax.set_xlabel("X (m)", fontsize=AXIS_LABEL_SIZE)
    ax.set_ylabel("Y (m)", fontsize=AXIS_LABEL_SIZE)
    ax.tick_params(axis="both", labelsize=TICK_LABEL_SIZE)
    ax.grid(alpha=0.25, linestyle="-")

    for i in range(len(ROBOT_NAMES)):
        ax.scatter(ROBOT_GOALS[i, 0], ROBOT_GOALS[i, 1], color=ROBOT_COLORS[i], marker="X", s=60)

    lines = []
    points = []
    for i, name in enumerate(ROBOT_NAMES):
        line, = ax.plot([], [], color=ROBOT_COLORS[i], lw=2.0, label=name)
        point = ax.scatter([], [], color=ROBOT_COLORS[i], s=42, marker="o")
        lines.append(line)
        points.append(point)

    obs_patches = []
    for j, name in enumerate(DYN_OBSTACLE_NAMES):
        patch = Circle((0.0, 0.0), DYN_OBSTACLE_RADII[j], facecolor=DYN_OBSTACLE_COLORS[j], alpha=0.35)
        ax.add_patch(patch)
        obs_patches.append(patch)

    static_patches = []
    for j, name in enumerate(STATIC_OBSTACLE_NAMES):
        patch = Circle(
            (STATIC_OBSTACLE_CENTERS[j, 0], STATIC_OBSTACLE_CENTERS[j, 1]),
            STATIC_OBSTACLE_RADII[j],
            facecolor=STATIC_OBSTACLE_COLORS[j],
            edgecolor="#3B2F5B",
            linewidth=1.0,
            alpha=0.55,
        )
        ax.add_patch(patch)
        static_patches.append(patch)
    sampled_indices = np.arange(0, len(TIMES), frame_stride, dtype=int)
    if sampled_indices[-1] != len(TIMES) - 1:
        sampled_indices = np.append(sampled_indices, len(TIMES) - 1)

    def init():
        for i in range(len(ROBOT_NAMES)):
            lines[i].set_data([], [])
            points[i].set_offsets(np.empty((0, 2)))
        for p in obs_patches:
            p.center = (-100.0, -100.0)
        return lines + points + obs_patches + static_patches

    def update(frame_id: int):
        k = sampled_indices[frame_id]
        for i in range(len(ROBOT_NAMES)):
            lines[i].set_data(robot_pos[: k + 1, i, 0], robot_pos[: k + 1, i, 1])
            points[i].set_offsets(robot_pos[k, i])
        for j in range(len(DYN_OBSTACLE_NAMES)):
            obs_patches[j].center = (obstacle_traj[k, j, 0], obstacle_traj[k, j, 1])
        return lines + points + obs_patches + static_patches

    ani = animation.FuncAnimation(
        fig,
        update,
        init_func=init,
        frames=len(sampled_indices),
        interval=max(20, int(DT * 1000 * frame_stride)),
        blit=False,
    )

    out_path = out_dir / "dynamic_avoidance.gif"
    ani.save(out_path, writer="pillow", fps=12)
    plt.close(fig)
    return out_path


def _snapshot_indices() -> list[int]:
    if TOTAL_TIME >= 20.0:
        desired = np.arange(0.0, TOTAL_TIME + 1e-9, 5.0)
        if abs(float(desired[-1]) - TOTAL_TIME) > 1e-9:
            desired = np.append(desired, TOTAL_TIME)
    else:
        if TOTAL_TIME <= 10.0:
            n_shots = 4
        elif TOTAL_TIME <= 16.0:
            n_shots = 5
        else:
            n_shots = 6
        desired = np.linspace(0.0, TOTAL_TIME, n_shots)

    idx_set = set()
    for t in desired:
        idx = int(round(float(t) / DT))
        idx = max(0, min(idx, len(TIMES) - 1))
        idx_set.add(idx)

    idxs = sorted(idx_set)
    if idxs[0] != 0:
        idxs = [0] + idxs
    if idxs[-1] != len(TIMES) - 1:
        idxs.append(len(TIMES) - 1)
    return idxs


def save_time_snapshots(
    out_dir: Path, robot_pos: np.ndarray, obstacle_traj: np.ndarray
) -> tuple[Path, list[float]]:
    shot_dir = out_dir / "time_snapshots"
    shot_dir.mkdir(parents=True, exist_ok=True)
    idxs = _snapshot_indices()

    for idx in idxs:
        t = float(TIMES[idx])
        fig, ax = plt.subplots(figsize=(7, 7))
        ax.set_xlim(WORLD_MIN, WORLD_MAX)
        ax.set_ylim(WORLD_MIN, WORLD_MAX)
        ax.set_aspect("equal")
        ax.grid(alpha=0.25, linestyle="-")
        ax.set_xlabel("X (m)", fontsize=AXIS_LABEL_SIZE)
        ax.set_ylabel("Y (m)", fontsize=AXIS_LABEL_SIZE)
        ax.tick_params(axis="both", labelsize=TICK_LABEL_SIZE)

        for j in range(len(DYN_OBSTACLE_NAMES)):
            ax.plot(
                obstacle_traj[: idx + 1, j, 0],
                obstacle_traj[: idx + 1, j, 1],
                color=DYN_OBSTACLE_COLORS[j],
                lw=1.8,
                linestyle="--",
                alpha=0.70,
            )
            disc = Circle(
                (obstacle_traj[idx, j, 0], obstacle_traj[idx, j, 1]),
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
                linewidth=1.0,
                alpha=0.55,
            )
            ax.add_patch(disc)

        for i in range(len(ROBOT_NAMES)):
            ax.plot(
                robot_pos[: idx + 1, i, 0],
                robot_pos[: idx + 1, i, 1],
                color=ROBOT_COLORS[i],
                lw=2.3,
            )
            ax.scatter(robot_pos[idx, i, 0], robot_pos[idx, i, 1], color=ROBOT_COLORS[i], s=70, marker="o")
            ax.scatter(
                ROBOT_GOALS[i, 0],
                ROBOT_GOALS[i, 1],
                color=ROBOT_COLORS[i],
                marker="X",
                s=90,
                edgecolors="black",
                linewidths=0.6,
            )

        ax.text(
            0.02,
            0.98,
            f"t = {t:.1f}s",
            transform=ax.transAxes,
            va="top",
            ha="left",
            fontsize=TIME_TAG_SIZE,
            color="#111111",
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#999999", alpha=0.9),
        )

        out_path = shot_dir / f"snapshot_t{t:05.1f}s.png"
        fig.savefig(out_path, dpi=260, bbox_inches="tight")
        plt.close(fig)

    shot_times = [float(TIMES[idx]) for idx in idxs]
    return shot_dir, shot_times


def main() -> None:
    parser = argparse.ArgumentParser(description="Dynamic obstacle avoidance demo for 4 robots.")
    parser.add_argument(
        "--skip-gif",
        action="store_true",
        help="Skip GIF generation (faster).",
    )
    parser.add_argument(
        "--frame-stride",
        type=int,
        default=2,
        help="Frame stride for GIF output. Larger value means fewer frames.",
    )
    args = parser.parse_args()

    out_dir = Path(__file__).resolve().parent
    robot_pos, robot_vel, obstacle_traj = run_simulation()
    min_clearance = compute_min_clearance(robot_pos, obstacle_traj)

    obstacle_csv = save_obstacle_csv(out_dir, obstacle_traj)
    robot_csv = save_robot_csv(out_dir, robot_pos, robot_vel, min_clearance)
    summary_txt = save_summary(out_dir, min_clearance, robot_pos)
    static_plot = save_static_plot(out_dir, robot_pos, obstacle_traj, min_clearance)
    snapshot_dir, snapshot_times = save_time_snapshots(out_dir, robot_pos, obstacle_traj)

    print(f"[saved] {obstacle_csv}")
    print(f"[saved] {robot_csv}")
    print(f"[saved] {summary_txt}")
    print(f"[saved] {static_plot}")
    print(f"[saved] {snapshot_dir}")
    print("[info] snapshot times: " + ", ".join(f"{t:.1f}s" for t in snapshot_times))

    if args.skip_gif:
        print("[info] GIF generation skipped by --skip-gif")
        return

    try:
        gif_path = save_animation(
            out_dir,
            robot_pos,
            obstacle_traj,
            frame_stride=max(1, args.frame_stride),
        )
        print(f"[saved] {gif_path}")
    except Exception as exc:
        print(f"[warn] GIF generation failed: {exc}")
        print("[warn] static outputs are still available.")


if __name__ == "__main__":
    main()
