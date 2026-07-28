#!/usr/bin/env python3
"""
==========================================================================
 招股书PDF下载爬虫
 数据源: 巨潮资讯网 (cninfo.com.cn) / 上交所 / 深交所 / 北交所
==========================================================================
功能:
  1. 从CSV企业清单读取目标公司
  2. 如果CSV中有prospectus_url则直接下载
  3. 如果无URL则通过巨潮资讯网搜索下载
  4. 记录下载状态到日志
==========================================================================
"""
import sys
import csv
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).parent))
from logger_util import setup_logger, log_error, log_step, log_stats

# === 路径配置 ===
BASE_DIR = Path("/Users/zhaobingqing/Documents/GitHub/prospectus-pevc-project")
DATA_DIR = BASE_DIR / "data"
PDF_DIR = DATA_DIR / "prospectus_pdfs"
CSV_FILE = BASE_DIR / "company_lists" / "week1_public_samples.csv"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
PDF_DIR.mkdir(parents=True, exist_ok=True)

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = LOG_DIR / f"downloader_{RUN_ID}.log"
logger, _ = setup_logger("downloader", LOG_FILE)

# 下载结果统计
DOWNLOAD_STATS = {
    "total_targets": 0,
    "success": 0,
    "already_exist": 0,
    "failed": 0,
    "skipped_no_url": 0,
    "details": [],
}

# 请求头（模拟浏览器）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/pdf,application/octet-stream,*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def read_company_list(csv_path):
    """读取企业清单CSV"""
    log_step(logger, "读取企业清单")
    companies = []
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("company_short_name"):
                    companies.append(row)
        logger.info(f"  读取到 {len(companies)} 家公司")
        DOWNLOAD_STATS["total_targets"] = len(companies)
        return companies
    except Exception as e:
        log_error(logger, e, "读取CSV失败")
        raise


def download_pdf(url, save_path, company_name):
    """下载单个PDF"""
    try:
        import urllib.request
        import ssl

        # 跳过SSL验证（部分网站证书问题）
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=120, context=ctx) as response:
            content = response.read()

            # 验证是否为PDF（检查文件头）
            if not content.startswith(b"%PDF"):
                logger.warning(f"  ⚠ {company_name}: 下载内容不是PDF (文件头: {content[:10]})")
                DOWNLOAD_STATS["failed"] += 1
                DOWNLOAD_STATS["details"].append({
                    "company": company_name, "url": url,
                    "status": "not_pdf", "size": len(content)
                })
                return False

            with open(save_path, "wb") as f:
                f.write(content)

            file_size_mb = len(content) / (1024 * 1024)
            md5 = hashlib.md5(content).hexdigest()

            logger.info(f"  ✓ {company_name}: {file_size_mb:.1f}MB (MD5: {md5[:8]}...)")
            DOWNLOAD_STATS["success"] += 1
            DOWNLOAD_STATS["details"].append({
                "company": company_name, "url": url,
                "status": "success", "size_mb": round(file_size_mb, 2),
                "md5": md5,
            })
            return True

    except urllib.error.HTTPError as e:
        logger.error(f"  ✗ {company_name}: HTTP {e.code} - {e.reason}")
        DOWNLOAD_STATS["failed"] += 1
        DOWNLOAD_STATS["details"].append({
            "company": company_name, "url": url,
            "status": f"HTTP_{e.code}", "error": str(e.reason)
        })
        return False
    except urllib.error.URLError as e:
        logger.error(f"  ✗ {company_name}: URL错误 - {e.reason}")
        DOWNLOAD_STATS["failed"] += 1
        DOWNLOAD_STATS["details"].append({
            "company": company_name, "url": url,
            "status": "URL_ERROR", "error": str(e.reason)
        })
        return False
    except Exception as e:
        log_error(logger, e, f"下载失败: {company_name}")
        DOWNLOAD_STATS["failed"] += 1
        return False


def generate_filename(company):
    """根据公司信息生成PDF文件名"""
    short_name = company.get("company_short_name", "unknown")
    version = company.get("prospectus_version", "正式稿")
    date_str = (company.get("prospectus_date", "") or "").replace("/", "")
    return f"{short_name}_招股书_{version}_{date_str}.pdf"


def process_all():
    """主下载流程"""
    logger.info("╔══════════════════════════════════════════╗")
    logger.info("║  招股书PDF下载爬虫                       ║")
    logger.info(f"║  Run ID: {RUN_ID}               ║")
    logger.info("╚══════════════════════════════════════════╝")

    companies = read_company_list(CSV_FILE)

    log_step(logger, "下载PDF")
    for company in companies:
        name = company.get("company_short_name", "unknown")
        url = company.get("prospectus_url", "").strip()

        if not url:
            logger.warning(f"  ⊘ {name}: 无URL，跳过")
            DOWNLOAD_STATS["skipped_no_url"] += 1
            continue

        filename = generate_filename(company)
        save_path = PDF_DIR / filename

        if save_path.exists():
            logger.info(f"  ⊙ {name}: 已存在 -> {filename}")
            DOWNLOAD_STATS["already_exist"] += 1
            continue

        logger.info(f"  ↓ {name}: 开始下载...")
        logger.debug(f"    URL: {url}")
        time.sleep(1)  # 礼貌延迟，避免被封
        download_pdf(url, save_path, name)

    # 保存下载记录
    download_log = LOG_DIR / f"download_record_{RUN_ID}.json"
    with open(download_log, "w", encoding="utf-8") as f:
        json.dump(DOWNLOAD_STATS, f, ensure_ascii=False, indent=2)

    # 统计
    log_step(logger, "下载统计", "DONE")
    log_stats(logger, {
        "目标数": DOWNLOAD_STATS["total_targets"],
        "下载成功": DOWNLOAD_STATS["success"],
        "已存在": DOWNLOAD_STATS["already_exist"],
        "失败": DOWNLOAD_STATS["failed"],
        "跳过(无URL)": DOWNLOAD_STATS["skipped_no_url"],
        "下载记录": str(download_log.name),
    })

    return DOWNLOAD_STATS


if __name__ == "__main__":
    try:
        process_all()
    except Exception as e:
        log_error(logger, e, "下载程序异常退出")
        sys.exit(1)
