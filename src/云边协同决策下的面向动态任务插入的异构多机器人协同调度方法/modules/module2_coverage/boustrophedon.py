"""
模块2：Boustrophedon 覆盖路径规划（高效版）
=============================================
修复要点：
  1. 引入连通分量分解 → 绝不跳过任何区域（修复漏扫）
  2. 行内连续格子直接顺序追加（高效）
  3. 行间 BFS 连接；失败时跳至行首强制包含（不静默丢弃）
  4. 分量间 BFS 跨越连接
"""
from collections import deque


# ──────────────────────────────────────
# 工具：连通分量分解（四联通）
# ──────────────────────────────────────

def _find_connected_components(cells: set, env) -> list:
    """
    对给定栅格集合做四联通连通分量分解。
    返回各分量集合列表（按大小降序排列）。
    """
    remaining = set(cells)
    components = []
    while remaining:
        start = next(iter(remaining))
        comp  = set()
        q     = deque([start])
        while q:
            cell = q.popleft()
            if cell in remaining:
                remaining.remove(cell)
                comp.add(cell)
                for nb in env.neighbors_4(*cell):
                    if nb in remaining:
                        q.append(nb)
        components.append(comp)
    components.sort(key=len, reverse=True)   # 大分量优先
    return components


# ──────────────────────────────────────
# 工具：对单一连通分量做行扫描
# ──────────────────────────────────────

def _plan_component(component: set, start: tuple, env) -> list:
    """
    对连通分量执行 Boustrophedon 行扫描，返回路径列表。
    - 行内格子顺序追加（无需BFS）
    - 行间用 BFS 桥接；失败时直接把目标格加入（不静默跳过）
    """
    # 按行分组
    rows_dict: dict = {}
    for (r, c) in component:
        rows_dict.setdefault(r, []).append(c)
    for r in rows_dict:
        rows_dict[r].sort()

    sorted_rows = sorted(rows_dict.keys())

    # 奇偶行交替方向
    scan_lines = []
    for i, row in enumerate(sorted_rows):
        cols = rows_dict[row]
        scan_lines.append([(row, c) for c in
                           (cols if i % 2 == 0 else reversed(cols))])

    path    = []
    current = start

    for line in scan_lines:
        if not line:
            continue

        # ── 行间桥接 ──────────────────────────
        bridge = env.bfs_path(current, line[0])
        if bridge:
            if path:
                path.extend(bridge[1:])    # 去掉重复头部
            else:
                path.extend(bridge)
        else:
            # BFS 失败：强制加入行首（不跳过）
            path.append(line[0])

        # ── 行内格子直接追加（行内通常连续）──
        last = path[-1]
        for cell in line:
            if cell != last:
                # 相邻格直接加；非相邻时 BFS 补桥（障碍绕行）
                if abs(cell[0] - last[0]) + abs(cell[1] - last[1]) == 1:
                    path.append(cell)
                else:
                    seg = env.bfs_path(last, cell)
                    if seg:
                        path.extend(seg[1:])
                    else:
                        path.append(cell)
                last = cell

        current = path[-1] if path else current

    return path


# ──────────────────────────────────────
# 公共接口
# ──────────────────────────────────────

def boustrophedon_path(zone: set, start: tuple, env) -> list:
    """
    生成 Boustrophedon 覆盖路径（支持多连通分量）。

    Parameters
    ----------
    zone  : set of (row, col)  需要覆盖的栅格集合
    start : (row, col)         机器人当前位置
    env   : GridEnvironment

    Returns
    -------
    path : list of (row, col)
    """
    if not zone:
        return []

    components  = _find_connected_components(zone, env)
    full_path   = []
    current_pos = start

    for comp in components:
        seg = _plan_component(comp, current_pos, env)
        if not seg:
            continue

        if full_path:
            # 分量间：BFS 跨越连接（允许通过非 zone 格子过渡）
            bridge = env.bfs_path(current_pos, seg[0])
            if bridge:
                full_path.extend(bridge[1:])
            else:
                full_path.append(seg[0])
            full_path.extend(seg[1:])       # 跳过重复的 seg[0]
        else:
            full_path.extend(seg)

        current_pos = full_path[-1] if full_path else current_pos

    return full_path


# ──────────────────────────────────────
# 辅助：计算机器人责任区未覆盖格子
# ──────────────────────────────────────

def compute_uncovered_holes(robot, env) -> set:
    """计算机器人责任区中尚未被覆盖的自由栅格。"""
    return {cell for cell in robot.zone
            if env.is_free(*cell) and cell not in robot.visited}
