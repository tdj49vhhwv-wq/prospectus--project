#!/bin/bash
# ============================================================
# Week 2 一键流水线: PDF解析 → JSONL生成 → 校验 → Excel
# 用法: bash scripts/run_all.sh
# ============================================================
set -e
cd "$(dirname "$0")/.."

echo "╔══════════════════════════════════════════════════════╗"
echo "║  Week 2 招股书股本变化提取 - 一键流水线             ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# Step 1: 模型检查
echo ">>> [1/4] Pydantic 模型检查"
python3 -c "from schemas.models import SubscriptionFlow, EquitySnapshot; print('  ✓ 模型加载成功')" || { echo "  ✗ schemas/models.py 有语法错误"; exit 1; }
echo ""

# Step 2: JSONL 生成
echo ">>> [2/4] 生成 JSONL (8家公司)"
python3 scripts/generate_jsonl.py
echo ""

# Step 3: Schema + Cross-Check 校验
echo ">>> [3/4] Pydantic Schema 校验 + 数值 Cross-Check"
python3 scripts/validate_jsonl.py
echo ""

# Step 4: JSONL → Excel
echo ">>> [4/4] JSONL → Excel (三表格式)"
python3 scripts/jsonl_to_excel.py
echo ""

echo "╔══════════════════════════════════════════════════════╗"
echo "║  流水线完成!                                        ║"
echo "║  JSONL: outputs/week2_jsonl/                         ║"
echo "║  Excel: outputs/week2_excel/                         ║"
echo "║  日志:  logs/schema_validation_log.csv               ║"
echo "║         logs/cross_check_summary.csv                 ║"
echo "╚══════════════════════════════════════════════════════╝"
