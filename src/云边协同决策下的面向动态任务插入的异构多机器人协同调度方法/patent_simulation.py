from __future__ import annotations

import csv
import math
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.colors import to_rgba
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle


ROWS = 40
COLS = 40
TOTAL_STEPS = 220
EVENT_STEP = 80
RETURN_STEP = 120
TASK_POS = (25, 15)
TASK_DURATION = 40
WINDOW = 40
NUM_SEEDS = 20
BASE_OBSTACLE_SEED = 55
BASELINE_REPLAN_DELAY = 8
SAFE_ENERGY = 0.2
SEARCH_RADIUS = 11
OUTPUT_DIR = Path("patent_outputs")

START_SPECS = [
    ("Robot-A", (5, 3), 0.95, 1.0, 4, {"patrol", "inspect", "emergency"}),
    ("Robot-B", (35, 4), 0.90, 1.4, 3, {"patrol", "delivery"}),
    ("Robot-C", (6, 35), 0.82, 1.2, 5, {"patrol", "inspect"}),
    ("Robot-D", (32, 33), 0.88, 1.1, 4, {"patrol", "emergency", "service"}),
]

ROBOT_COLORS = {
    "Robot-A": "#d95f5f",
    "Robot-B": "#4c78a8",
    "Robot-C": "#59a14f",
    "Robot-D": "#f2b84b",
}


@dataclass
class PatentRobot:
    robot_id: int
    name: str
    position: tuple[int, int]
    energy: float
    speed: float
    radius: int
    capabilities: set[str]
    color: str
    zone: set[tuple[int, int]] = field(default_factory=set)
    temp_zone: set[tuple[int, int]] = field(default_factory=set)
    state: str = "patrol"
    path: list[tuple[int, int]] = field(default_factory=list)
    target: tuple[int, int] | None = None
    move_credit: float = 0.0
    trajectory: list[tuple[int, int]] = field(default_factory=list)
    event_arrival_step: int | None = None
    assigned_subblocks: list[str] = field(default_factory=list)
    replan_delay: int = 0

    def clone(self) -> "PatentRobot":
        copied = PatentRobot(
            self.robot_id,
            self.name,
            self.position,
            self.energy,
            self.speed,
            self.radius,
            set(self.capabilities),
            self.color,
        )
        copied.zone = set(self.zone)
        copied.temp_zone = set(self.temp_zone)
        copied.state = self.state
        copied.path = list(self.path)
        copied.target = self.target
        copied.move_credit = self.move_credit
        copied.trajectory = list(self.trajectory)
        copied.event_arrival_step = self.event_arrival_step
        copied.assigned_subblocks = list(self.assigned_subblocks)
        copied.replan_delay = self.replan_delay
        return copied

    @property
    def effective_zone(self) -> set[tuple[int, int]]:
        if self.state == "responding":
            return set()
        return self.zone | self.temp_zone


class PatentGrid:
    def __init__(self, seed: int = BASE_OBSTACLE_SEED) -> None:
        self.rows = ROWS
        self.cols = COLS
        self.seed = seed
        self.grid = np.zeros((ROWS, COLS), dtype=np.uint8)
        self._build_obstacles()
        self.free_cells = {
            (r, c)
            for r in range(self.rows)
            for c in range(self.cols)
            if self.grid[r, c] == 0
        }
        self._dist_cache: dict[tuple[int, int], dict[tuple[int, int], int]] = {}

    def _build_obstacles(self) -> None:
        rects = [
            (9, 12, 7, 14),
            (18, 23, 22, 28),
            (28, 32, 10, 16),
            (4, 7, 24, 29),
            (14, 17, 4, 10),
            (31, 35, 25, 31),
        ]
        for r1, r2, c1, c2 in rects:
            self.grid[r1:r2, c1:c2] = 1

        rng = np.random.default_rng(self.seed)
        protected = {TASK_POS, *(spec[1] for spec in START_SPECS)}
        placed = 0
        while placed < 10:
            r = int(rng.integers(2, ROWS - 3))
            c = int(rng.integers(2, COLS - 3))
            block = {(r + dr, c + dc) for dr in range(2) for dc in range(2)}
            if block & protected:
                continue
            if any(self.grid[rr, cc] for rr, cc in block):
                continue
            for rr, cc in block:
                self.grid[rr, cc] = 1
            placed += 1

        for cell in protected:
            self.grid[cell] = 0
        self._carve_key_corridors()
        self._remove_unreachable_cells(START_SPECS[0][1])

    def _carve_key_corridors(self) -> None:
        keys = [spec[1] for spec in START_SPECS] + [TASK_POS]
        for start, goal in zip(keys, keys[1:]):
            r, c = start
            gr, gc = goal
            while r != gr:
                self.grid[r, c] = 0
                r += 1 if gr > r else -1
            while c != gc:
                self.grid[r, c] = 0
                c += 1 if gc > c else -1
            self.grid[gr, gc] = 0

    def _remove_unreachable_cells(self, start: tuple[int, int]) -> None:
        q = deque([start])
        reached = {start}
        while q:
            r, c = q.popleft()
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nb = (r + dr, c + dc)
                rr, cc = nb
                if 0 <= rr < self.rows and 0 <= cc < self.cols and self.grid[rr, cc] == 0 and nb not in reached:
                    reached.add(nb)
                    q.append(nb)
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r, c] == 0 and (r, c) not in reached:
                    self.grid[r, c] = 1

    def is_free(self, cell: tuple[int, int]) -> bool:
        r, c = cell
        return 0 <= r < self.rows and 0 <= c < self.cols and self.grid[r, c] == 0

    def neighbors4(self, cell: tuple[int, int]) -> list[tuple[int, int]]:
        r, c = cell
        out = []
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nb = (r + dr, c + dc)
            if self.is_free(nb):
                out.append(nb)
        return out

    def all_distances(self, start: tuple[int, int]) -> dict[tuple[int, int], int]:
        if start in self._dist_cache:
            return self._dist_cache[start]
        dist = {start: 0}
        q = deque([start])
        while q:
            cur = q.popleft()
            for nb in self.neighbors4(cur):
                if nb not in dist:
                    dist[nb] = dist[cur] + 1
                    q.append(nb)
        self._dist_cache[start] = dist
        return dist

    def distance(self, start: tuple[int, int], goal: tuple[int, int]) -> float:
        return float(self.all_distances(start).get(goal, math.inf))

    def path(self, start: tuple[int, int], goal: tuple[int, int]) -> list[tuple[int, int]]:
        if start == goal:
            return []
        q = deque([start])
        prev = {start: None}
        while q:
            cur = q.popleft()
            for nb in self.neighbors4(cur):
                if nb in prev:
                    continue
                prev[nb] = cur
                if nb == goal:
                    path = [goal]
                    while path[-1] != start:
                        parent = prev[path[-1]]
                        if parent is None:
                            break
                        path.append(parent)
                    path.reverse()
                    return path[1:]
                q.append(nb)
        return []


def make_robots() -> list[PatentRobot]:
    robots = []
    for idx, (name, pos, energy, speed, radius, caps) in enumerate(START_SPECS):
        robots.append(
            PatentRobot(
                robot_id=idx,
                name=name,
                position=pos,
                energy=energy,
                speed=speed,
                radius=radius,
                capabilities=set(caps),
                color=ROBOT_COLORS[name],
                trajectory=[pos],
            )
        )
    return robots


def normalize(values: Iterable[float]) -> np.ndarray:
    arr = np.array(list(values), dtype=float)
    lo = float(arr.min())
    hi = float(arr.max())
    if hi - lo < 1e-9:
        return np.ones_like(arr)
    return (arr - lo) / (hi - lo)


def partition_zones(
    robots: list[PatentRobot],
    env: PatentGrid,
    active_only: bool = False,
) -> dict[int, set[tuple[int, int]]]:
    active = [r for r in robots if (not active_only or r.state != "responding")]
    energies = normalize(r.energy for r in active)
    speeds = normalize(r.speed for r in active)
    radii = normalize(r.radius for r in active)
    weights = 0.4 * energies + 0.3 * speeds + 0.3 * radii
    weights = np.clip(weights, 1e-6, None)

    zones = {r.robot_id: set() for r in robots}
    dist_maps = {r.robot_id: env.all_distances(r.position) for r in active}
    for cell in env.free_cells:
        best = None
        best_cost = math.inf
        for idx, robot in enumerate(active):
            d = dist_maps[robot.robot_id].get(cell, math.inf)
            cost = d / (weights[idx] + 1e-6)
            tie = robot.robot_id if best is None else best.robot_id
            if cost < best_cost - 1e-9 or (abs(cost - best_cost) <= 1e-9 and robot.robot_id < tie):
                best = robot
                best_cost = cost
        if best is not None:
            zones[best.robot_id].add(cell)

    for robot in robots:
        robot.zone = zones[robot.robot_id]
        robot.temp_zone.clear()
        robot.path.clear()
        robot.target = None
    return zones


def cover_nearby(robot: PatentRobot, env: PatentGrid, last_covered: np.ndarray, step: int) -> None:
    rr, cc = robot.position
    radius_sq = robot.radius * robot.radius
    r1 = max(0, rr - robot.radius)
    r2 = min(env.rows, rr + robot.radius + 1)
    c1 = max(0, cc - robot.radius)
    c2 = min(env.cols, cc + robot.radius + 1)
    for r in range(r1, r2):
        for c in range(c1, c2):
            if env.grid[r, c] == 0 and (r - rr) ** 2 + (c - cc) ** 2 <= radius_sq:
                last_covered[r, c] = step


def boundary_bonus(cell: tuple[int, int], zone: set[tuple[int, int]], env: PatentGrid) -> float:
    r, c = cell
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nb = (r + dr, c + dc)
        if nb not in zone or not env.is_free(nb):
            return 1.0
    return 0.0


def choose_patrol_target(
    robot: PatentRobot,
    env: PatentGrid,
    last_covered: np.ndarray,
    step: int,
    recovery_bias: bool = False,
    use_idleness: bool = True,
) -> tuple[int, int] | None:
    zone = robot.effective_zone
    if not zone:
        return None
    distances = env.all_distances(robot.position)
    reachable = [cell for cell in zone if cell in distances]
    local = [cell for cell in reachable if distances[cell] <= SEARCH_RADIUS]
    candidates = local or reachable
    if not candidates:
        return None

    idles = np.array([max(0, step - int(last_covered[cell])) for cell in candidates], dtype=float)
    dists = np.array([distances[cell] for cell in candidates], dtype=float)
    idle_norm = idles / max(float(idles.max()), 1.0)
    dist_norm = dists / max(float(dists.max()), 1.0)
    bonus = np.array([boundary_bonus(cell, zone, env) for cell in candidates], dtype=float)
    if not use_idleness:
        score = -0.78 * dist_norm + 0.22 * bonus
    elif recovery_bias:
        score = 0.78 * idle_norm - 0.17 * dist_norm + 0.05 * bonus
    else:
        score = 0.55 * idle_norm - 0.30 * dist_norm + 0.15 * bonus
    best_idx = int(np.argmax(score))
    return candidates[best_idx]


def step_patrol_robot(
    robot: PatentRobot,
    env: PatentGrid,
    last_covered: np.ndarray,
    step: int,
    recovery_bias: bool,
    use_idleness: bool = True,
) -> None:
    if robot.replan_delay > 0:
        robot.replan_delay -= 1
        return
    robot.move_credit += robot.speed
    while robot.move_credit >= 1.0:
        robot.move_credit -= 1.0
        if not robot.path:
            target = choose_patrol_target(robot, env, last_covered, step, recovery_bias, use_idleness)
            if target is None:
                return
            robot.target = target
            robot.path = env.path(robot.position, target)
        if robot.path:
            robot.position = robot.path.pop(0)
            robot.trajectory.append(robot.position)
            robot.energy = max(0.0, robot.energy - 0.0008)
        else:
            return


def step_responding_robot(robot: PatentRobot, env: PatentGrid, step: int) -> None:
    robot.move_credit += max(robot.speed, 1.0)
    while robot.move_credit >= 1.0:
        robot.move_credit -= 1.0
        if robot.position == TASK_POS:
            if robot.event_arrival_step is None:
                robot.event_arrival_step = step
            return
        if not robot.path:
            robot.path = env.path(robot.position, TASK_POS)
        if robot.path:
            robot.position = robot.path.pop(0)
            robot.trajectory.append(robot.position)
            robot.energy = max(0.0, robot.energy - 0.0012)
        else:
            return


def task_utility(robot: PatentRobot, env: PatentGrid, robots: list[PatentRobot]) -> float:
    if "emergency" not in robot.capabilities or robot.energy < SAFE_ENERGY or robot.state == "fault":
        return -math.inf
    distances = [env.distance(r.position, TASK_POS) for r in robots]
    max_dist = max(d for d in distances if math.isfinite(d))
    f_time = 1.0 - env.distance(robot.position, TASK_POS) / max(max_dist, 1.0)
    soft = {"inspect", "service"}
    q = len(robot.capabilities & soft) / len(soft)
    f_energy = robot.energy
    f_free = 1.0 if robot.state == "patrol" else 0.35
    return 0.40 * f_time + 0.30 * q + 0.15 * f_energy + 0.15 * f_free


def choose_patent_responder(robots: list[PatentRobot], env: PatentGrid) -> tuple[PatentRobot, dict[str, float]]:
    scores = {r.name: task_utility(r, env, robots) for r in robots}
    winner = max(robots, key=lambda r: scores[r.name])
    return winner, scores


def choose_baseline_responder(robots: list[PatentRobot], env: PatentGrid) -> PatentRobot:
    candidates = [r for r in robots if r.energy >= SAFE_ENERGY and r.state != "fault"]
    return min(candidates, key=lambda r: env.distance(r.position, TASK_POS))


def split_hole_subblocks(
    hole: set[tuple[int, int]],
    env: PatentGrid,
    count: int = 3,
) -> list[set[tuple[int, int]]]:
    cells = list(hole)
    if not cells:
        return []
    coords = np.array(cells)
    seed_indices = [
        int(np.argmin(coords[:, 0] + coords[:, 1])),
        int(np.argmin(coords[:, 0] - coords[:, 1])),
        int(np.argmax(coords[:, 0] + coords[:, 1])),
    ][:count]
    seeds = [cells[i] for i in seed_indices]
    subblocks = [set([seed]) for seed in seeds]
    assigned = set(seeds)
    queues = [deque([seed]) for seed in seeds]
    while len(assigned) < len(hole):
        progressed = False
        for idx, q in enumerate(queues):
            if not q:
                continue
            cur = q.popleft()
            for nb in env.neighbors4(cur):
                if nb in hole and nb not in assigned:
                    subblocks[idx].add(nb)
                    assigned.add(nb)
                    q.append(nb)
                    progressed = True
        if not progressed:
            remaining = [cell for cell in cells if cell not in assigned]
            for cell in remaining:
                nearest = int(np.argmin([abs(cell[0] - s[0]) + abs(cell[1] - s[1]) for s in seeds]))
                subblocks[nearest].add(cell)
                assigned.add(cell)
    return [block for block in subblocks if block]


def average_idleness(block: set[tuple[int, int]], last_covered: np.ndarray, step: int) -> float:
    if not block:
        return 0.0
    return float(np.mean([max(0, step - int(last_covered[cell])) for cell in block]))


def touches_zone(block: set[tuple[int, int]], zone: set[tuple[int, int]], env: PatentGrid) -> bool:
    for cell in block:
        for nb in env.neighbors4(cell):
            if nb in zone:
                return True
    return False


def assign_hole_subblocks(
    responder: PatentRobot,
    robots: list[PatentRobot],
    env: PatentGrid,
    hole: set[tuple[int, int]],
    last_covered: np.ndarray,
    step: int,
) -> dict[str, dict[str, object]]:
    subblocks = split_hole_subblocks(hole, env, count=3)
    assignments: dict[str, dict[str, object]] = {}
    for idx, block in enumerate(subblocks, start=1):
        label = f"H{idx}"
        candidates = [
            r
            for r in robots
            if r.robot_id != responder.robot_id
            and r.energy >= SAFE_ENERGY
            and r.state != "responding"
            and touches_zone(block, r.zone, env)
        ]
        if not candidates:
            candidates = [
                r
                for r in robots
                if r.robot_id != responder.robot_id and r.energy >= SAFE_ENERGY and r.state != "responding"
            ]
        block_idle = average_idleness(block, last_covered, step)
        idle_norm = min(block_idle / max(step, 1), 1.0)
        centroid = block_centroid(block)

        scores = {}
        for robot in candidates:
            min_d = min(env.distance(robot.position, cell) for cell in block)
            f_adj = 1.0 - min(min_d / (env.rows + env.cols), 1.0)
            f_free = 1.0 - min(len(robot.temp_zone) / max(len(robot.zone), 1), 1.0)
            f_energy = robot.energy
            scores[robot.name] = 0.35 * f_adj + 0.25 * f_free + 0.20 * f_energy + 0.20 * idle_norm * f_adj
        winner = max(candidates, key=lambda r: scores[r.name])
        winner.temp_zone |= block
        winner.assigned_subblocks.append(label)
        assignments[label] = {
            "cells": block,
            "robot": winner,
            "centroid": centroid,
            "score": scores[winner.name],
        }
    responder.zone -= hole
    return assignments


def block_centroid(block: set[tuple[int, int]]) -> tuple[float, float]:
    arr = np.array(list(block), dtype=float)
    return float(arr[:, 0].mean()), float(arr[:, 1].mean())


def metric_snapshot(
    robots: list[PatentRobot],
    env: PatentGrid,
    last_covered: np.ndarray,
    step: int,
    global_replans: int,
) -> dict[str, float]:
    idles = np.array([max(0, step - int(last_covered[cell])) for cell in env.free_cells], dtype=float)
    covered_recent = sum(1 for cell in env.free_cells if 0 <= step - int(last_covered[cell]) <= WINDOW)
    loads = np.array([len(r.effective_zone) for r in robots], dtype=float)
    return {
        "step": step,
        "coverage": covered_recent / len(env.free_cells),
        "i_max": float(idles.max()),
        "i_mean": float(idles.mean()),
        "load_std": float(loads.std()),
        "global_replans": float(global_replans),
    }


def clone_snapshot(robots: list[PatentRobot]) -> list[PatentRobot]:
    return [r.clone() for r in robots]


def run_method(method: str, seed: int = BASE_OBSTACLE_SEED) -> dict[str, object]:
    env = PatentGrid(seed=seed)
    robots = make_robots()
    partition_zones(robots, env)
    last_covered = np.zeros((env.rows, env.cols), dtype=int)
    for robot in robots:
        cover_nearby(robot, env, last_covered, 0)

    initial_robots = clone_snapshot(robots)
    initial_zones = {r.robot_id: set(r.zone) for r in robots}
    metrics = [metric_snapshot(robots, env, last_covered, 0, 0)]
    global_replans = 0
    responder: PatentRobot | None = None
    response_scores: dict[str, float] = {}
    hole: set[tuple[int, int]] = set()
    subblock_assignments: dict[str, dict[str, object]] = {}
    event_snapshot = None
    recovery_snapshot = None
    response_time: int | None = None

    for step in range(1, TOTAL_STEPS + 1):
        if step == EVENT_STEP:
            if method == "patent":
                responder, response_scores = choose_patent_responder(robots, env)
                hole = set(responder.zone)
                responder.state = "responding"
                responder.path = env.path(responder.position, TASK_POS)
                subblock_assignments = assign_hole_subblocks(
                    responder, robots, env, hole, last_covered, step
                )
            else:
                responder = choose_baseline_responder(robots, env)
                response_scores = {r.name: -env.distance(r.position, TASK_POS) for r in robots}
                responder.state = "responding"
                responder.path = env.path(responder.position, TASK_POS)
                partition_zones(robots, env, active_only=True)
                for robot in robots:
                    if robot.state != "responding":
                        robot.replan_delay = BASELINE_REPLAN_DELAY
                global_replans += 1
            event_snapshot = {
                "robots": clone_snapshot(robots),
                "zones": {r.robot_id: set(r.zone) for r in robots},
                "last_covered": last_covered.copy(),
                "hole": set(hole),
                "assignments": subblock_assignments.copy(),
                "responder": responder.name,
                "scores": dict(response_scores),
            }

        recovery_bias = step >= RETURN_STEP and method == "patent"
        for robot in robots:
            if robot.state == "responding":
                step_responding_robot(robot, env, step)
                if robot.event_arrival_step is not None and response_time is None:
                    response_time = robot.event_arrival_step - EVENT_STEP
            else:
                use_idleness = method == "patent" or step < EVENT_STEP
                step_patrol_robot(robot, env, last_covered, step, recovery_bias, use_idleness)

        for robot in robots:
            cover_nearby(robot, env, last_covered, step)

        if step == RETURN_STEP and responder is not None:
            responder.state = "patrol"
            responder.path.clear()
            responder.target = None
            partition_zones(robots, env)
            if method == "baseline":
                for robot in robots:
                    robot.replan_delay = BASELINE_REPLAN_DELAY
            global_replans += 1
            recovery_snapshot = {
                "robots": clone_snapshot(robots),
                "zones": {r.robot_id: set(r.zone) for r in robots},
                "last_covered": last_covered.copy(),
                "responder": responder.name,
            }

        metrics.append(metric_snapshot(robots, env, last_covered, step, global_replans))

    if response_time is None and responder is not None and responder.event_arrival_step is not None:
        response_time = responder.event_arrival_step - EVENT_STEP
    result = {
        "method": method,
        "env": env,
        "robots": robots,
        "initial_robots": initial_robots,
        "initial_zones": initial_zones,
        "metrics": metrics,
        "event_snapshot": event_snapshot,
        "recovery_snapshot": recovery_snapshot,
        "response_time": response_time if response_time is not None else -1,
        "global_replans": global_replans,
        "hole": hole,
        "assignments": subblock_assignments,
    }
    return result


def zone_image(
    zones: dict[int, set[tuple[int, int]]],
    robots: list[PatentRobot],
    env: PatentGrid,
    alpha: float = 0.28,
) -> np.ndarray:
    img = np.ones((env.rows, env.cols, 4), dtype=float)
    img[:, :, :] = to_rgba("#ffffff")
    by_id = {r.robot_id: r for r in robots}
    for rid, cells in zones.items():
        rgba = np.array(to_rgba(by_id[rid].color, alpha))
        for r, c in cells:
            img[r, c, :] = rgba
    return img


def draw_base(
    ax: plt.Axes,
    env: PatentGrid,
    robots: list[PatentRobot],
    zones: dict[int, set[tuple[int, int]]] | None = None,
    time_label: str | None = None,
) -> None:
    ax.set_facecolor("white")
    if zones is not None:
        ax.imshow(zone_image(zones, robots, env), extent=[0, env.cols, env.rows, 0], interpolation="none")
        draw_zone_boundaries(ax, zones, env)
    obstacle = np.zeros((env.rows, env.cols, 4), dtype=float)
    obstacle[:, :, :] = to_rgba("#ffffff", 0.0)
    obstacle[env.grid == 1] = to_rgba("#858585", 0.95)
    ax.imshow(obstacle, extent=[0, env.cols, env.rows, 0], interpolation="none")

    free_r, free_c = zip(*sorted(env.free_cells))
    ax.scatter(np.array(free_c) + 0.5, np.array(free_r) + 0.5, s=1.8, c="#d8d8d8", alpha=0.28, linewidths=0)
    ax.set_xlim(0, env.cols)
    ax.set_ylim(env.rows, 0)
    ax.set_aspect("equal")
    ax.set_xticks(np.arange(0, env.cols + 1, 5))
    ax.set_yticks(np.arange(0, env.rows + 1, 5))
    ax.tick_params(labelsize=6, length=2, colors="#666666")
    ax.grid(color="#e6e6e6", linewidth=0.22)
    for spine in ax.spines.values():
        spine.set_linewidth(0.8)
        spine.set_color("#222222")
    if time_label:
        ax.text(
            0.985,
            0.985,
            time_label,
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=7,
            color="#111111",
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.72, pad=1.4),
            zorder=20,
        )


def draw_zone_boundaries(ax: plt.Axes, zones: dict[int, set[tuple[int, int]]], env: PatentGrid) -> None:
    owner = {}
    for rid, cells in zones.items():
        for cell in cells:
            owner[cell] = rid
    segments = []
    for r in range(env.rows):
        for c in range(env.cols):
            if env.grid[r, c] == 1:
                continue
            rid = owner.get((r, c))
            if rid is None:
                continue
            right = owner.get((r, c + 1))
            down = owner.get((r + 1, c))
            if right is not None and right != rid:
                segments.append([(c + 1, r), (c + 1, r + 1)])
            if down is not None and down != rid:
                segments.append([(c, r + 1), (c + 1, r + 1)])
    ax.add_collection(LineCollection(segments, colors="#111111", linewidths=0.58, alpha=0.92))


def draw_robots(
    ax: plt.Axes,
    robots: list[PatentRobot],
    emphasize: str | None = None,
    muted: set[str] | None = None,
) -> None:
    muted = muted or set()
    for robot in robots:
        r, c = robot.position
        size = 78 if robot.name != emphasize else 130
        face = "#9b9b9b" if robot.name in muted else robot.color
        text_color = "#666666" if robot.name in muted else "#111111"
        ax.scatter(c + 0.5, r + 0.5, s=size, c=face, edgecolors="#111111", linewidths=0.75, zorder=8)
        ax.text(c + 0.9, r + 0.1, robot.name, fontsize=7.2, color=text_color, weight="bold", zorder=9)
        if robot.name == emphasize:
            ax.scatter(
                c + 0.5,
                r + 0.5,
                s=235,
                facecolors="none",
                edgecolors="#111111",
                linewidths=1.15,
                zorder=7,
            )


def draw_path(
    ax: plt.Axes,
    path: list[tuple[int, int]],
    color: str,
    linewidth: float = 0.8,
    alpha: float = 0.75,
    linestyle: str = "-",
) -> None:
    if len(path) < 2:
        return
    pts = np.array([(c + 0.5, r + 0.5) for r, c in path])
    ax.plot(pts[:, 0], pts[:, 1], color=color, linewidth=linewidth, alpha=alpha, linestyle=linestyle, zorder=6)


def draw_arrow(
    ax: plt.Axes,
    start: tuple[float, float],
    end: tuple[float, float],
    color: str,
    lw: float = 1.6,
    linestyle: str = "-",
) -> None:
    ax.annotate(
        "",
        xy=(end[1] + 0.5, end[0] + 0.5),
        xytext=(start[1] + 0.5, start[0] + 0.5),
        arrowprops=dict(arrowstyle="->", color=color, lw=lw, linestyle=linestyle, shrinkA=4, shrinkB=4),
        zorder=10,
    )


def draw_path_arrow(
    ax: plt.Axes,
    path: list[tuple[int, int]],
    color: str,
    linewidth: float = 1.25,
    linestyle: str = "-",
) -> None:
    if len(path) < 2:
        return
    draw_path(ax, path, color, linewidth=linewidth, alpha=0.88, linestyle=linestyle)
    draw_arrow(ax, path[-2], path[-1], color, lw=linewidth, linestyle=linestyle)


def draw_hole(ax: plt.Axes, hole: set[tuple[int, int]], color: str = "#d65f5f", hatch: str = "///") -> None:
    for r, c in hole:
        ax.add_patch(
            Rectangle(
                (c, r),
                1,
                1,
                facecolor=to_rgba(color, 0.075),
                edgecolor=to_rgba(color, 0.35),
                linewidth=0.08,
                hatch=hatch,
                zorder=4,
            )
        )
    draw_cell_outline(ax, hole, color=color, linewidth=1.05, linestyle="--")


def draw_cell_outline(
    ax: plt.Axes,
    cells: set[tuple[int, int]],
    color: str = "#222222",
    linewidth: float = 1.0,
    linestyle: str = "-",
) -> None:
    segments = []
    for r, c in cells:
        for side, nb in [
            ("top", (r - 1, c)),
            ("bottom", (r + 1, c)),
            ("left", (r, c - 1)),
            ("right", (r, c + 1)),
        ]:
            if nb in cells:
                continue
            if side == "top":
                segments.append([(c, r), (c + 1, r)])
            elif side == "bottom":
                segments.append([(c, r + 1), (c + 1, r + 1)])
            elif side == "left":
                segments.append([(c, r), (c, r + 1)])
            else:
                segments.append([(c + 1, r), (c + 1, r + 1)])
    ax.add_collection(LineCollection(segments, colors=color, linewidths=linewidth, linestyles=linestyle, zorder=7))


def add_common_legend(
    ax: plt.Axes,
    robots: list[PatentRobot],
    extra: list[object] | None = None,
    include_robots: bool = True,
    outside: bool = True,
) -> None:
    handles = []
    if include_robots:
        handles.extend(
            [
                Line2D([0], [0], marker="o", color="none", markerfacecolor=r.color, markeredgecolor="#111111", markersize=5.8, label=r.name)
                for r in robots
            ]
        )
        handles.extend(
            [
                Patch(facecolor="#858585", edgecolor="#858585", label="Obstacle"),
                Line2D([0], [0], color="#111111", lw=0.7, label="Zone boundary"),
            ]
        )
    if extra:
        handles.extend(extra)
    if not handles:
        return
    if outside:
        ax.legend(
            handles=handles,
            loc="center left",
            bbox_to_anchor=(1.02, 0.5),
            fontsize=5.8,
            frameon=True,
            framealpha=0.78,
            borderpad=0.45,
            labelspacing=0.36,
            handlelength=1.6,
        )
    else:
        ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.01, 0.01), fontsize=5.8, frameon=True, framealpha=0.75)


def save_figure(fig: plt.Figure, name: str) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    fig.savefig(OUTPUT_DIR / f"{name}.png", dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(OUTPUT_DIR / f"{name}.svg", bbox_inches="tight", facecolor="white")
    fig.savefig(OUTPUT_DIR / f"{name}.pdf", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_fig2(result: dict[str, object]) -> None:
    env: PatentGrid = result["env"]  # type: ignore[assignment]
    robots: list[PatentRobot] = result["initial_robots"]  # type: ignore[assignment]
    zones: dict[int, set[tuple[int, int]]] = result["initial_zones"]  # type: ignore[assignment]
    fig, ax = plt.subplots(figsize=(6.6, 6.2))
    draw_base(ax, env, robots, zones, "t=0")
    for robot in robots:
        zone_cells = sorted(robot.zone, key=lambda x: (x[0], x[1]))
        sample_path = nearest_sweep_path(env, robot.position, zone_cells[: min(80, len(zone_cells))])
        draw_path(ax, sample_path, robot.color, linewidth=0.55, alpha=0.42, linestyle=(0, (2.2, 2.2)))
    draw_robots(ax, robots)
    add_common_legend(ax, robots, [Line2D([0], [0], color="#555555", lw=0.65, linestyle=(0, (2.2, 2.2)), label="Coverage route")])
    save_figure(fig, "fig2_initial_partition")


def nearest_sweep_path(
    env: PatentGrid,
    start: tuple[int, int],
    cells: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    remaining = set(cells)
    cur = start
    path = [start]
    for _ in range(min(35, len(remaining))):
        if not remaining:
            break
        target = min(remaining, key=lambda cell: env.distance(cur, cell))
        leg = env.path(cur, target)
        path.extend(leg)
        cur = target
        remaining.remove(target)
    return path


def plot_fig3(result: dict[str, object]) -> None:
    env: PatentGrid = result["env"]  # type: ignore[assignment]
    snapshot = result["event_snapshot"]
    if snapshot is None:
        return
    robots: list[PatentRobot] = snapshot["robots"]  # type: ignore[index,assignment]
    zones = snapshot["zones"]  # type: ignore[index,assignment]
    hole = snapshot["hole"]  # type: ignore[index,assignment]
    responder_name = snapshot["responder"]  # type: ignore[index,assignment]
    responder = next(r for r in robots if r.name == responder_name)

    fig, ax = plt.subplots(figsize=(6.6, 6.2))
    draw_base(ax, env, robots, zones, r"$t=t_e$")
    draw_hole(ax, hole, hatch="/")
    response_path = [responder.position] + env.path(responder.position, TASK_POS)
    draw_path_arrow(ax, response_path, responder.color, linewidth=1.15)
    ax.scatter(TASK_POS[1] + 0.5, TASK_POS[0] + 0.5, s=180, marker="*", c="#ffd23f", edgecolors="#111111", linewidths=0.9, zorder=10)
    ax.text(TASK_POS[1] + 1.0, TASK_POS[0] - 0.8, r"$T_{\tau}$", fontsize=8.5, weight="bold")
    h_centroid = block_centroid(hole)
    ax.text(h_centroid[1] + 0.25, h_centroid[0] + 0.25, r"$H_{\tau}$", fontsize=9, color="#9b2f2f", weight="bold", zorder=11)
    draw_robots(ax, robots, emphasize=responder_name)
    add_common_legend(
        ax,
        robots,
        [
            Line2D([0], [0], marker="*", color="none", markerfacecolor="#ffd23f", markeredgecolor="#111111", markersize=9, label=r"$T_{\tau}$"),
            Patch(facecolor=to_rgba("#d65f5f", 0.09), edgecolor="#d65f5f", hatch="/", label=r"$H_{\tau}$"),
            Line2D([0], [0], color=responder.color, lw=1.15, label="response path"),
        ],
        include_robots=False,
    )
    save_figure(fig, "fig3_event_and_hole")


def plot_fig4(result: dict[str, object]) -> None:
    env: PatentGrid = result["env"]  # type: ignore[assignment]
    snapshot = result["event_snapshot"]
    if snapshot is None:
        return
    robots: list[PatentRobot] = snapshot["robots"]  # type: ignore[index,assignment]
    zones = snapshot["zones"]  # type: ignore[index,assignment]
    assignments = snapshot["assignments"]  # type: ignore[index,assignment]
    responder_name = snapshot["responder"]  # type: ignore[index,assignment]
    display_robots = clone_snapshot(robots)
    responder = next(r for r in display_robots if r.name == responder_name)
    original_pos = responder.position
    response_path = [original_pos] + env.path(original_pos, TASK_POS)
    if len(response_path) > 4:
        responder.position = response_path[-4]
    else:
        responder.position = TASK_POS

    fig, ax = plt.subplots(figsize=(6.6, 6.2))
    draw_base(ax, env, display_robots, zones, r"$t=t_e$")
    draw_path(ax, response_path[: response_path.index(responder.position) + 1] if responder.position in response_path else response_path, "#777777", linewidth=0.85, alpha=0.75, linestyle=(0, (2, 2)))
    ax.scatter(TASK_POS[1] + 0.5, TASK_POS[0] + 0.5, s=130, marker="*", c="#ffd23f", edgecolors="#111111", linewidths=0.8, zorder=10)
    ax.text(TASK_POS[1] + 1.0, TASK_POS[0] - 0.8, r"$T_{\tau}$", fontsize=8.5, weight="bold")
    fill_colors = ["#f4a582", "#92c5de", "#b2df8a"]
    for idx, (label, info) in enumerate(assignments.items()):
        block = info["cells"]
        owner: PatentRobot = info["robot"]
        color = fill_colors[idx % len(fill_colors)]
        for r, c in block:
            ax.add_patch(
                Rectangle(
                    (c, r),
                    1,
                    1,
                    facecolor=to_rgba(color, 0.30),
                    edgecolor=to_rgba("#444444", 0.35),
                    linewidth=0.12,
                    zorder=4,
                )
            )
        draw_cell_outline(ax, block, color="#333333", linewidth=1.05, linestyle="-")
        centroid = info["centroid"]
        ax.text(centroid[1] + 0.25, centroid[0] + 0.25, rf"$H_{{\tau,{idx + 1}}}$", fontsize=9, weight="bold", zorder=11)
        display_owner = next(r for r in display_robots if r.name == owner.name)
        draw_arrow(ax, display_owner.position, centroid, owner.color, lw=1.35, linestyle=(0, (3, 2)))
        mid_r = (display_owner.position[0] + centroid[0]) / 2.0
        mid_c = (display_owner.position[1] + centroid[1]) / 2.0
        ax.text(mid_c + 0.45, mid_r + 0.45, rf"$j_{{\tau,{idx + 1}}}$", fontsize=8, color="#111111", zorder=11)
    draw_robots(ax, display_robots, muted={responder_name})
    add_common_legend(
        ax,
        display_robots,
        [
            Patch(facecolor=to_rgba("#f4a582", 0.30), edgecolor="#333333", label=r"$H_{\tau,q}$"),
            Line2D([0], [0], color="#333333", lw=1.1, linestyle=(0, (3, 2)), label=r"$j_{\tau,q}$"),
            Line2D([0], [0], marker="o", color="none", markerfacecolor="#9b9b9b", markeredgecolor="#111111", markersize=5.8, label="responding"),
        ],
        include_robots=False,
    )
    save_figure(fig, "fig4_hole_subblocks_repair")


def plot_fig5(result: dict[str, object]) -> None:
    env: PatentGrid = result["env"]  # type: ignore[assignment]
    snapshot = result["recovery_snapshot"]
    if snapshot is None:
        return
    robots: list[PatentRobot] = snapshot["robots"]  # type: ignore[index,assignment]
    zones = snapshot["zones"]  # type: ignore[index,assignment]
    last_covered: np.ndarray = snapshot["last_covered"]  # type: ignore[index,assignment]
    fig, ax = plt.subplots(figsize=(6.6, 6.2))
    draw_base(ax, env, robots, zones, r"$t=t_r$")
    idleness = np.full((env.rows, env.cols), np.nan)
    for cell in env.free_cells:
        idleness[cell] = max(0, RETURN_STEP - int(last_covered[cell]))
    cmap = plt.get_cmap("YlOrRd").copy()
    cmap.set_bad((1, 1, 1, 0))
    ax.imshow(idleness, extent=[0, env.cols, env.rows, 0], cmap=cmap, alpha=0.50, interpolation="none")
    high_threshold = float(np.nanpercentile(idleness, 86))
    high_cells = {cell for cell in env.free_cells if idleness[cell] >= high_threshold}
    draw_cell_outline(ax, high_cells, color="#d97904", linewidth=0.95, linestyle="-")
    draw_zone_boundaries(ax, zones, env)
    for robot in robots:
        if robot.zone:
            high_idle = max(robot.zone, key=lambda cell: idleness[cell] if not np.isnan(idleness[cell]) else -1)
            draw_arrow(ax, robot.position, high_idle, robot.color, lw=1.55)
            ax.scatter(high_idle[1] + 0.5, high_idle[0] + 0.5, s=82, marker="x", c="#111111", linewidths=1.45, zorder=12)
            suffix = robot.name.split("-")[-1]
            ax.text(high_idle[1] + 0.75, high_idle[0] - 0.35, rf"$g_{{{suffix}}}^{{rec}}$", fontsize=8.2, weight="bold", zorder=13)
    draw_robots(ax, robots)
    add_common_legend(
        ax,
        robots,
        [
            Patch(facecolor=to_rgba("#cc4c02", 0.30), edgecolor="#d97904", label="high idleness"),
            Line2D([0], [0], marker="x", color="#111111", lw=0, markersize=6, label=r"$g_i^{rec}$"),
        ],
        include_robots=False,
    )
    save_figure(fig, "fig5_recovery_with_idleness")


def series_from_runs(runs: list[dict[str, object]], key: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    values = np.array([[m[key] for m in result["metrics"]] for result in runs], dtype=float)  # type: ignore[index]
    steps = np.array([m["step"] for m in runs[0]["metrics"]], dtype=float)  # type: ignore[index]
    return steps, values.mean(axis=0), values.std(axis=0)


def plot_fig6(patent_runs: list[dict[str, object]], baseline_runs: list[dict[str, object]]) -> None:
    p_step, p_cov, p_cov_std = series_from_runs(patent_runs, "coverage")
    _, p_imax, p_imax_std = series_from_runs(patent_runs, "i_max")
    b_step, b_cov, b_cov_std = series_from_runs(baseline_runs, "coverage")
    _, b_imax, b_imax_std = series_from_runs(baseline_runs, "i_max")

    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.1), sharex=True)
    axes[0].plot(p_step, p_cov, color="#2f7f4f", lw=2.0, label="本发明方法")
    axes[0].fill_between(p_step, p_cov - p_cov_std, p_cov + p_cov_std, color="#2f7f4f", alpha=0.12, linewidth=0)
    axes[0].plot(b_step, b_cov, color="#4c78a8", lw=2.0, linestyle="--", label="最近原则+全局重规划")
    axes[0].fill_between(b_step, b_cov - b_cov_std, b_cov + b_cov_std, color="#4c78a8", alpha=0.12, linewidth=0)
    axes[0].set_title("(a) Cov(t)", fontsize=10)
    axes[0].set_ylabel(f"Coverage ratio (sliding window W={WINDOW})")
    axes[0].set_ylim(0, 1.02)

    axes[1].plot(p_step, p_imax, color="#2f7f4f", lw=2.0, label="本发明方法")
    axes[1].fill_between(p_step, p_imax - p_imax_std, p_imax + p_imax_std, color="#2f7f4f", alpha=0.12, linewidth=0)
    axes[1].plot(b_step, b_imax, color="#4c78a8", lw=2.0, linestyle="--", label="最近原则+全局重规划")
    axes[1].fill_between(b_step, b_imax - b_imax_std, b_imax + b_imax_std, color="#4c78a8", alpha=0.12, linewidth=0)
    axes[1].set_title("(b) Maximum idleness", fontsize=10)
    axes[1].set_ylabel("Maximum idleness")

    for ax in axes:
        ax.axvline(EVENT_STEP, color="#a33b3b", lw=1.3, linestyle=":", label="t_e" if ax is axes[0] else None)
        ax.axvline(RETURN_STEP, color="#555555", lw=1.3, linestyle="-.", label="t_r" if ax is axes[0] else None)
        ax.text(EVENT_STEP + 2, ax.get_ylim()[1] * 0.92, r"$t_e$", fontsize=9, color="#a33b3b")
        ax.text(RETURN_STEP + 2, ax.get_ylim()[1] * 0.84, r"$t_r$", fontsize=9, color="#333333")
        ax.set_xlabel("Time step")
        ax.grid(True, color="#dddddd", linewidth=0.7)
        ax.tick_params(labelsize=8)
        for spine in ax.spines.values():
            spine.set_color("#222222")
            spine.set_linewidth(0.8)
    axes[0].legend(loc="lower right", fontsize=8, frameon=True, framealpha=0.95)
    save_figure(fig, "fig6_coverage_idleness_comparison")


def summarize_runs(runs: list[dict[str, object]]) -> dict[str, float]:
    response_times = np.array([float(result["response_time"]) for result in runs], dtype=float)
    replans = np.array([float(result["global_replans"]) for result in runs], dtype=float)
    event_min_cov = []
    mean_cov = []
    peak_i_max = []
    mean_load_std = []
    for result in runs:
        metrics = result["metrics"]  # type: ignore[assignment]
        event_metrics = [m for m in metrics if EVENT_STEP <= m["step"] <= RETURN_STEP]
        event_min_cov.append(min(m["coverage"] for m in event_metrics))
        mean_cov.append(float(np.mean([m["coverage"] for m in metrics])))
        peak_i_max.append(max(m["i_max"] for m in metrics))
        mean_load_std.append(float(np.mean([m["load_std"] for m in metrics])))
    return {
        "response_time": float(response_times.mean()),
        "event_min_coverage": float(np.mean(event_min_cov)),
        "mean_coverage": float(np.mean(mean_cov)),
        "peak_i_max": float(np.mean(peak_i_max)),
        "global_replans": float(replans.mean()),
        "load_std": float(np.mean(mean_load_std)),
    }


def write_metrics_table(patent_runs: list[dict[str, object]], baseline_runs: list[dict[str, object]]) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    rows = []
    for runs, label in [(baseline_runs, "最近原则+全局重规划"), (patent_runs, "本发明方法")]:
        summary = summarize_runs(runs)
        rows.append(
            {
                "method": label,
                "avg_response_time_steps": f"{summary['response_time']:.2f}",
                "event_min_coverage": f"{summary['event_min_coverage']:.4f}",
                "avg_coverage": f"{summary['mean_coverage']:.4f}",
                "peak_i_max": f"{summary['peak_i_max']:.2f}",
                "global_replans": f"{summary['global_replans']:.2f}",
                "avg_load_std": f"{summary['load_std']:.2f}",
            }
        )
    with (OUTPUT_DIR / "table_metrics.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def configure_fonts() -> None:
    available = {font.name for font in fm.fontManager.ttflist}
    for candidate in ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial Unicode MS"]:
        if candidate in available:
            plt.rcParams["font.sans-serif"] = [candidate, "DejaVu Sans"]
            break
    plt.rcParams["axes.unicode_minus"] = False


def run_many(method: str, n: int = NUM_SEEDS) -> list[dict[str, object]]:
    return [run_method(method, seed=BASE_OBSTACLE_SEED + idx * 17) for idx in range(n)]


def main() -> None:
    configure_fonts()
    patent = run_method("patent", seed=BASE_OBSTACLE_SEED)
    patent_runs = run_many("patent")
    baseline_runs = run_many("baseline")
    plot_fig2(patent)
    plot_fig3(patent)
    plot_fig4(patent)
    plot_fig5(patent)
    plot_fig6(patent_runs, baseline_runs)
    write_metrics_table(patent_runs, baseline_runs)
    print(f"Patent figures and metrics written to: {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
