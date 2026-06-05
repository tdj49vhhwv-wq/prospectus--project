#!/usr/bin/env python3
"""
==========================================================================
 PDF解析为Markdown (基于MinerU)
 将 data/prospectus_pdfs/ 中的PDF解析为 review/ 中的Markdown文件
==========================================================================
使用MinerU (magic_pdf) 命令行工具:
  magic-pdf -p <pdf_path> -o <output_dir> -m auto
==========================================================================
"""
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from logger_util import setup_logger, log_error, log_step, log_stats

BASE_DIR = Path("/Users/zhaobingqing/Documents/GitHub/prospectus-pevc-project")
PDF_DIR = BASE_DIR / "data" / "prospectus_pdfs"
REVIEW_DIR = BASE_DIR / "review"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
REVIEW_DIR.mkdir(parents=True, exist_ok=True)

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = LOG_DIR / f"pdf_parser_{RUN_ID}.log"
logger, _ = setup_logger("pdf_parser", LOG_FILE)

PARSE_STATS = {"total": 0, "success": 0, "failed": 0, "skipped": 0, "details": []}


def parse_with_mineru(pdf_path, output_dir):
    """使用MinerU命令行工具解析PDF"""
    cmd = [
        "magic-pdf",
        "-p", str(pdf_path),
        "-o", str(output_dir),
        "-m", "auto",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, result.stderr
    except FileNotFoundError:
        return False, "MinerU未安装，请运行: pip install magic-pdf"
    except subprocess.TimeoutExpired:
        return False, "解析超时(>10min)"
    except Exception as e:
        return False, str(e)


def parse_with_pymupdf(pdf_path, output_path):
    """备选方案：使用PyMuPDF解析PDF为文本"""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# {pdf_path.stem}\n\n")
            for page_num, page in enumerate(doc):
                text = page.get_text()
                f.write(f"## 第{page_num + 1}页\n\n")
                f.write(text + "\n\n")
        doc.close()
        return True, f"共{doc.page_count}页"
    except ImportError:
        return False, "PyMuPDF未安装，请运行: pip install PyMuPDF"
    except Exception as e:
        return False, str(e)


def process_all(use_mineru=True):
    """批量解析所有PDF"""
    logger.info("╔══════════════════════════════════════════╗")
    logger.info("║  PDF解析为Markdown                        ║")
    logger.info(f"║  Run ID: {RUN_ID}               ║")
    logger.info("╚══════════════════════════════════════════╝")

    pdf_files = sorted(PDF_DIR.glob("*.pdf"))
    PARSE_STATS["total"] = len(pdf_files)
    logger.info(f"  发现 {len(pdf_files)} 个PDF文件")

    for pdf_path in pdf_files:
        name = pdf_path.stem
        output_path = REVIEW_DIR / f"{name}.md"

        if output_path.exists():
            logger.info(f"  ⊙ {name}: 已存在 -> {output_path.name}")
            PARSE_STATS["skipped"] += 1
            continue

        logger.info(f"  → {name}: 开始解析...")

        if use_mineru:
            success, msg = parse_with_mineru(pdf_path, REVIEW_DIR)
        else:
            success, msg = parse_with_pymupdf(pdf_path, output_path)

        if success:
            logger.info(f"    ✓ {name}: 解析成功 ({msg})")
            PARSE_STATS["success"] += 1
            PARSE_STATS["details"].append({"file": name, "status": "success", "info": msg})
        else:
            logger.error(f"    ✗ {name}: {msg}")
            PARSE_STATS["failed"] += 1
            PARSE_STATS["details"].append({"file": name, "status": "failed", "error": msg})

            # 如果MinerU失败，尝试PyMuPDF
            if use_mineru:
                logger.info(f"    → {name}: MinerU失败，尝试PyMuPDF...")
                success2, msg2 = parse_with_pymupdf(pdf_path, output_path)
                if success2:
                    logger.info(f"    ✓ {name}: PyMuPDF解析成功 ({msg2})")
                    PARSE_STATS["success"] += 1
                    PARSE_STATS["failed"] -= 1

    # 保存记录
    record_path = LOG_DIR / f"parse_record_{RUN_ID}.json"
    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(PARSE_STATS, f, ensure_ascii=False, indent=2)

    log_stats(logger, PARSE_STATS)
    return PARSE_STATS


if __name__ == "__main__":
    try:
        process_all(use_mineru=False)  # 默认使用PyMuPDF (不需额外安装MinerU)
    except Exception as e:
        log_error(logger, e, "PDF解析异常退出")
        sys.exit(1)
