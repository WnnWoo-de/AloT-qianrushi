"""
机器人实体类（完整版）
状态机：COVERING → EVENT → WORKING → COVERING
关键修复：
  - STATE_WORKING：到达任务点后在现场工作一段时间才算完成
  - _replan_coverage：路径耗尽自动寻找未覆盖区域
  - event_progress：同时反映前往阶段和工作阶段进度
"""
from __future__ import annotations

from config.global_params import (
    BATTERY_COST_PER_STEP,
    BATTERY_COST_EVENT_BONUS,
    TASK_WORK_DURATION,
    BATTERY_RECOVERY_RATE_IDLE,
)


class Robot:
    STATE_COVERAGE = "coverage"  # 常态覆盖巡检
    STATE_EVENT    = "event"     # 前往事件任务点
    STATE_WORKING  = "working"   # 到达任务点，正在现场工作
    STATE_IDLE     = "idle"      # 空闲

    def __init__(self, profile: dict, env):
        self.robot_id      = profile["id"]
        self.name          = profile["name"]
        self.color         = profile.get("color", "#888888")

        # 性能参数（speed 仅用于 Voronoi 权重，不决定视觉移动速度）
        self.battery       = float(profile["battery"])
        self.speed         = int(profile["speed"])
        self.detect_radius = float(profile["detect_radius"])
        self.max_load      = int(profile["max_load"])

        # 能力集合（用于事件任务可行性筛选）
        self.capabilities: list = profile.get("capabilities", ["inspection"])

        self.position = tuple(profile.get("start_pos", [0, 0]))
        self.env = env

        # 区域 & 路径
        self.zone: set           = set()
        self.coverage_path: list = []
        self.path_index: int     = 0
        self.current_tasks: list = []
        self.visited: set        = set()
        self.state: str          = self.STATE_IDLE

        # 事件任务
        self.event_path: list       = []
        self.event_path_index: int  = 0
        self.event_initial_len: int = 0
        self.active_event           = None

        # 现场工作倒计时
        self.work_remaining: int = 0

        # 历史轨迹（可视化用）
        self.trajectory: list = [self.position]

    # ──────────────────────────────────────
    # 能力权重（供 Voronoi 计算）
    # ──────────────────────────────────────
    def capability_raw(self) -> dict:
        return {
            "battery":       self.battery,
            "detect_radius": self.detect_radius,
            "speed":         self.speed,
        }

    # ──────────────────────────────────────
    # 主步进（每次移动正好 1 格）
    # ──────────────────────────────────────
    def step(self):
        self._cleanup_task_queue()
        # 空闲时自动充电
        if self.state == self.STATE_IDLE:
            # Never charge while actively owning an event task.
            if self.active_event is None and not self.current_tasks:
                self.battery = min(100.0, self.battery + BATTERY_RECOVERY_RATE_IDLE)
                if self.battery > BATTERY_COST_PER_STEP and self.zone:
                    self._replan_coverage()
            return
        if self.battery <= 0:
            self.state = self.STATE_IDLE
            return
        if self.state == self.STATE_EVENT:
            move_budget = max(1, int(round(self.speed)))
            for _ in range(move_budget):
                if self.state != self.STATE_EVENT or self.battery <= 0:
                    break
                self._step_event()
        elif self.state == self.STATE_WORKING:
            self._step_working()
        elif self.state == self.STATE_COVERAGE:
            move_budget = max(1, int(round(self.speed)))
            for _ in range(move_budget):
                if self.state != self.STATE_COVERAGE or self.battery <= 0:
                    break
                self._step_coverage()

    # ──────────────────────────────────────
    # 前往事件点
    # ──────────────────────────────────────
    def _step_event(self):
        """沿事件路径前进 1 格。"""
        if not self.event_path or self.event_path_index >= len(self.event_path):
            self._on_event_arrived()
            return

        self.position = self.event_path[self.event_path_index]
        self.event_path_index += 1
        self.visited.add(self.position)
        self._consume_battery(extra=BATTERY_COST_EVENT_BONUS)
        self.trajectory.append(self.position)

        if self.event_path_index >= len(self.event_path):
            self._on_event_arrived()

    def _on_event_arrived(self):
        """到达任务点：进入现场工作状态（不立即完成）。"""
        self.work_remaining = TASK_WORK_DURATION
        self.state = self.STATE_WORKING

    # ──────────────────────────────────────
    # 现场工作（不移动，倒计时）
    # ──────────────────────────────────────
    def _step_working(self):
        """在任务点原地工作，耗尽计时后标记完成并返回覆盖。"""
        self._consume_battery(extra=BATTERY_COST_EVENT_BONUS)
        self.work_remaining -= 1
        if self.work_remaining <= 0:
            self._on_work_complete()

    def _on_work_complete(self):
        """工作完成：标记任务 done，返回覆盖状态。"""
        if self.active_event is not None:
            self.active_event.done = True
            self.current_tasks = [t for t in self.current_tasks
                                  if t.task_id != self.active_event.task_id]
            self.active_event = None
        self._replan_coverage()

    # ──────────────────────────────────────
    # 覆盖路径
    # ──────────────────────────────────────
    def _step_coverage(self):
        """沿覆盖路径前进 1 格。"""
        if self.path_index >= len(self.coverage_path):
            self._replan_coverage()
            return

        self.position = self.coverage_path[self.path_index]
        self.path_index += 1
        self.visited.add(self.position)
        self._consume_battery()
        self.trajectory.append(self.position)

        if self.path_index >= len(self.coverage_path):
            self._replan_coverage()

    def _replan_coverage(self):
        """?????????????????????????"""
        if self.battery <= 0:
            self.state = self.STATE_IDLE
            return

        zone_free = {c for c in self.zone if self.env.is_free(*c)}
        if not zone_free:
            self.state = self.STATE_IDLE
            return

        uncovered = {c for c in zone_free if c not in self.visited}
        target_cells = uncovered if uncovered else zone_free

        from modules.module2_coverage.boustrophedon import boustrophedon_path
        new_path = boustrophedon_path(target_cells, self.position, self.env)
        if new_path:
            self.coverage_path = new_path
            self.path_index = 0
            self.state = self.STATE_COVERAGE
        else:
            self.state = self.STATE_IDLE

    def _consume_battery(self, extra: float = 0.0):
        self.battery = max(0.0, self.battery - BATTERY_COST_PER_STEP - extra)

    # ──────────────────────────────────────
    # 事件分配
    # ──────────────────────────────────────
    def assign_event(self, task, path: list):
        if self.active_event is not None:
            return False
        if not path:
            return False
        self.active_event      = task
        self.event_path        = path
        self.event_path_index  = 0
        self.event_initial_len = len(path)
        if all(t.task_id != task.task_id for t in self.current_tasks):
            self.current_tasks.append(task)
        self.state = self.STATE_EVENT
        return True

    # ──────────────────────────────────────
    # 属性
    # ──────────────────────────────────────
    @property
    def load(self) -> int:
        return len(self.current_tasks)

    @property
    def load_ratio(self) -> float:
        return self.load / self.max_load if self.max_load > 0 else 1.0

    @property
    def is_available(self) -> bool:
        return (
            self.battery > 0
            and self.load < self.max_load
            and self.active_event is None
            and self.state in (self.STATE_COVERAGE, self.STATE_IDLE)
        )

    @property
    def event_progress(self) -> float | None:
        """
        事件任务综合进度（0~1），None 表示未在执行事件。
          前往阶段：0.0 ~ 0.7
          工作阶段：0.7 ~ 1.0
        """
        if self.state == self.STATE_EVENT:
            travel = self.event_path_index / max(self.event_initial_len, 1)
            return min(0.7, 0.7 * travel)
        if self.state == self.STATE_WORKING:
            work_done = TASK_WORK_DURATION - self.work_remaining
            return 0.7 + 0.3 * work_done / max(TASK_WORK_DURATION, 1)
        return None

    @property
    def coverage_ratio(self) -> float:
        if not self.zone:
            return 1.0
        return len(self.visited & self.zone) / len(self.zone)

    def uncovered_in_zone(self) -> set:
        return {c for c in self.zone if c not in self.visited}

    def __repr__(self):
        return (f"Robot({self.name}, pos={self.position}, "
                f"bat={self.battery:.1f}%, state={self.state})")

    def _cleanup_task_queue(self):
        self.current_tasks = [
            t for t in self.current_tasks
            if (not getattr(t, "done", False))
        ]
