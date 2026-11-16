#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为 sim2d_mvp_3.2.2.py 生成三联轨迹效果图。

设计原则：
1. 不改动 sim2d_mvp_3.2.2.py 的求解器；
2. 直接复用其 main()，分别跑多个场景；
3. 读取该脚本已保存的单场景 PNG，再拼成一张三联图；
4. 适合作为“先快速出图”的独立辅助程序。

默认三联场景：
- normal_occ
- lio_only
- mixed_all

使用示例：
python3 make_triptych_3_2_2.py \
    --src ./sim2d_mvp_3.2.2.py \
    --out ./figs/triptych_3.2.2_normal_lio_mixed.png
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont


DEFAULT_CASES = ["normal_occ", "lio_only", "mixed_all"]
CASE_LABELS: Dict[str, str] = {
    "normal_occ": "正常遮挡",
    "uwb_only": "单UWB退化",
    "lio_only": "单模态退化",
    "rtab_only": "单RTAB退化",
    "dual_lio_uwb": "LIO+UWB退化",
    "dual_rtab_uwb": "RTAB+UWB退化",
    "mixed_all": "混合退化",
}


def load_module(py_path: Path):
    if not py_path.exists():
        raise FileNotFoundError(f"找不到源脚本: {py_path}")

    spec = importlib.util.spec_from_file_location("sim2d_mvp_3_2_2_mod", str(py_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载模块: {py_path}")

    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def expected_single_fig_path(mod, case_name: str) -> Path:
    filename = (
        f"sim2d_mvp_3.2.2_{mod.BASELINE_MODE}_{case_name}_"
        f"uwb_prior_balanced_stronger_state_prior.png"
    )
    return Path("figs") / filename


def run_single_case(mod, case_name: str, quiet: bool = True) -> Path:
    # 关闭交互显示，避免逐张弹窗/阻塞
    mod.plt.show = lambda *args, **kwargs: None

    # 可选降低打印噪声；不改求解本体
    if quiet:
        if hasattr(mod, "PRINT_STAGE0_RMSE"):
            mod.PRINT_STAGE0_RMSE = False
        if hasattr(mod, "PRINT_STAGE2_STATE_STATS"):
            mod.PRINT_STAGE2_STATE_STATS = False

    mod.DEGRADATION_CASE = case_name

    # 清理当前 pyplot 状态，避免多次调用 main() 累积句柄
    plt.close("all")
    mod.main()
    plt.close("all")

    out_path = expected_single_fig_path(mod, case_name)
    if not out_path.exists():
        raise FileNotFoundError(f"单场景图未生成成功: {out_path}")
    return out_path


def _get_font(font_size: int = 28):
    # 尝试常见中文字体，找不到就退回默认字体
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, font_size)
            except Exception:
                pass
    return ImageFont.load_default()


def compose_triptych(single_paths: List[Path], case_names: List[str], out_path: Path, gap: int = 24) -> Path:
    images = [Image.open(p).convert("RGB") for p in single_paths]

    # 所有单图尺寸通常一致；这里仍做鲁棒处理，统一高度
    max_h = max(img.height for img in images)
    resized = []
    for img in images:
        if img.height != max_h:
            new_w = int(img.width * (max_h / img.height))
            img = img.resize((new_w, max_h), Image.LANCZOS)
        resized.append(img)

    label_band = 56
    total_w = sum(img.width for img in resized) + gap * (len(resized) - 1)
    total_h = label_band + max_h

    canvas = Image.new("RGB", (total_w, total_h), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    font = _get_font(28)

    x = 0
    for img, case in zip(resized, case_names):
        label = CASE_LABELS.get(case, case)
        canvas.paste(img, (x, label_band))

        # 文本居中
        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        tx = x + (img.width - tw) // 2
        ty = (label_band - (bbox[3] - bbox[1])) // 2 - 2
        draw.text((tx, ty), label, fill=(0, 0, 0), font=font)

        x += img.width + gap

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)
    return out_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="为 sim2d_mvp_3.2.2.py 生成三联轨迹效果图")
    parser.add_argument(
        "--src",
        type=str,
        default="sim2d_mvp_3.2.2.py",
        help="3.2.2 主脚本路径",
    )
    parser.add_argument(
        "--cases",
        nargs="+",
        default=DEFAULT_CASES,
        help="三联图场景列表，默认: normal_occ lio_only mixed_all",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="figs/triptych_3.2.2_normal_lio_mixed.png",
        help="三联图输出路径",
    )
    parser.add_argument(
        "--no-quiet",
        action="store_true",
        help="保留 3.2.2 脚本内部更多打印",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    src = Path(args.src).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()
    case_names = args.cases

    if len(case_names) < 2:
        raise ValueError("至少提供 2 个场景；三联图建议正好 3 个。")

    mod = load_module(src)

    # 切换到源脚本所在目录运行，确保它内部相对路径 figs/ 行为一致
    old_cwd = Path.cwd()
    try:
        os.chdir(src.parent)
        single_paths = []
        for case in case_names:
            print(f"\n[Triptych] 运行场景: {case}")
            single_png = run_single_case(mod, case_name=case, quiet=(not args.no_quiet))
            single_paths.append((src.parent / single_png).resolve())

        triptych_path = compose_triptych(
            single_paths=[p for p in single_paths],
            case_names=case_names,
            out_path=out,
        )
        print(f"\n[Triptych] 三联图已保存: {triptych_path}")
    finally:
        os.chdir(old_cwd)

    return 0


if __name__ == "__main__":
    sys.exit(main())
