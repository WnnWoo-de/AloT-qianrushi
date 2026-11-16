"""从仓库根目录启动三端，共享本机数据库；Ctrl+C 清理全部子进程。"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SERVICES = [("云端小车监控中心", 8001), ("云端监控中心", 8002), ("护工移动端", 8003)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "runtime/collaboration.sqlite3")
    args = parser.parse_args()
    env = {**os.environ, "SILVERGUARD_DB": str(args.db.resolve())}
    children = []
    try:
        for name, port in SERVICES:
            children.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT / "src" / name / "backend", env=env))
        print("协同链路仅监听 127.0.0.1，数据库：", args.db.resolve(), flush=True)
        while all(p.poll() is None for p in children):
            time.sleep(0.5)
        raise SystemExit("有服务退出，请检查端口和启动日志。")
    except KeyboardInterrupt:
        pass
    finally:
        for p in children:
            if p.poll() is None:
                p.terminate()
        for p in children:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()


if __name__ == "__main__":
    main()
