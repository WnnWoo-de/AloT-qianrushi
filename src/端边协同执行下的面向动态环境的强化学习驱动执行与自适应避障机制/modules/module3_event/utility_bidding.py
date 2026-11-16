"""
模块3：基于任务优先级调控的多维复合效用竞价机制（完整版）
=========================================================
修复：
  - feasibility_filter 增加能力类型匹配（capabilities ∩ task_type）
  - _score_capability 根据能力集合精确打分
"""
import numpy as np
from config.algorithm_params import (
    EVENT_WEIGHTS_PRIORITY_1,
    EVENT_WEIGHTS_PRIORITY_2,
    EVENT_WEIGHTS_PRIORITY_3,
    EVENT_MIN_BATTERY,
    EVENT_MAX_LOAD_RATIO,
)

_PRIORITY_WEIGHTS = {
    1: EVENT_WEIGHTS_PRIORITY_1,
    2: EVENT_WEIGHTS_PRIORITY_2,
    3: EVENT_WEIGHTS_PRIORITY_3,
}


def _get_weights(priority: int) -> dict:
    return _PRIORITY_WEIGHTS.get(priority, EVENT_WEIGHTS_PRIORITY_2)


def _score_distance(dist: float, max_dist: float) -> float:
    if max_dist < 1e-9:
        return 1.0
    return 1.0 - dist / max_dist


def _score_capability(robot, task) -> float:
    """
    能力匹配得分 f_cap：
      - 具备所需能力类型：1.0
      - 不具备（但通过了可行性筛选的降级情况）：0.4
    """
    robot_caps = getattr(robot, "capabilities", [])
    task_type  = getattr(task, "task_type", "inspection")
    if task_type in robot_caps:
        return 1.0
    return 0.4


def _score_battery(battery: float) -> float:
    return battery / 100.0


def _score_load(load_ratio: float) -> float:
    return 1.0 - load_ratio


def feasibility_filter(robots: list, task) -> list:
    """
    可行性筛选：
      1. 电量 >= EVENT_MIN_BATTERY
      2. 负载比率 <= EVENT_MAX_LOAD_RATIO
      3. 能力类型匹配（capabilities ∩ {task_type} ≠ ∅）
         若无任何机器人满足能力约束，则放宽（所有机器人都可参与）
    """
    task_type = getattr(task, "task_type", "inspection")

    capable    = []
    non_capable = []
    for r in robots:
        if r.battery < EVENT_MIN_BATTERY:
            continue
        if r.load_ratio > EVENT_MAX_LOAD_RATIO:
            continue
        # One robot handles one event at a time; avoid overriding active task.
        if getattr(r, "active_event", None) is not None:
            continue
        if getattr(r, "state", None) not in (
            getattr(r, "STATE_COVERAGE", "coverage"),
            getattr(r, "STATE_IDLE", "idle"),
        ):
            continue
        if not getattr(r, "is_available", True):
            continue
        robot_caps = getattr(r, "capabilities", ["inspection"])
        if task_type in robot_caps:
            capable.append(r)
        else:
            non_capable.append(r)

    # 有能力匹配的机器人优先；若无则降级使用所有通过基本筛选的
    return capable if capable else non_capable


def compute_utility(robot, task, max_dist: float) -> float:
    """
    计算单个机器人对任务的综合效用 U_i(T)。
    U_i(T) = w1·f_dist + w2·f_cap + w3·f_battery + w4·f_load
    """
    from core.environment import GridEnvironment
    w    = _get_weights(task.priority)
    dist = GridEnvironment.euclidean(robot.position, task.position)

    f_dist    = _score_distance(dist, max_dist)
    f_cap     = _score_capability(robot, task)
    f_battery = _score_battery(robot.battery)
    f_load    = _score_load(robot.load_ratio)

    return (w["w1_dist"]    * f_dist
          + w["w2_cap"]     * f_cap
          + w["w3_battery"] * f_battery
          + w["w4_load"]    * f_load)


def bid_for_task(robots: list, task, env) -> tuple:
    """
    竞价并分配任务。
    Returns: (winner: Robot|None, scores: dict{robot_id: score})
    """
    candidates = feasibility_filter(robots, task)
    if not candidates:
        return None, {}

    from core.environment import GridEnvironment
    distances = [GridEnvironment.euclidean(r.position, task.position)
                 for r in candidates]
    max_dist  = max(distances) if distances else 1.0

    scores = {r.robot_id: compute_utility(r, task, max_dist) for r in candidates}
    ranked = sorted(candidates, key=lambda r: scores[r.robot_id], reverse=True)

    winner = None
    path = []
    for cand in ranked:
        cand_path = env.bfs_path(cand.position, task.position)
        if cand_path:
            winner = cand
            path = cand_path
            break

    if winner is None:
        return None, scores

    assigned = winner.assign_event(task, path)
    if not assigned:
        return None, scores
    task.assigned_to = winner.robot_id
    return winner, scores
