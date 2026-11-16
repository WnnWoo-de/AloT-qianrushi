"""
模块4：空洞修补与恢复
=======================
流程：
  1. 检测被调走机器人责任区中的未覆盖区域（空洞）
  2. 仅在邻近机器人之间触发局部二次竞价
     B_k(H) = λ1·f_adj + λ2·f_freeload + λ3·f_battery
  3. 将空洞分配给得分最高的邻近机器人
  4. 任务结束后执行全局责任区重构（重新 Voronoi 划分）
"""
from collections import deque

import numpy as np
from config.algorithm_params import (
    HOLE_LAMBDA1,
    HOLE_LAMBDA2,
    HOLE_LAMBDA3,
    HOLE_NEIGHBOR_RADIUS,
)


# ──────────────────────────────────────────
# 空洞检测
# ──────────────────────────────────────────

def detect_holes(robot, env, include_visited: bool = False) -> set:
    """
    检测机器人责任区内尚未覆盖的自由栅格（空洞）。

    Parameters
    ----------
    robot : Robot
    env   : GridEnvironment

    Returns
    -------
    holes : set of (row, col)
    """
    free_in_zone = {cell for cell in robot.zone if env.is_free(*cell)}
    if include_visited:
        return free_in_zone
    return free_in_zone - robot.visited


def _hole_centroid(holes: set) -> tuple:
    """计算空洞区域的几何中心。"""
    if not holes:
        return (0, 0)
    arr = np.array(list(holes))
    return (float(arr[:, 0].mean()), float(arr[:, 1].mean()))


# ──────────────────────────────────────────
# 竞价得分计算
# ──────────────────────────────────────────

def _score_adjacency(robot, holes: set, env) -> float:
    """
    邻接距离得分 f_adj：机器人到空洞边界最近点的距离越近，得分越高。
    """
    from core.environment import GridEnvironment
    if not holes:
        return 0.0
    min_d = min(GridEnvironment.euclidean(robot.position, h) for h in holes)
    # 归一化：用地图对角线长度归一
    max_d = GridEnvironment.euclidean((0, 0), (env.rows, env.cols))
    return 1.0 - min(min_d / max_d, 1.0)


def _score_freeload(robot) -> float:
    """
    剩余可承担负载得分 f_freeload：剩余空闲容量越大得分越高。
    """
    remaining = robot.max_load - robot.load
    return remaining / robot.max_load if robot.max_load > 0 else 0.0


def _score_battery(battery: float) -> float:
    """电量得分 f_battery。"""
    return battery / 100.0


def compute_hole_bid(robot, holes: set, env,
                     lam1: float = HOLE_LAMBDA1,
                     lam2: float = HOLE_LAMBDA2,
                     lam3: float = HOLE_LAMBDA3) -> float:
    """
    计算机器人对空洞区域的竞价得分 B_k(H)。

    B_k(H) = λ1·f_adj + λ2·f_freeload + λ3·f_battery
    """
    f_adj      = _score_adjacency(robot, holes, env)
    f_freeload = _score_freeload(robot)
    f_battery  = _score_battery(robot.battery)
    return lam1 * f_adj + lam2 * f_freeload + lam3 * f_battery


# ──────────────────────────────────────────
# 邻近机器人筛选
# ──────────────────────────────────────────

def find_neighbors(source_robot, all_robots: list, env,
                   radius: float = HOLE_NEIGHBOR_RADIUS) -> list:
    """
    找出在搜索半径内的其他机器人（排除 source_robot 自身）。
    若半径内无机器人，自动放宽至全局所有机器人（保证总能找到接管者）。
    """
    from core.environment import GridEnvironment
    neighbors = []
    for r in all_robots:
        if r.robot_id == source_robot.robot_id:
            continue
        d = GridEnvironment.euclidean(r.position, source_robot.position)
        if d <= radius:
            neighbors.append(r)
    # 若邻居为空（机器人分布分散），对全图所有机器人开放
    if not neighbors:
        neighbors = [r for r in all_robots
                     if r.robot_id != source_robot.robot_id]
    return neighbors


# ──────────────────────────────────────────
# 局部二次竞价
# ──────────────────────────────────────────

def local_hole_bidding(source_robot, all_robots: list, holes: set, env) -> dict:
    """
    对 source_robot 的空洞区域，在邻近机器人之间发起局部二次竞价。

    Parameters
    ----------
    source_robot : Robot      产生空洞的机器人
    all_robots   : list       所有机器人
    holes        : set        待修补的空洞栅格集合
    env          : GridEnvironment

    Returns
    -------
    assignment : dict {robot_id: set of (row,col)}  分配给各邻近机器人的空洞子集
    """
    if not holes:
        return {}

    neighbors = find_neighbors(source_robot, all_robots, env)
    # 若没有邻居，尝试全局搜索
    if not neighbors:
        neighbors = [r for r in all_robots if r.robot_id != source_robot.robot_id]
    if not neighbors:
        return {}

    scores = {r.robot_id: compute_hole_bid(r, holes, env) for r in neighbors}
    ranked_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    robot_by_id = {r.robot_id: r for r in neighbors}
    unassigned = set(holes)

    def neighbors4(cell):
        r, c = cell
        out = []
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            rr, cc = r + dr, c + dc
            if env.is_valid(rr, cc):
                out.append((rr, cc))
        return out

    # 边界扩张：种子必须与接管机器人当前责任区相邻
    frontiers: dict[int, deque] = {}
    for rid in ranked_ids:
        rb = robot_by_id[rid]
        seeds = [
            h for h in unassigned
            if any(nb in rb.zone for nb in neighbors4(h))
        ]
        seeds.sort(key=lambda x: env.euclidean(rb.position, x))
        frontiers[rid] = deque(seeds)

    assignment: dict[int, set] = {rid: set() for rid in ranked_ids}
    progressed = True
    while unassigned and progressed:
        progressed = False
        for rid in ranked_ids:
            q = frontiers[rid]
            while q and q[0] not in unassigned:
                q.popleft()
            if not q:
                continue
            cell = q.popleft()
            if cell not in unassigned:
                continue

            assignment[rid].add(cell)
            unassigned.remove(cell)
            progressed = True

            for nb in neighbors4(cell):
                if nb in unassigned:
                    q.append(nb)

    # 兜底：若仍有离散洞格，按局部距离最小分配（尽量减少穿越）
    if unassigned:
        for cell in list(unassigned):
            best_rid = min(
                ranked_ids,
                key=lambda rid: env.euclidean(robot_by_id[rid].position, cell),
            )
            assignment[best_rid].add(cell)
            unassigned.remove(cell)

    assignment = {rid: cells for rid, cells in assignment.items() if cells}
    for rid, cells in assignment.items():
        rb = robot_by_id[rid]
        rb.zone = rb.zone | cells
        _append_hole_to_path(rb, cells, env)
    source_robot.zone = source_robot.zone - holes
    return assignment


def _append_hole_to_path(robot, holes: set, env):
    """
    将空洞洞所在区域添加到机器人覆盖路径中。
    修复：当路径已耗尽（path_index >= len）时，从当前位置重新开始规划。
    """
    from modules.module2_coverage.boustrophedon import boustrophedon_path
    if not holes:
        return

    extra_path = boustrophedon_path(holes, robot.position, env)
    if not extra_path:
        return

    path_exhausted = robot.path_index >= len(robot.coverage_path)

    if path_exhausted or not robot.coverage_path:
        # 路径已耗尽或无路径：直接以当前位置为起点重新开始
        robot.coverage_path = extra_path
        robot.path_index    = 0
    else:
        # 路径未耗尽：拼接到路径末尾
        bridge = env.bfs_path(robot.coverage_path[-1], extra_path[0])
        if bridge:
            robot.coverage_path.extend(bridge[1:])
        robot.coverage_path.extend(extra_path)

    if robot.state == robot.STATE_IDLE:
        robot.state = robot.STATE_COVERAGE


# ──────────────────────────────────────────
# 全局恢复重构
# ──────────────────────────────────────────

def global_recovery(robots: list, env):
    """
    全局责任区重构：任务结束后重新进行 Voronoi 划分，
    并为每个机器人重新规划未覆盖区域的路径。
    """
    from modules.module1_voronoi.weighted_voronoi import weighted_voronoi_partition
    from modules.module2_coverage.boustrophedon import boustrophedon_path

    # 重新划分责任区
    weighted_voronoi_partition(robots, env)

    # 为每个机器人重建责任区巡逻路径（任务中机器人除外）
    for robot in robots:
        if robot.state in (robot.STATE_EVENT, robot.STATE_WORKING):
            continue
        zone_free = {cell for cell in robot.zone if env.is_free(*cell)}
        if not zone_free:
            robot.coverage_path = []
            robot.path_index = 0
            robot.state = robot.STATE_IDLE
            continue

        uncovered = zone_free - robot.visited
        target = uncovered if uncovered else zone_free
        new_path = boustrophedon_path(target, robot.position, env)
        if new_path:
            robot.coverage_path = new_path
            robot.path_index = 0
            robot.state = robot.STATE_COVERAGE
        else:
            robot.coverage_path = []
            robot.path_index = 0
            robot.state = robot.STATE_IDLE
