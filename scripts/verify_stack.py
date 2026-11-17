"""隔离复制三端并启动真实 HTTP 进程，验证去重、跨端闭环和重启恢复。"""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time

import httpx
from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[1]
NAMES = ["云端小车监控中心", "云端监控中心", "护工移动端"]


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    with tempfile.TemporaryDirectory(prefix="silverguard-check-") as temporary:
        root = Path(temporary)
        shutil.copytree(ROOT / "silverguard", root / "silverguard", ignore=shutil.ignore_patterns("__pycache__"))
        for name in NAMES:
            shutil.copytree(ROOT / "src" / name, root / "src" / name, ignore=shutil.ignore_patterns("runtime", "__pycache__"))
        env = {**os.environ, "SILVERGUARD_DB": str(root / "state.sqlite3"), "PYTHONIOENCODING": "utf-8"}
        ports = [port() for _ in NAMES]
        processes = []
        log = (root / "services.log").open("w", encoding="utf-8")

        def launch(index):
            process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(ports[index])], cwd=root / "src" / NAMES[index] / "backend", env=env, stdout=log, stderr=log)
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("服务启动失败：" + NAMES[index])
                try:
                    if httpx.get(f"http://127.0.0.1:{ports[index]}/api/v1/health", trust_env=False, timeout=2).status_code == 200:
                        return process
                except httpx.HTTPError:
                    pass
                time.sleep(0.2)
            process.terminate()
            process.wait()
            raise RuntimeError("健康检查超时")

        def request(index, method, path, body=None):
            response = httpx.request(method, f"http://127.0.0.1:{ports[index]}/api/v1" + path, json=body, timeout=10, trust_env=False)
            response.raise_for_status()
            return response.json()["data"]

        try:
            for index in range(3):
                processes.append(launch(index))
            request(0, "POST", "/robots/A/telemetry", {"battery": 90})
            request(0, "POST", "/robots/B/telemetry", {"battery": 90})
            payload = {"run_id": "isolated-software-test", "event_id": "controlled-001", "type": "受控异常", "position": "模拟走廊"}
            # 订阅云端 WS，再由小车端写入，验证跨进程增量转发而非仅本端广播。
            with connect(f"ws://127.0.0.1:{ports[1]}/ws/monitor", proxy=None) as websocket:
                websocket.recv(timeout=5)  # 首帧系统状态
                event = request(0, "POST", "/events", payload)
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    message = json.loads(websocket.recv(timeout=5))
                    if message.get("type") == "event_update" and message["data"].get("event_id") == payload["event_id"]:
                        break
                else:
                    raise AssertionError("云端未收到小车端事件广播")
            assert request(0, "POST", "/events", payload)["task_id"] == event["task_id"]
            assert len(request(1, "GET", "/events")) == 1
            assert len(request(2, "GET", "/tasks")) == 1
            # 护工个人待办与机器人任务分流，不能把护理待办写成机器人派单。
            todo = request(2, "POST", "/care/todos", {"content": "交班记录"})
            assert request(2, "GET", "/care/todos")[0]["task_id"] == todo["task_id"]
            assert len(request(2, "GET", "/tasks")) == 1
            request(2, "PATCH", "/care/todos/" + todo["task_id"], {"done": True, "status": "已完成"})
            request(2, "DELETE", "/care/todos/" + todo["task_id"])
            assert request(2, "GET", "/care/todos") == []
            # 重启小车服务，未结任务必须仍然存在。
            processes[0].terminate()
            processes[0].wait(timeout=10)
            processes[0] = launch(0)
            assert request(0, "GET", "/tasks/current")["task_id"] == event["task_id"]
            for state in ("已接单", "已到场"):
                request(0, "PATCH", "/tasks/" + event["task_id"], {"robot_id": "A", "status": state})
            request(2, "POST", "/events/controlled-001/confirm", {"handled_by": "测试护工"})
            for index in range(3):
                assert request(index, "GET", "/events/current")["status"] == "已处理"
            # 重启护工服务，再验证最终状态。
            processes[2].terminate()
            processes[2].wait(timeout=10)
            processes[2] = launch(2)
            assert request(2, "GET", "/events/current")["status"] == "已处理"
            trace = request(1, "GET", "/events/controlled-001/trace")
            assert len(trace) == 8
            print(json.dumps({"scope": "software-only", "services": 3, "event_count": 1, "task_count": 1, "trace_records": len(trace), "care_todos_separated": "passed", "cross_process_websocket": "passed", "open_and_final_restart_recovery": "passed"}, ensure_ascii=False))
        except BaseException:
            log.flush()
            print((root / "services.log").read_text(encoding="utf-8"), file=sys.stderr)
            raise
        finally:
            for process in processes:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)
            log.close()


if __name__ == "__main__":
    main()
