#!/usr/bin/env python3
"""
日志系统 - 为所有提取脚本提供统一日志记录
"""
import logging
import sys
from pathlib import Path
from datetime import datetime

import sys
from pathlib import Path

# 确保能导入同级 config 模块
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import LOG_DIR


def setup_logger(name, log_file=None):
    """创建带时间戳的logger"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # 控制台输出
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    console.setFormatter(console_fmt)

    # 文件输出
    if log_file is None:
        log_file = LOG_DIR / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s")
    file_handler.setFormatter(file_fmt)

    logger.addHandler(console)
    logger.addHandler(file_handler)

    return logger, log_file


def log_error(logger, error, context=""):
    """记录错误详情"""
    import traceback
    logger.error(f"[ERROR] {context}")
    logger.error(f"[ERROR] Type: {type(error).__name__}")
    logger.error(f"[ERROR] Message: {str(error)}")
    logger.debug(f"[TRACEBACK]\n{traceback.format_exc()}")


def log_step(logger, step_name, status="START"):
    """记录步骤"""
    border = "=" * 50
    if status == "START":
        logger.info(f"\n{border}\n  ▶ {step_name}\n{border}")
    elif status == "DONE":
        logger.info(f"  ✓ {step_name} 完成")
    elif status == "FAIL":
        logger.error(f"  ✗ {step_name} 失败")
    elif status == "SKIP":
        logger.warning(f"  ⊘ {step_name} 跳过")


def log_stats(logger, stats_dict):
    """记录统计信息"""
    logger.info("--- 统计信息 ---")
    for k, v in stats_dict.items():
        logger.info(f"  {k}: {v}")
    logger.info("----------------")
