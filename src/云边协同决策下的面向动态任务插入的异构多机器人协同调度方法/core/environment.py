"""
栅格地图环境
包含地图生成、障碍物布置、距离计算等基础功能。
"""
from __future__ import annotations

import numpy as np
from config.global_params import MAP_ROWS, MAP_COLS, OBSTACLE_DENSITY, RANDOM_SEED


class GridEnvironment:
    """
    栅格地图环境。

    属性：
        rows, cols : 地图尺寸
        grid       : 二维数组，0=自由栅格，1=障碍物
        free_cells : 所有自由栅格坐标列表 [(r,c), ...]
    """

    FREE = 0
    OBSTACLE = 1

    def __init__(self, rows: int = MAP_ROWS, cols: int = MAP_COLS,
                 obstacle_density: float = OBSTACLE_DENSITY,
                 seed: int | None = RANDOM_SEED):
        self.rows = rows
        self.cols = cols
        self.obstacle_density = obstacle_density

        rng = np.random.default_rng(seed)

        # 生成障碍物地图
        self.grid = np.zeros((rows, cols), dtype=np.int8)
        mask = rng.random((rows, cols)) < obstacle_density
        # 地图边界不设障碍
        mask[0, :] = False
        mask[-1, :] = False
        mask[:, 0] = False
        mask[:, -1] = False
        self.grid[mask] = self.OBSTACLE

        self._update_free_cells()

    # ──────────────────────────────────────
    # 基本查询
    # ──────────────────────────────────────
    def _update_free_cells(self):
        coords = np.argwhere(self.grid == self.FREE)
        self.free_cells = [tuple(c) for c in coords]

    def is_free(self, r: int, c: int) -> bool:
        if 0 <= r < self.rows and 0 <= c < self.cols:
            return self.grid[r, c] == self.FREE
        return False

    def is_valid(self, r: int, c: int) -> bool:
        return 0 <= r < self.rows and 0 <= c < self.cols

    # ──────────────────────────────────────
    # 距离计算（欧氏距离）
    # ──────────────────────────────────────
    @staticmethod
    def euclidean(p1, p2) -> float:
        return float(np.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2))

    @staticmethod
    def manhattan(p1, p2) -> int:
        return abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])

    # ──────────────────────────────────────
    # 邻域查询（4联通）
    # ──────────────────────────────────────
    def neighbors_4(self, r: int, c: int):
        """返回四联通自由邻居列表。"""
        result = []
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if self.is_free(nr, nc):
                result.append((nr, nc))
        return result

    def neighbors_8(self, r: int, c: int):
        """返回八联通自由邻居列表。"""
        result = []
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if self.is_free(nr, nc):
                    result.append((nr, nc))
        return result

    # ──────────────────────────────────────
    # BFS 最短路径
    # ──────────────────────────────────────
    def bfs_path(self, start, goal):
        """
        在栅格地图中用 BFS 求最短路径。
        返回路径列表（包含 start 和 goal），若无路径则返回 []。
        """
        if start == goal:
            return [start]
        from collections import deque
        queue = deque([[start]])
        visited = {start}
        while queue:
            path = queue.popleft()
            cur = path[-1]
            for nb in self.neighbors_4(*cur):
                if nb == goal:
                    return path + [nb]
                if nb not in visited:
                    visited.add(nb)
                    queue.append(path + [nb])
        return []

    # ──────────────────────────────────────
    # 随机自由栅格采样
    # ──────────────────────────────────────
    def random_free_cell(self, rng=None, exclude=None):
        """随机返回一个自由栅格，排除指定坐标集合。"""
        exclude = set(exclude) if exclude else set()
        candidates = [c for c in self.free_cells if c not in exclude]
        if not candidates:
            return None
        if rng is None:
            rng = np.random.default_rng()
        idx = rng.integers(0, len(candidates))
        return candidates[idx]

    def __repr__(self):
        return (f"GridEnvironment({self.rows}×{self.cols}, "
                f"obstacles={self.grid.sum()}, "
                f"free={len(self.free_cells)})")
