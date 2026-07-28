#!/usr/bin/env python3
"""
Week 3 自动化流程 — 一键运行入口

用法: python3 pipeline/run_all.py [--step 1-6]

流程步骤:
  [人工] Step 0: PDF下载 + PDF→MD解析
  [自动] Step 1: extract_with_rules.py  — 规则自动提取 → auto_jsonl/
  [半自动] Step 2: 人工Gold生成        — ⚠ 人工回到PDF复核,生成structured JSON
  [自动] Step 3: validate_schema.py    — Pydantic校验 + Cross-Check
  [自动] Step 4: compare_to_gold.py    — Auto vs Gold逐字段对比
  [人工] Step 5: 失败样本复核          — 检查evaluation/中的差异,更新manual_review_queue.csv

⚠ 人工环节说明:
  Step 0: 从巨潮资讯网(cninfo.com.cn)下载招股书PDF, 用PyMuPDF解析为review/*.md
  Step 2: 阅读PDF原文, 逐项提取融资事件, 保存为outputs/{公司名}/{公司名}_融资历史_结构化.json
  Step 5: 检查auto_vs_gold_comparison.xlsx中标记mismatch/gold_only的行, 判断是Gold缺失还是Auto误提
"""
import sys
import subprocess
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent


def run_script(name, args=None):
    """运行pipeline脚本"""
    script = PIPELINE_DIR / name
    if not script.exists():
        print(f"  ✗ 脚本不存在: {name}")
        return 1
    cmd = [sys.executable, str(script)]
    if args:
        cmd.extend(args)
    result = subprocess.run(cmd, cwd=str(PIPELINE_DIR))
    return result.returncode


def print_step(n, title, step_type):
    icon = "⚠" if step_type == "manual" else ("◐" if step_type == "semi" else "⚙")
    print(f"\n{'='*60}")
    print(f"  {icon} Step {n} [{step_type.upper()}]: {title}")
    print(f"{'='*60}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Week 3 自动化流程")
    parser.add_argument("--step", type=int, choices=range(0, 7), help="只运行指定步骤")
    parser.add_argument("--skip-manual", action="store_true", help="跳过人工步骤提示")
    args = parser.parse_args()

    steps = []

    # Step 0: PDF解析 (人工)
    if args.step is None or args.step == 0:
        steps.append((0, "PDF下载 + PyMuPDF解析为MD", "manual",
                      "从巨潮资讯网下载招股书PDF → python3 parse_pdf.py → review/*.md",
                      "parse_pdf.py", []))

    # Step 1: 规则自动提取
    if args.step is None or args.step == 1:
        steps.append((1, "规则自动提取 (extract_with_rules)", "auto",
                      "正则+关键词从MD中提取认购事件",
                      "extract_with_rules.py", []))

    # Step 2: 人工Gold生成 (半自动)
    if args.step is None or args.step == 2:
        steps.append((2, "人工Gold生成 (extract_with_llm)", "semi",
                      "⚠ 人工从PDF逐项复核 → 生成_融资历史_结构化.json → 脚本转为JSONL",
                      "extract_with_llm.py", []))

    # Step 3: Schema校验 + Cross-Check
    if args.step is None or args.step == 3:
        steps.append((3, "Schema校验 + Cross-Check (validate_schema)", "auto",
                      "Pydantic校验字段类型/必填项 + 流量存量交叉验证",
                      "validate_schema.py", []))

    # Step 4: Auto vs Gold对比
    if args.step is None or args.step == 4:
        steps.append((4, "Auto vs Gold对比 (compare_to_gold)", "auto",
                      "逐字段diff: match/mismatch/auto_only/gold_only",
                      "compare_to_gold.py", []))

    # Step 5: 失败样本复核 (人工)
    if args.step is None or args.step == 5:
        steps.append((5, "失败样本复核", "manual",
                      "检查 evaluation/auto_vs_gold_comparison.xlsx, 更新 manual_review_queue.csv",
                      None, []))

    # 执行
    errors = 0
    for n, title, step_type, desc, script, script_args in steps:
        print_step(n, title, step_type)
        print(f"  {desc}")

        if script is None:
            print(f"  → 人工操作, 请完成后继续")
            if not args.skip_manual:
                print(f"  → 文件: evaluation/auto_vs_gold_comparison.xlsx")
                print(f"  → 队列: manual_gold/manual_review_queue.csv")
        else:
            rc = run_script(script, script_args)
            if rc != 0:
                print(f"  ✗ 失败 (exit code={rc})")
                errors += 1
            else:
                print(f"  ✓ 完成")

    # 最终输出摘要
    print(f"\n{'='*60}")
    print(f"  流程结束 (错误: {errors})")
    print(f"{'='*60}")
    print(f"\n输出文件:")
    print(f"  auto_jsonl:        {PIPELINE_DIR.parent}/outputs/auto_jsonl/")
    print(f"  auto_excel:        {PIPELINE_DIR.parent}/outputs/auto_excel/")
    print(f"  schema日志:        {PIPELINE_DIR.parent}/logs/schema_validation_log.csv")
    print(f"  cross-check:       {PIPELINE_DIR.parent}/logs/cross_check_summary.csv")
    print(f"  auto vs gold:      {PIPELINE_DIR.parent}/evaluation/auto_vs_gold_comparison.xlsx")
    print(f"  失败样本队列:       {PIPELINE_DIR.parent}/manual_gold/manual_review_queue.csv")

    if errors == 0:
        print(f"\n✓ 所有自动步骤通过")
    else:
        print(f"\n⚠ {errors}个步骤失败, 请检查日志")

    return errors


if __name__ == "__main__":
    sys.exit(main())
