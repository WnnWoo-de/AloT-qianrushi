"""
可视化模块（中文字体兼容 + 责任区归属增强版）
"""
from __future__ import annotations

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba
from matplotlib.gridspec import GridSpec
from matplotlib import font_manager

from config.global_params import TASK_TYPE_NAMES_CN, TASK_WORK_DURATION

PRIORITY_COLORS = {1: "#F1C40F", 2: "#E67E22", 3: "#E74C3C"}
PRIORITY_LABELS = {1: "低优先级", 2: "中优先级", 3: "高优先级"}
FADE_DURATION = 40

_MAX_EVENTS_HINT = 0


def _setup_chinese_fonts() -> None:
    candidates = [
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Source Han Sans CN",
        "PingFang SC",
        "WenQuanYi Zen Hei",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    installed = {f.name for f in font_manager.fontManager.ttflist}
    picked = [x for x in candidates if x in installed]
    if not picked:
        picked = ["DejaVu Sans"]
    matplotlib.rcParams["font.sans-serif"] = picked
    matplotlib.rcParams["axes.unicode_minus"] = False


_setup_chinese_fonts()


def set_max_events_hint(n: int):
    global _MAX_EVENTS_HINT
    _MAX_EVENTS_HINT = n


class Visualizer:
    def __init__(self, env, robots: list):
        self.env = env
        self.robots = robots
        self.fig = None
        self.ax_map = None
        self.ax_info = None
        self._zone_img = None
        self._obs_img = None
        self._task_done_step: dict[int, int] = {}

    def init(self):
        self.fig = plt.figure(figsize=(14, 8), facecolor="#1A1A2E")
        self.fig.canvas.manager.set_window_title("多机器人协同系统仿真")

        gs = GridSpec(
            1,
            2,
            width_ratios=[3, 1],
            figure=self.fig,
            left=0.03,
            right=0.98,
            top=0.94,
            bottom=0.04,
            wspace=0.06,
        )
        self.ax_map = self.fig.add_subplot(gs[0])
        self.ax_info = self.fig.add_subplot(gs[1])

        self.ax_map.set_facecolor("#0D0D1A")
        self.ax_map.set_xlim(-0.5, self.env.cols - 0.5)
        self.ax_map.set_ylim(self.env.rows - 0.5, -0.5)
        self.ax_map.set_aspect("equal")
        self.ax_map.tick_params(colors="#666688")
        for sp in self.ax_map.spines.values():
            sp.set_edgecolor("#2A2A44")

        self.ax_info.set_facecolor("#12122A")
        self.ax_info.axis("off")

        self._build_zone_image()
        self._draw_obstacles()
        return self.fig

    def _build_zone_image(self):
        rows, cols = self.env.rows, self.env.cols
        img = np.zeros((rows, cols, 4), dtype=float)
        for robot in self.robots:
            rgba = to_rgba(robot.color, alpha=0.26)
            for (r, c) in robot.zone:
                img[r, c] = rgba
        if self._zone_img is not None:
            self._zone_img.remove()
        self._zone_img = self.ax_map.imshow(
            img,
            origin="upper",
            extent=(-0.5, cols - 0.5, rows - 0.5, -0.5),
            zorder=1,
            interpolation="nearest",
        )

    def _draw_obstacles(self):
        rows, cols = self.env.rows, self.env.cols
        img = np.zeros((rows, cols, 4), dtype=float)
        obs_c = to_rgba("#2C3E50", alpha=0.90)
        for r in range(rows):
            for c in range(cols):
                if self.env.grid[r, c] == 1:
                    img[r, c] = obs_c
        if self._obs_img is not None:
            self._obs_img.remove()
        self._obs_img = self.ax_map.imshow(
            img,
            origin="upper",
            extent=(-0.5, cols - 0.5, rows - 0.5, -0.5),
            zorder=2,
            interpolation="nearest",
        )

    def update(self, step: int, tasks: list, holes_map: dict = None):
        for artist in list(self.ax_map.lines) + list(self.ax_map.collections):
            artist.remove()
        for txt in list(self.ax_map.texts):
            txt.remove()
        self.ax_info.clear()
        self.ax_info.set_facecolor("#12122A")
        self.ax_info.axis("off")

        for task in tasks:
            if task.done and task.task_id not in self._task_done_step:
                self._task_done_step[task.task_id] = step

        self._build_zone_image()
        self._draw_holes(holes_map)
        self._draw_zone_boundaries()
        self._draw_trajectories()
        self._draw_tasks(tasks, step)
        self._draw_robots()
        self._draw_title(step, tasks)
        self._draw_info_panel(tasks)
        self.fig.canvas.draw_idle()

    def _draw_holes(self, holes_map):
        if not holes_map:
            return
        robot_by_id = {r.robot_id: r for r in self.robots}
        for rid, holes in holes_map.items():
            if not holes:
                continue
            ys = [h[0] for h in holes]
            xs = [h[1] for h in holes]
            color = robot_by_id.get(rid).color if rid in robot_by_id else "#FF6B6B"
            self.ax_map.scatter(
                xs,
                ys,
                s=16,
                c=color,
                alpha=0.55,
                marker="s",
                edgecolors="white",
                linewidths=0.25,
                zorder=3,
            )

    def _draw_zone_boundaries(self):
        for robot in self.robots:
            for (r, c) in robot.zone:
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    rr, cc = r + dr, c + dc
                    if (rr, cc) not in robot.zone:
                        self.ax_map.plot(
                            [c, c + 0.001],
                            [r, r + 0.001],
                            marker="s",
                            markersize=0.75,
                            color=robot.color,
                            alpha=0.28,
                            zorder=2.8,
                        )
                        break

    def _draw_trajectories(self):
        for robot in self.robots:
            if len(robot.trajectory) >= 2:
                traj = np.array(robot.trajectory[-120:])
                self.ax_map.plot(
                    traj[:, 1], traj[:, 0], color=robot.color, lw=0.8, alpha=0.42, zorder=4
                )

            ahead = robot.coverage_path[robot.path_index : robot.path_index + 40]
            if len(ahead) >= 2:
                arr = np.array(ahead)
                self.ax_map.plot(
                    arr[:, 1],
                    arr[:, 0],
                    color=robot.color,
                    lw=0.5,
                    alpha=0.22,
                    linestyle="--",
                    zorder=4,
                )

    def _draw_tasks(self, tasks: list, step: int):
        for task in tasks:
            color = PRIORITY_COLORS.get(task.priority, "#FFFFFF")
            type_cn = TASK_TYPE_NAMES_CN.get(getattr(task, "task_type", "inspection"), "巡检")
            if task.done:
                done_step = self._task_done_step.get(task.task_id, step)
                elapsed = step - done_step
                if elapsed > FADE_DURATION:
                    continue
                alpha = max(0.05, 0.65 * (1 - elapsed / FADE_DURATION))
                self.ax_map.scatter(
                    task.position[1],
                    task.position[0],
                    s=55,
                    c=color,
                    marker="*",
                    alpha=alpha,
                    zorder=5,
                )
            else:
                pulse = 0.75 + 0.25 * abs(np.sin(step * 0.22))
                edge = "white" if task.assigned_to is None else color
                self.ax_map.scatter(
                    task.position[1],
                    task.position[0],
                    s=190,
                    c=color,
                    marker="*",
                    alpha=pulse,
                    zorder=6,
                    edgecolors=edge,
                    linewidths=0.9,
                )
                label = f"P{task.priority} {type_cn}"
                self.ax_map.annotate(
                    label,
                    xy=(task.position[1], task.position[0]),
                    xytext=(task.position[1] + 0.7, task.position[0] - 1.0),
                    color=color,
                    fontsize=6.5,
                    fontweight="bold",
                    zorder=7,
                )

    def _draw_robots(self):
        for robot in self.robots:
            rr, cc = robot.position
            self.ax_map.scatter(cc, rr, s=300, c=robot.color, alpha=0.18, marker="o", zorder=7)
            self.ax_map.scatter(
                cc,
                rr,
                s=105,
                c=robot.color,
                alpha=0.96,
                marker="o",
                zorder=8,
                edgecolors="white",
                linewidths=1.25,
            )
            self.ax_map.annotate(
                robot.name,
                xy=(cc, rr),
                xytext=(cc + 0.8, rr - 0.8),
                color="white",
                fontsize=7,
                fontweight="bold",
                zorder=9,
                bbox=dict(boxstyle="round,pad=0.15", fc=robot.color, alpha=0.65, ec="none"),
            )

    def _draw_title(self, step: int, tasks: list):
        appeared = len(tasks)
        done = sum(1 for t in tasks if t.done)
        self.ax_map.set_title(
            f"多机器人协同仿真    已出现任务 {appeared}/{_MAX_EVENTS_HINT}    "
            f"已完成 {done}/{appeared}    Step: {step}",
            color="white",
            fontsize=10,
            pad=7,
            fontweight="bold",
        )

    def _draw_info_panel(self, tasks: list):
        ax = self.ax_info
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)

        y = 0.97
        ax.text(0.5, y, "状态面板", ha="center", va="top", color="white", fontsize=10, fontweight="bold", transform=ax.transAxes)
        y -= 0.04
        ax.plot([0.02, 0.98], [y, y], color="#333366", lw=0.8, transform=ax.transAxes)
        y -= 0.025

        bar_left, bar_width = 0.08, 0.82

        for robot in self.robots:
            ax.text(0.05, y, f"{robot.name}", color=robot.color, fontsize=8.5, fontweight="bold", va="top", transform=ax.transAxes)
            y -= 0.032

            bat_c = "#E74C3C" if robot.battery < 20 else "#F39C12" if robot.battery < 50 else "#2ECC71"
            ax.barh(y + 0.011, bar_width, height=0.017, left=bar_left, color="#2A2A4A", transform=ax.transAxes)
            ax.barh(
                y + 0.011,
                robot.battery / 100 * bar_width,
                height=0.017,
                left=bar_left,
                color=bat_c,
                alpha=0.85,
                transform=ax.transAxes,
            )
            ax.text(bar_left - 0.02, y + 0.011, "电", fontsize=6, va="center", ha="right", color=bat_c, transform=ax.transAxes)
            ax.text(bar_left + bar_width + 0.01, y + 0.011, f"{robot.battery:.0f}%", color=bat_c, fontsize=6.5, va="center", transform=ax.transAxes)
            y -= 0.028

            ep = robot.event_progress
            if ep is not None:
                if robot.state == robot.STATE_WORKING:
                    bar_c = "#E67E22"
                    label = f"现场工作 {ep*100:.0f}%"
                else:
                    bar_c = "#E74C3C"
                    label = f"前往任务 {ep*100:.0f}%"
                ax.barh(y + 0.011, bar_width, height=0.017, left=bar_left, color="#2A2A4A", transform=ax.transAxes)
                ax.barh(y + 0.011, ep * bar_width, height=0.017, left=bar_left, color=bar_c, alpha=0.85, transform=ax.transAxes)
                ax.text(bar_left - 0.02, y + 0.011, "任", fontsize=6, va="center", ha="right", color=bar_c, transform=ax.transAxes)
                ax.text(bar_left + bar_width + 0.01, y + 0.011, label, color=bar_c, fontsize=6, va="center", transform=ax.transAxes)
            else:
                cov = robot.coverage_ratio
                bar_c = "#3498DB"
                ax.barh(y + 0.011, bar_width, height=0.017, left=bar_left, color="#2A2A4A", transform=ax.transAxes)
                ax.barh(y + 0.011, cov * bar_width, height=0.017, left=bar_left, color=bar_c, alpha=0.75, transform=ax.transAxes)
                ax.text(bar_left - 0.02, y + 0.011, "巡", fontsize=6, va="center", ha="right", color=bar_c, transform=ax.transAxes)
                ax.text(bar_left + bar_width + 0.01, y + 0.011, f"{cov*100:.0f}%", color=bar_c, fontsize=6.5, va="center", transform=ax.transAxes)
            y -= 0.028

            state_map = {
                "coverage": "巡检覆盖中",
                "event": "前往任务点",
                "working": "现场执行中",
                "idle": "空闲",
            }
            s = state_map.get(robot.state, robot.state)
            ax.text(
                bar_left,
                y,
                f"{s}  负载:{robot.load}/{robot.max_load}  区域:{len(robot.zone)}格",
                color="#9999BB",
                fontsize=6.5,
                va="top",
                transform=ax.transAxes,
            )
            y -= 0.038

        ax.plot([0.02, 0.98], [y, y], color="#333366", lw=0.6, transform=ax.transAxes)
        y -= 0.022

        total = len(tasks)
        done = sum(1 for t in tasks if t.done)
        active = sum(1 for t in tasks if not t.done and t.assigned_to is not None)
        waiting = total - done - active

        ax.text(0.5, y, "任务统计", ha="center", color="white", fontsize=8, fontweight="bold", va="top", transform=ax.transAxes)
        y -= 0.03
        for label, val, col in [
            ("已出现", total, "#AAAACC"),
            ("已完成", done, "#2ECC71"),
            ("执行中", active, "#E74C3C"),
            ("等待中", waiting, "#F39C12"),
        ]:
            ax.text(0.10, y, f"{label}: {val}", color=col, fontsize=7.5, va="top", transform=ax.transAxes)
            y -= 0.028

    def save(self, path: str):
        self.fig.savefig(path, dpi=150, facecolor=self.fig.get_facecolor())

    def close(self):
        plt.show()
