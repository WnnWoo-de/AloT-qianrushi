"""
任务/事件类
"""
from __future__ import annotations


class Task:
    """
    事件任务。

    属性：
        task_id      : 唯一 ID
        position     : 任务位置 (row, col)
        priority     : 优先级（1=低, 2=中, 3=高）
        task_type    : 任务类型字符串（"inspection"/"emergency"/"service"/"delivery"）
        appear_step  : 出现时的仿真步数
        assigned_to  : 负责执行的机器人 ID（None=未分配）
        done         : 是否已完成
    """

    _id_counter = 0

    def __init__(self, position: tuple, priority: int, appear_step: int,
                 task_type: str = "inspection"):
        Task._id_counter += 1
        self.task_id     = Task._id_counter
        self.position    = position
        self.priority    = priority           # 1=低, 2=中, 3=高
        self.task_type   = task_type          # 任务类型（用于能力匹配）
        self.appear_step = appear_step
        self.assigned_to: int | None  = None
        self.done: bool               = False
        self.complete_step: int | None = None

    @classmethod
    def reset_counter(cls):
        cls._id_counter = 0

    def __repr__(self):
        status = "done" if self.done else (
            f"→ Robot{self.assigned_to}" if self.assigned_to is not None else "pending"
        )
        return (f"Task#{self.task_id}"
                f"(pos={self.position}, P{self.priority}, "
                f"{self.task_type}, {status})")
