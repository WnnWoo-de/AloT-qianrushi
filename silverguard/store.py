"""单机多进程 SQLite 协同状态；事务内去重、派单与审计一起提交。"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class Conflict(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class Store:
    def __init__(self, path):
        self.path = str(Path(path).resolve())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            for table in ("events", "tasks", "robots"):
                db.execute(f"CREATE TABLE IF NOT EXISTS {table} (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS journal (seq INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, kind TEXT NOT NULL, body TEXT NOT NULL)")

    @contextmanager
    def connection(self, write=False):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            db.execute("PRAGMA synchronous=FULL")
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _get(db, table, key):
        row = db.execute(f"SELECT body FROM {table} WHERE id=?", (key,)).fetchone()
        if not row:
            raise KeyError(key)
        return json.loads(row[0])

    @staticmethod
    def _list(db, table):
        return [json.loads(r[0]) for r in db.execute(f"SELECT body FROM {table} ORDER BY rowid DESC")]

    @staticmethod
    def _save(db, table, key, item):
        db.execute(f"INSERT INTO {table} VALUES (?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body", (key, json.dumps(item, ensure_ascii=False)))

    @staticmethod
    def _log(db, kind, item):
        db.execute("INSERT INTO journal(at,kind,body) VALUES (?,?,?)", (now(), kind, json.dumps(item, ensure_ascii=False)))

    def list(self, table):
        assert table in ("events", "tasks", "robots")
        with self.connection() as db:
            rows = self._list(db, table)
        if table == "robots":
            for row in rows:
                row["online"] = bool(row.get("online")) and (datetime.now(timezone.utc) - datetime.fromisoformat(row["last_update"])).total_seconds() <= 30
        return rows

    def get(self, table, key):
        assert table in ("events", "tasks", "robots")
        if table == "robots":
            for row in self.list("robots"):
                if row["robot_id"] == key:
                    return row
            raise KeyError(key)
        with self.connection() as db:
            return self._get(db, table, key)

    def changes(self, after=0):
        with self.connection() as db:
            return [{"seq": r[0], "at": r[1], "kind": r[2], "data": json.loads(r[3])} for r in db.execute("SELECT * FROM journal WHERE seq>? ORDER BY seq", (after,))]

    def telemetry(self, robot_id, payload):
        with self.connection(True) as db:
            item = {**payload, "robot_id": robot_id, "last_update": now()}
            self._save(db, "robots", robot_id, item)
            self._log(db, "robot_update", item)
            return item

    def _dispatch(self, db, task, event):
        if task["status"] != "待派单":
            return
        busy = {t["robot_id"] for t in self._list(db, "tasks") if t["status"] not in ("已完成", "失败", "待派单")}
        candidates = [r for r in self._list(db, "robots") if r.get("online") and r.get("battery", 0) >= 20 and r["robot_id"] not in busy and (datetime.now(timezone.utc) - datetime.fromisoformat(r["last_update"])).total_seconds() <= 30]
        if not candidates:
            return
        # 联调基线：按 robot_id 稳定选择，不冒充论文中的效用竞价调度。
        robot = min(candidates, key=lambda r: r["robot_id"])
        task.update(robot_id=robot["robot_id"], status="已派单", dispatched_at=now(), dispatch_reason="在线、电量>=20%、心跳<=30秒且未占用；按ID稳定选择")
        event.update(status="已派单", robot_id=robot["robot_id"])

    def create_event(self, payload):
        with self.connection(True) as db:
            try:
                old = self._get(db, "events", payload["event_id"])
            except KeyError:
                old = None
            if old:
                if any(old[k] != payload[k] for k in ("run_id", "type", "position")):
                    raise Conflict("同一 event_id 的 run_id、类型或位置不一致")
                return old
            stamp = now()
            event = {**payload, "status": "已上报", "created_at": stamp, "updated_at": stamp, "task_id": "task-" + uuid4().hex}
            task = {"task_id": event["task_id"], "event_id": event["event_id"], "run_id": event["run_id"], "robot_id": None, "status": "待派单", "created_at": stamp, "updated_at": stamp, "title": event["type"], "done": False}
            self._dispatch(db, task, event)
            self._save(db, "events", event["event_id"], event)
            self._save(db, "tasks", task["task_id"], task)
            self._log(db, "event_update", event)
            self._log(db, "task_update", task)
            return event

    def dispatch(self, task_id):
        with self.connection(True) as db:
            task = self._get(db, "tasks", task_id)
            event = self._get(db, "events", task["event_id"])
            before = task["status"]
            self._dispatch(db, task, event)
            if before != task["status"]:
                self._persist_pair(db, task, event)
            return task

    def _persist_pair(self, db, task, event):
        task["updated_at"] = event["updated_at"] = now()
        self._save(db, "tasks", task["task_id"], task)
        self._save(db, "events", event["event_id"], event)
        self._log(db, "task_update", task)
        self._log(db, "event_update", event)

    def transition(self, task_id, status, robot_id, reason=""):
        allowed = {"已派单": ("已接单", "失败"), "已接单": ("已到场", "失败"), "已到场": ("失败",)}
        with self.connection(True) as db:
            task = self._get(db, "tasks", task_id)
            event = self._get(db, "events", task["event_id"])
            if task["robot_id"] != robot_id:
                raise Conflict("回执机器人与派单不符")
            if task["status"] == status:
                return task
            if status not in allowed.get(task["status"], ()):
                raise Conflict("不允许跳过接单、到场或终态回退")
            if status == "失败" and not reason.strip():
                raise Conflict("失败必须记录原因")
            task.update(status=status, failure_reason=reason)
            task[{"已接单": "accepted_at", "已到场": "arrived_at", "失败": "failed_at"}[status]] = now()
            event["status"] = status
            self._persist_pair(db, task, event)
            return task

    def confirm(self, event_id, actor):
        with self.connection(True) as db:
            event = self._get(db, "events", event_id)
            task = self._get(db, "tasks", event["task_id"])
            if task["status"] == "已完成":
                return event
            if task["status"] != "已到场":
                raise Conflict("须车端确认到场后才能完成护工处置")
            task.update(status="已完成", done=True, confirmed_at=now(), handled_by=actor)
            event.update(status="已处理", confirmed_at=task["confirmed_at"], handled_by=actor)
            self._persist_pair(db, task, event)
            return event

    def start_care(self, event_id, actor):
        with self.connection(True) as db:
            event = self._get(db, "events", event_id)
            task = self._get(db, "tasks", event["task_id"])
            if task["status"] in ("已完成", "失败"):
                raise Conflict("终态事件不可重新开始处置")
            if event.get("care_started_at"):
                return event
            event.update(handled_by=actor, care_started_at=now(), updated_at=now())
            self._save(db, "events", event_id, event)
            self._log(db, "event_update", event)
            return event

    def mark_popup(self, event_id, shown):
        with self.connection(True) as db:
            event = self._get(db, "events", event_id)
            event.update(popup_shown=shown, popupShown=shown, updated_at=now())
            self._save(db, "events", event_id, event)
            self._log(db, "event_update", event)
            return event
