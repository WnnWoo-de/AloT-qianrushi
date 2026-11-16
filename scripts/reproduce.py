"""输出新实验到独立目录，保留配置、源码哈希、环境与逐轮结果。"""
import argparse
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import statistics
import sys

os.environ.setdefault("MPLBACKEND", "Agg")
ROOT = Path(__file__).resolve().parents[1]


def load(path):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("experiment", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def save_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment", choices=["scheduling", "avoidance"])
    parser.add_argument("--runs", type=int, default=20, help="调度种子数；避障为确定性场景各1轮")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs 必须 >= 1")
    out = args.output or ROOT / "artifacts" / args.experiment
    out.mkdir(parents=True, exist_ok=True)
    if args.experiment == "scheduling":
        source = next((ROOT / "src").glob("云边协同决策*/patent_simulation.py"))
    else:
        source = next((ROOT / "src").glob("端边协同执行*/dynamic_obstacle_demo/two_robot_overlap_demo.py"))
    module = load(source)
    import numpy as np
    import matplotlib
    manifest = {"kind": "simulation-not-field-test", "command": sys.argv, "python": platform.python_version(), "numpy": np.__version__, "matplotlib": matplotlib.__version__, "source": str(source.relative_to(ROOT)), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    if args.experiment == "scheduling":
        seeds = [module.BASE_OBSTACLE_SEED + i * 17 for i in range(args.runs)]
        manifest.update(seeds=seeds, event_steps=[module.EVENT_STEP], return_steps=[module.RETURN_STEP], total_steps=module.TOTAL_STEPS, coverage_window_steps=module.WINDOW, coverage_unit="ratio [0,1]", latency_unit="step", scope="单事件配置，不能直接对应PDF双事件曲线")
        rows = []
        for method in ("patent", "baseline"):
            for seed in seeds:
                run = module.run_method(method, seed)
                metrics = run["metrics"]
                save_csv(out / f"{method}-{seed}-timeline.csv", metrics)
                latency = run["response_time"]
                rows.append({"method": method, "seed": seed, "response_steps": latency if latency >= 0 else "", "success": latency >= 0, "event_min_coverage_ratio": min(m["coverage"] for m in metrics if module.EVENT_STEP <= m["step"] <= module.RETURN_STEP), "global_replans": run["global_replans"]})
        save_csv(out / "runs.csv", rows)
        summary = []
        for method in ("patent", "baseline"):
            group = [r for r in rows if r["method"] == method]
            latencies = [r["response_steps"] for r in group if r["success"]]
            summary.append({"method": method, "total": len(group), "success": len(latencies), "failed_or_timeout": len(group) - len(latencies), "mean_success_response_steps": statistics.mean(latencies) if latencies else None, "worst_success_response_steps": max(latencies) if latencies else None, "mean_event_min_coverage_ratio": statistics.mean(r["event_min_coverage_ratio"] for r in group), "worst_event_min_coverage_ratio": min(r["event_min_coverage_ratio"] for r in group)})
        (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        manifest.update(methods=module.METHOD_LABELS, robot_max_speed_mps=module.ROBOT_MAX_SPEED.tolist(), start_delay_s=module.ROBOT_START_DELAY.tolist(), hard_separation_m=module.SAFE_MARGIN_BETWEEN_ROBOTS, dt_s=module.DT, sample_count_per_method=1, seed=None, caveat="确定性规则对比，非SAC；硬投影及到点吸附不是动力学可执行控制，不应转为实车指令")
        rows = []
        for method in ("rl", "apf"):
            times, positions, velocities, obstacles, indices, arrivals = module.run_simulation(method)
            clearance = module.min_clearance_to_any_obstacle(positions, obstacles)
            rows.append(module.build_method_metrics(method, times, positions, velocities, clearance, arrivals))
            trajectory = module.save_robot_csv(out, times, positions, velocities, indices, clearance, arrivals)
            # 原函数使用固定文件名，按方法重命名避免互相覆盖。
            trajectory.replace(out / f"{method}-trajectories.csv")
            schedule = module.save_obstacle_csv(out, obstacles, times)
            schedule.replace(out / f"{method}-obstacles.csv")
        save_csv(out / "metrics.csv", rows)
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out.resolve())


if __name__ == "__main__":
    main()
