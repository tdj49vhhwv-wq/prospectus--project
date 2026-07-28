#!/bin/bash
# Week 4 PE/VC 专项提取 - 一键运行
# 用法: bash run_week4.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "========================================"
echo "  Week 4: 三协电机 PE/VC 专项提取"
echo "========================================"
echo ""

cd "$SCRIPT_DIR"

python3 scripts/run_week4.py "$@"

echo ""
echo "完成。查看输出: outputs/"
