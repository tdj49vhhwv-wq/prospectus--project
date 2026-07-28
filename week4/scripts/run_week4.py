#!/usr/bin/env python3
"""
Week 4 一键流水线: 三协电机 PE/VC 专项提取

流水线架构（老师要求: 定位-抽取两步独立 + 完整step_log）:

  Step 0 [⚠人工] PDF下载 (已完成: week1/data/week1PDF/)
    ↓
  Step 1 [⚙自动] PE/VC章节定位 (代码定位 + 关键词截取)
    ↓
  Step 2 [⚙自动] PE/VC结构化提取 (表格 + 文本 + PE基金详情)
    ↓
  Step 3 [⚙自动] OCR + 结构化表格处理
    ↓
  Step 4 [⚙自动] Pydantic Schema校验
    ↓
  Step 5 [⚙自动] 数值Cross-Check
    ↓
  Step 6 [⚙自动] 生成提取报告

用法:
  python3 run_week4.py           # 运行全流程
  python3 run_week4.py --step 1  # 只运行Step 1
"""
import json
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
from config import *


def run_step(step_num: int, script_name: str, description: str) -> bool:
    """运行单个步骤并记录结果"""
    print(f"\n{'='*60}")
    print(f"  Step {step_num}: {description}")
    print(f"{'='*60}")

    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        print(f"  ✗ 脚本不存在: {script_path}")
        return False

    start = time.time()
    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=False,
        cwd=str(SCRIPTS_DIR),
    )
    elapsed = time.time() - start

    if result.returncode == 0:
        print(f"  ✓ Step {step_num} 完成 ({elapsed:.1f}s)")
        return True
    else:
        print(f"  ✗ Step {step_num} 失败 (exit={result.returncode}, {elapsed:.1f}s)")
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Week 4 PE/VC 提取流水线")
    parser.add_argument("--step", type=int, choices=[1, 2, 3], help="只运行指定步骤")
    parser.add_argument("--from-step", type=int, choices=[1, 2, 3], help="从指定步骤开始运行")
    args = parser.parse_args()

    print("=" * 60)
    print(f"  Week 4 PE/VC 专项提取流水线")
    print(f"  目标: {TARGET['name']} ({TARGET['code']})")
    print(f"  时间: {datetime.now().isoformat()}")
    print(f"  PDF: {TARGET['pdf']}")
    print("=" * 60)

    # ── 前置检查 ──
    pdf_path = PDF_DIR / TARGET["pdf"]
    if not pdf_path.exists():
        print(f"\n✗ PDF不存在: {pdf_path}")
        print(f"  → 请先下载PDF到 {PDF_DIR}")
        return 1

    # ── 初始化 step_log ──
    STEP_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(STEP_LOG, "w", encoding="utf-8") as f:
        f.write("timestamp,step,status,detail\n")

    # ── 执行流水线 ──
    steps = [
        (1, "locate_pevc_sections.py", "PE/VC章节定位"),
        (2, "extract_pevc.py", "PE/VC结构化提取"),
        (3, "ocr_extract.py", "OCR+结构化表格处理"),
    ]

    start_step = args.from_step or args.step or 1
    end_step = args.step or 3

    results = {}
    for step_num, script, desc in steps:
        if step_num < start_step or step_num > end_step:
            print(f"\n  → Step {step_num} 跳过")
            continue

        success = run_step(step_num, script, desc)
        results[step_num] = success

        if not success and not args.step:
            print(f"\n  ⚠ Step {step_num} 失败，流水线中止")
            break

    # ── 汇总 ──
    print(f"\n{'='*60}")
    print(f"  流水线汇总")
    print(f"{'='*60}")
    for step_num, success in results.items():
        icon = "✓" if success else "✗"
        print(f"  {icon} Step {step_num}")

    # ── 输出文件清单 ──
    print(f"\n  输出文件:")
    output_files = [
        (OUTPUTS_DIR / "located_sections.json", "章节定位结果"),
        (SF_JSONL, "认缴流量"),
        (ES_JSONL, "股权结构快照"),
        (PE_DETAIL_JSONL, "PE基金详情"),
        (ST_JSONL, "股权转让"),
        (OUTPUTS_DIR / "ocr_tables.json", "OCR表格数据"),
        (STEP_LOG, "步骤日志"),
    ]
    for path, desc in output_files:
        icon = "✓" if path.exists() else "✗"
        size = f"({path.stat().st_size:,}B)" if path.exists() else "(未生成)"
        print(f"  {icon} {desc}: {path.relative_to(PROJECT_ROOT)} {size}")

    all_success = all(results.values()) if results else False
    if all_success:
        print(f"\n✓ 全流程完成！")
    else:
        print(f"\n⚠ 部分步骤失败，请查看 {STEP_LOG}")

    return 0 if all_success else 1


if __name__ == "__main__":
    sys.exit(main())
