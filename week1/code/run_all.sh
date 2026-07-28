#!/bin/bash
# ============================================================
#  招股书PEVC融资历史提取 - 一键运行脚本
#  按顺序执行: 爬虫 → 解析 → 结构化 → Schema JSON
# ============================================================
set -e

# 自动定位项目根目录 (run_all.sh 所在目录的上级)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CODE_DIR="$PROJECT_DIR/code"
LOG_DIR="$PROJECT_DIR/logs"

cd "$PROJECT_DIR"
mkdir -p "$LOG_DIR"

echo "╔════════════════════════════════════════════╗"
echo "║  招股书 PEVC 融资历史提取 - 全流程       ║"
echo "╚════════════════════════════════════════════╝"
echo ""

# Step 0: 环境检查
echo ">>> Step 0: 环境检查"
python3 -c "import json, csv, re, pathlib; print('  ✓ Python基础库 OK')"
python3 -c "import urllib.request; print('  ✓ urllib OK')" 2>/dev/null || echo "  ⚠ urllib可能有问题"
echo ""

# Step 1: PDF下载 (如果CSV中有URL)
echo ">>> Step 1: PDF下载爬虫"
python3 "$CODE_DIR/05_pdf_downloader.py" 2>&1 | tee -a "$LOG_DIR/downloader.log"
echo ""

# Step 2: PDF解析为Markdown
echo ">>> Step 2: PDF解析为Markdown"
python3 "$CODE_DIR/06_pdf_to_markdown.py" 2>&1 | tee -a "$LOG_DIR/parser.log"
echo ""

# Step 3: 主Pipeline (定位章节 + 截取文本 + 结构化JSON + Schema校验)
echo ">>> Step 3: 融资历史提取Pipeline"
python3 "$CODE_DIR/pipeline_main.py" 2>&1 | tee -a "$LOG_DIR/pipeline.log"
echo ""

# Step 4: Schema JSON输出 (5家重点公司)
echo ">>> Step 4: 生成最终Schema JSON"
python3 "$CODE_DIR/04_schema_json_output.py" 2>&1 | tee -a "$LOG_DIR/schema_output.log"
echo ""

echo "╔════════════════════════════════════════════╗"
echo "║  全流程完成!                              ║"
echo "║  日志目录: $LOG_DIR                       ║"
echo "║  输出目录: $PROJECT_DIR/outputs/           ║"
echo "╚════════════════════════════════════════════╝"
