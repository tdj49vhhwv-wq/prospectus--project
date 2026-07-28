#!/bin/bash
# Week 3 一键运行
# 用法: cd 项目根目录 && bash scripts/run_week3.sh
set -e
cd "$(dirname "$0")/.."

echo "============================================"
echo "Week 3 Auto Pipeline"
echo "============================================"

echo ""
echo "[Step 1/3] 规则自动提取..."
python3 scripts/extract_with_rules.py

echo ""
echo "[Step 2/3] Schema校验 + Cross-Check..."
python3 scripts/validate_schema.py

echo ""
echo "[Step 3/4] Cross-check数字重建 (全部列)..."
python3 scripts/build_cross_check.py

echo ""
echo "[Step 4/4] Auto vs Gold对比..."
python3 scripts/compare_to_gold.py

echo ""
echo "============================================"
echo "完成! 输出文件:"
echo "  auto_jsonl:      outputs/jsonl/"
echo "  schema日志:      logs/schema_validation_log.csv"
echo "  cross-check:     logs/cross_check_summary.csv"
echo "  auto vs gold:    reports/auto_vs_gold_comparison.xlsx"
echo "  manual_gold:     manual_gold/"
echo "============================================"
