"""
模块1：加权 Voronoi 责任区划分
===============================
原理：
  综合能力权重  a_i = α·Ê_i + β·R̂_i + γ·V̂_i
  加权分隔代价 C_i(g) = d(g, p_i) / a_i

  对每个自由栅格 g，计算其到所有机器人的加权代价，
  分配给代价最小的机器人，形成各机器人的责任区。
"""
import numpy as np
from config.algorithm_params import VORONOI_ALPHA, VORONOI_BETA, VORONOI_GAMMA


def _normalize(values: np.ndarray) -> np.ndarray:
    """将数组归一化到 [0, 1]，若全为同一值则返回全1数组。"""
    vmin, vmax = values.min(), values.max()
    if vmax - vmin < 1e-9:
        return np.ones_like(values, dtype=float)
    return (values - vmin) / (vmax - vmin)


def compute_capability_weights(robots: list,
                                alpha: float = VORONOI_ALPHA,
                                beta: float  = VORONOI_BETA,
                                gamma: float = VORONOI_GAMMA) -> np.ndarray:
    """
    计算所有机器人的综合能力权重 a_i。

    Parameters
    ----------
    robots : List[Robot]  机器人列表
    alpha, beta, gamma : 电量/探测半径/速度的权重系数

    Returns
    -------
    weights : np.ndarray, shape=(N,)  每台机器人的综合权重（已归一化和加权）
    """
    n = len(robots)
    batteries = np.array([r.battery        for r in robots], dtype=float)
    radii     = np.array([r.detect_radius  for r in robots], dtype=float)
    speeds    = np.array([r.speed          for r in robots], dtype=float)

    E_hat = _normalize(batteries)
    R_hat = _normalize(radii)
    V_hat = _normalize(speeds)

    # 综合权重，确保非零
    a = alpha * E_hat + beta * R_hat + gamma * V_hat
    a = np.clip(a, 1e-6, None)   # 防止除以零
    return a


def weighted_voronoi_partition(robots: list, env) -> dict:
    """
    对地图中所有自由栅格执行加权 Voronoi 划分。

    Parameters
    ----------
    robots : List[Robot]  机器人列表
    env    : GridEnvironment

    Returns
    -------
    zones : dict  {robot_id: set of (row, col)}
    """
    weights = compute_capability_weights(robots)

    # 初始化各机器人区域
    zones = {r.robot_id: set() for r in robots}

    # 对每个自由栅格计算加权代价并分配
    for cell in env.free_cells:
        min_cost = float('inf')
        winner_id = robots[0].robot_id
        for i, r in enumerate(robots):
            d = env.euclidean(cell, r.position)
            cost = d / weights[i]
            if cost < min_cost:
                min_cost = cost
                winner_id = r.robot_id
        zones[winner_id].add(cell)

    # 更新机器人的责任区属性
    for r in robots:
        r.zone = zones[r.robot_id]

    return zones


def get_zone_boundary(zone: set) -> set:
    """
    获取责任区的边界栅格（与非本区域栅格相邻的栅格）。
    """
    boundary = set()
    for (row, col) in zone:
        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
            nb = (row+dr, col+dc)
            if nb not in zone:
                boundary.add((row, col))
                break
    return boundary
