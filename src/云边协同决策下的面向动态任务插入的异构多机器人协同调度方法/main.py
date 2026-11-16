"""
多机器人协同系统 — 主仿真入口（重构版）
=========================================
修复内容：
  1. FuncAnimation 驱动，不阻塞 UI
  2. 四象限起始位置，避免两车同区域
  3. 任务完成后机器人继续覆盖（robot.py 内部处理）
  4. 任务计数驱动：出现 MAX_EVENTS 个任务且全部完成后结束
  5. 进度条显示在可视化器中
"""
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation

from config.global_params import (
    MAP_ROWS, MAP_COLS, OBSTACLE_DENSITY, RANDOM_SEED,
    NUM_ROBOTS, RANDOM_START_POS,
    EVENT_INTERVAL, MAX_EVENTS, EVENT_PRIORITY_PROBS, TASK_TYPES,
    MAX_STEPS, ANIMATION_INTERVAL_MS,
)
from core.environment import GridEnvironment
from core.robot        import Robot
from core.task         import Task
from modules.module1_voronoi.weighted_voronoi import weighted_voronoi_partition
from modules.module2_coverage.boustrophedon   import boustrophedon_path
from modules.module3_event.utility_bidding    import bid_for_task
from modules.module4_recovery.hole_patching   import (
    detect_holes, local_hole_bidding, global_recovery
)
from robots.robot_profiles import ROBOT_PROFILES
from visualization.visualizer import Visualizer, set_max_events_hint


def _merge_hole_assignment(holes_map: dict, assignment: dict):
    for rid, cells in assignment.items():
        if not cells:
            continue
        holes_map.setdefault(rid, set()).update(cells)


# ══════════════════════════════════════════
#  地图初始化
# ══════════════════════════════════════════

def init_environment() -> GridEnvironment:
    env = GridEnvironment(
        rows=MAP_ROWS, cols=MAP_COLS,
        obstacle_density=OBSTACLE_DENSITY, seed=RANDOM_SEED,
    )
    print(f"[环境] {env}")
    return env


# ══════════════════════════════════════════
#  四象限起始位置（修复：避免两车在同一区域）
# ══════════════════════════════════════════

def _quadrant_pos(env: GridEnvironment, quad_idx: int, rng, occupied: set):
    """
    将地图分成4个象限，每个机器人分配到不同象限中的随机自由栅格。
    """
    rows, cols = env.rows, env.cols
    mid_r, mid_c = rows // 2, cols // 2
    margin = 2
    quadrants = [
        (margin,        mid_r,          margin,        mid_c),         # 左上
        (margin,        mid_r,          mid_c,         cols - margin), # 右上
        (mid_r,         rows - margin,  margin,        mid_c),         # 左下
        (mid_r,         rows - margin,  mid_c,         cols - margin), # 右下
    ]
    r1, r2, c1, c2 = quadrants[quad_idx % 4]
    candidates = [(r, c) for (r, c) in env.free_cells
                  if r1 <= r < r2 and c1 <= c < c2 and (r, c) not in occupied]
    if not candidates:
        return env.random_free_cell(rng=rng, exclude=occupied)
    idx = int(rng.integers(0, len(candidates)))
    return candidates[idx]


def init_robots(env: GridEnvironment) -> list:
    rng      = np.random.default_rng(RANDOM_SEED)
    occupied = set()
    robots   = []
    profiles = ROBOT_PROFILES[:NUM_ROBOTS]

    for i, profile in enumerate(profiles):
        p = dict(profile)
        if RANDOM_START_POS:
            pos = _quadrant_pos(env, i, rng, occupied)
        else:
            pos = tuple(p.get("start_pos", [0, 0]))
            if not env.is_free(*pos):
                pos = _quadrant_pos(env, i, rng, occupied)

        if pos is None:
            pos = (0, 0)
        p["start_pos"] = list(pos)

        robot = Robot(p, env)
        robot.position = tuple(p["start_pos"])
        robot.visited.add(robot.position)
        occupied.add(robot.position)
        robots.append(robot)
        print(f"[机器人] {robot.name}  位置={robot.position}  "
              f"电量={robot.battery}%  速度={robot.speed}  "
              f"探测半径={robot.detect_radius}")
    return robots


# ══════════════════════════════════════════
#  事件任务生成（随机间隔，更自然）
# ══════════════════════════════════════════

def _schedule_next_event(rng, base_interval: int) -> int:
    """在 [base/2, base*2] 内随机抽取下次事件触发步数。"""
    lo = max(5, base_interval // 2)
    hi = base_interval * 2
    return int(rng.integers(lo, hi + 1))


def try_generate_event(step: int, tasks: list, env: GridEnvironment,
                        rng, sim_state: dict, occupied: set):
    """若当前步到达下次事件触发点，生成一个任务。"""
    if len(tasks) >= MAX_EVENTS:
        return None
    if step < sim_state["next_event_step"]:
        return None

    # 安排下次触发
    sim_state["next_event_step"] = step + _schedule_next_event(rng, EVENT_INTERVAL)

    priority  = int(rng.choice([1, 2, 3], p=EVENT_PRIORITY_PROBS))
    task_type = TASK_TYPES[int(rng.integers(0, len(TASK_TYPES)))]
    existing  = {t.position for t in tasks if not t.done}
    pos = env.random_free_cell(rng=rng, exclude=occupied | existing)
    if pos is None:
        return None

    task = Task(position=pos, priority=priority, appear_step=step,
                task_type=task_type)
    tasks.append(task)
    print(f"  [事件] Step {step}: 生成 {task}")
    return task


# ══════════════════════════════════════════
#  主仿真
# ══════════════════════════════════════════

def run_simulation():
    Task.reset_counter()
    print("=" * 60)
    print("  多机器人协同系统仿真启动")
    print("=" * 60)

    env    = init_environment()
    robots = init_robots(env)
    rng_event = np.random.default_rng(RANDOM_SEED + 7 if RANDOM_SEED else None)

    # 模块1：Voronoi 划分
    print("\n[模块1] 加权 Voronoi 责任区划分 ...")
    weighted_voronoi_partition(robots, env)
    for r in robots:
        print(f"  {r.name}: 责任区 {len(r.zone)} 格")

    # 模块2：Boustrophedon 覆盖路径
    print("\n[模块2] Boustrophedon 覆盖路径规划 ...")
    for r in robots:
        path = boustrophedon_path(r.zone, r.position, env)
        r.coverage_path = path
        r.path_index    = 0
        r.state         = r.STATE_COVERAGE if path else r.STATE_IDLE
        print(f"  {r.name}: 路径 {len(path)} 步")

    # 可视化
    vis = Visualizer(env, robots)
    vis.init()
    set_max_events_hint(MAX_EVENTS)

    # 仿真状态（用 dict 在闭包中共享）
    tasks     = []
    holes_map = {}
    sim_state = {
        "step":            0,
        "next_event_step": _schedule_next_event(rng_event, EVENT_INTERVAL),
        "last_hole_check": 0,
        "completed_task_ids": set(),
        "recovery_pending": False,
        "finished":        False,
        "ani":             None,   # 动画对象引用
    }

    print(f"\n[仿真] FuncAnimation 启动，最大 {MAX_STEPS} 帧 ...\n")

    # ── 动画更新函数 ──────────────────────
    def update_frame(_frame):
        if sim_state["finished"]:
            return

        sim_state["step"] += 1
        step = sim_state["step"]

        # 1. 每个机器人推进（移动步数由 robot.speed 决定）
        for r in robots:
            r.step()

        newly_completed = [
            t for t in tasks
            if t.done and t.task_id not in sim_state["completed_task_ids"]
        ]
        if newly_completed:
            for t in newly_completed:
                sim_state["completed_task_ids"].add(t.task_id)
                t.complete_step = step
            sim_state["recovery_pending"] = True

        # 2. 生成事件任务
        occupied = {r.position for r in robots}
        new_task = try_generate_event(step, tasks, env, rng_event,
                                      sim_state, occupied)
        # 每帧重建空洞分配显示，避免展示过期归属
        holes_map.clear()

        # 3. 模块3：竞价
        if new_task is not None:
            winner, scores = bid_for_task(robots, new_task, env)
            if winner:
                print(f"  [竞价] Task#{new_task.task_id}(P{new_task.priority})"
                      f"[{new_task.task_type}] → {winner.name}"
                      f"  U={scores[winner.robot_id]:.3f}")
                # ★ 修复3：任务分配后立即检测并分配空洞（不等周期）
                # 任务执行期间：响应节点责任区整体托管给其他机器人
                holes = detect_holes(winner, env, include_visited=True)
                if holes:
                    assign = local_hole_bidding(winner, robots, holes, env)
                    _merge_hole_assignment(holes_map, assign)
                    for rid, h in assign.items():
                        nr = next((x for x in robots if x.robot_id == rid), None)
                        if nr:
                            print(f"  [修补] {winner.name} 空洞→{nr.name} "
                                  f"({len(h)}格，立即分配)")
            else:
                print(f"  [竞价] Task#{new_task.task_id} 无可用机器人")

        # 4. 模块4：周期性补充检测空洞（处理 WORKING 阶段的新空洞）
        if step - sim_state["last_hole_check"] >= 50:
            sim_state["last_hole_check"] = step
            for r in robots:
                if r.state in (r.STATE_EVENT, r.STATE_WORKING):
                    holes = detect_holes(r, env, include_visited=True)
                    if holes:
                        assign = local_hole_bidding(r, robots, holes, env)
                        _merge_hole_assignment(holes_map, assign)
                        for rid, h in assign.items():
                            nr = next((x for x in robots if x.robot_id == rid), None)
                            if nr:
                                print(f"  [修补+] {r.name} 空洞→{nr.name} ({len(h)}格)")

        # 任务机器人返回后触发全局责任区重分配
        if sim_state["recovery_pending"]:
            responders = [
                r for r in robots if r.state in (r.STATE_EVENT, r.STATE_WORKING)
            ]
            if not responders:
                global_recovery(robots, env)
                sim_state["recovery_pending"] = False
                print(f"  [恢复] Step {step}: 已完成任务机器人返回，执行全局责任区重分配")


        # 5. 刷新可视化
        vis.update(step, tasks, holes_map or None)

        # 6. 每 100 步打印一次状态
        if step % 100 == 0:
            done = sum(1 for t in tasks if t.done)
            parts = "  ".join(
                f"{r.name}:bat={r.battery:.0f}%,cov={r.coverage_ratio*100:.0f}%"
                for r in robots)
            print(f"  [Step {step}] {parts}  任务:{done}/{len(tasks)}")

        # 7. 结束判断：MAX_EVENTS 全出现并全完成
        total_done = sum(1 for t in tasks if t.done)
        if len(tasks) >= MAX_EVENTS and total_done >= len(tasks):
            sim_state["finished"] = True
            print("\n[模块4] 全局责任区重构 ...")
            global_recovery(robots, env)
            vis.update(step, tasks)
            _print_final_stats(step, robots, tasks)
            vis.save("simulation_result.png")
            print("[完成] 截图已保存为 simulation_result.png")
            return

        # 步数上限保底
        if step >= MAX_STEPS:
            sim_state["finished"] = True
            print("\n[模块4] 全局责任区重构 ...")
            global_recovery(robots, env)
            vis.update(step, tasks)
            _print_final_stats(step, robots, tasks)
            vis.save("simulation_result.png")

    # ── 启动动画 ──────────────────────────
    ani = animation.FuncAnimation(
        vis.fig,
        update_frame,
        interval=ANIMATION_INTERVAL_MS,
        cache_frame_data=False,
    )
    sim_state["ani"] = ani   # 防止被垃圾回收
    plt.show()


# ══════════════════════════════════════════
#  统计输出
# ══════════════════════════════════════════

def _print_final_stats(step: int, robots: list, tasks: list):
    print("\n" + "=" * 60)
    print("  仿真结束统计")
    print("=" * 60)
    for r in robots:
        uncov = len(r.uncovered_in_zone())
        print(f"  {r.name:<12} 电量: {r.battery:5.1f}%  "
              f"覆盖率: {r.coverage_ratio*100:5.1f}%  "
              f"区域: {len(r.zone):4d}格  未覆盖: {uncov:4d}格")
    done = sum(1 for t in tasks if t.done)
    print(f"\n  事件任务: 共{len(tasks)}个 完成{done}个 "
          f"({done/max(len(tasks),1)*100:.1f}%)")
    print(f"  总步数: {step}")
    print("=" * 60)


if __name__ == "__main__":
    run_simulation()
