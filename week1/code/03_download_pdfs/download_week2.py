#!/usr/bin/env python3
"""
==========================================================================
 Week 2 科创板招股书PDF批量下载脚本
 使用curl下载（绕过Python SSL兼容性问题）
==========================================================================
用法:
  python3 download_week2.py          # 下载所有有URL的公司
  python3 download_week2.py --dry-run  # 仅检查，不下载
  python3 download_week2.py --retry-failed  # 重试之前失败的
==========================================================================
"""
import csv
import subprocess
import sys
import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path("/Users/zhaobingqing/Documents/GitHub/prospectus-pevc-project")
CSV_FILE = BASE_DIR / "company_lists" / "week2_2025_company_list.csv"
PDF_DIR = BASE_DIR / "week2PDF"
LOG_FILE = PDF_DIR / "download_log.json"

PDF_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = [
    "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept: application/pdf,application/octet-stream,*/*",
    "Accept-Language: zh-CN,zh;q=0.9,en;q=0.8",
]


def build_filename(row):
    """根据CSV行构建PDF文件名: 股票代码_公司简称_招股书_版本_日期.pdf"""
    code = row.get("stock_code", "unknown")
    name = row.get("company_short_name", "unknown")
    version = row.get("prospectus_version", "") or "正式稿"
    # 解析日期，支持 2025/1/6 和 2025/01/06 两种格式
    raw_date = (row.get("prospectus_date", "") or "").strip()
    try:
        parts = raw_date.replace("/", "-").replace(".", "-").split("-")
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 1
        date_str = f"{y:04d}{m:02d}{d:02d}"
    except (ValueError, IndexError):
        date_str = raw_date.replace("/", "")
    return f"{code}_{name}_招股书_{version}_{date_str}.pdf"


def curl_download(url, save_path, timeout=120):
    """用curl下载PDF"""
    cmd = [
        "curl", "-sL", "-o", str(save_path),
        "--connect-timeout", "15",
        "--max-time", str(timeout),
        "-w", "%{http_code}|%{size_download}|%{time_total}",
    ]
    for h in HEADERS:
        cmd.extend(["-H", h])
    cmd.append(url)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)
        parts = result.stdout.strip().split("|")
        http_code = int(parts[0]) if parts and parts[0].isdigit() else 0
        size = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        elapsed = float(parts[2]) if len(parts) > 2 else 0

        if http_code != 200:
            save_path.unlink(missing_ok=True)
            return False, f"HTTP {http_code}", 0

        if size < 50000:  # <50KB，可能是错误页面或提示性公告
            save_path.unlink(missing_ok=True)
            return False, f"文件太小({size/1024:.0f}KB)，可能为提示性公告非完整招股书", size

        return True, f"{size/1024/1024:.1f}MB ({elapsed:.1f}s)", size

    except subprocess.TimeoutExpired:
        save_path.unlink(missing_ok=True)
        return False, "下载超时", 0
    except Exception as e:
        save_path.unlink(missing_ok=True)
        return False, str(e), 0


def validate_pdf(filepath):
    """验证PDF有效性"""
    try:
        with open(filepath, "rb") as f:
            header = f.read(5)
        if header != b"%PDF-":
            return False, f"非PDF文件头: {header}"
        # 检查文件大小（完整招股书通常 > 1MB）
        size_mb = filepath.stat().st_size / (1024 * 1024)
        if size_mb < 1:
            return False, f"文件过小({size_mb:.1f}MB)，可能非完整招股书"
        if size_mb > 100:
            return False, f"文件过大({size_mb:.1f}MB)，可能含异常附件"
        return True, f"{size_mb:.1f}MB"
    except Exception as e:
        return False, str(e)


def read_csv():
    """读取企业清单CSV"""
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_log(log_data):
    """保存下载日志"""
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)


def main():
    dry_run = "--dry-run" in sys.argv
    retry_failed = "--retry-failed" in sys.argv

    # 读取已有日志
    if LOG_FILE.exists():
        with open(LOG_FILE, "r") as f:
            log = json.load(f)
    else:
        log = {"run_time": "", "results": [], "stats": {}}

    rows = read_csv()
    results = []
    stats = {"total": 0, "success": 0, "skipped": 0, "failed": 0, "no_url": 0}

    print("=" * 70)
    print("  Week 2 科创板招股书PDF批量下载")
    print(f"  目标目录: {PDF_DIR}")
    if dry_run:
        print("  *** DRY RUN 模式，仅检查不下载 ***")
    print("=" * 70)
    print()

    for row in rows:
        sid = row.get("sample_id", "")
        name = row.get("company_short_name", "")
        url = row.get("prospectus_url", "").strip()
        stats["total"] += 1

        # 检查是否已存在
        filename = build_filename(row)
        filepath = PDF_DIR / filename

        # 也检查模糊匹配（版本/日期可能不同）
        code = row.get("stock_code", "")
        existing = list(PDF_DIR.glob(f"{code}_*.pdf"))
        if existing:
            print(f"  [{sid}] {name}: ⊙ 已存在 → {existing[0].name}")
            results.append({"sample_id": sid, "company": name, "status": "skipped",
                           "reason": "already_exists", "file": str(existing[0].name)})
            stats["skipped"] += 1
            continue

        # 检查URL
        if not url:
            print(f"  [{sid}] {name}: ⊘ 无URL，跳过")
            results.append({"sample_id": sid, "company": name, "status": "no_url"})
            stats["no_url"] += 1
            continue

        # 下载
        print(f"  [{sid}] {name}: ↓ {url[:80]}...")
        if dry_run:
            print(f"         [DRY RUN] 将保存为: {filename}")
            results.append({"sample_id": sid, "company": name, "status": "dry_run",
                           "url": url, "target_file": filename})
            continue

        success, msg, size = curl_download(url, filepath)
        if success:
            # 验证
            valid, vmsg = validate_pdf(filepath)
            if valid:
                print(f"         ✓ {msg} (PDF {vmsg})")
                results.append({"sample_id": sid, "company": name, "status": "success",
                               "size_mb": round(size / 1024 / 1024, 2), "file": filename})
                stats["success"] += 1
            else:
                print(f"         ✗ PDF验证失败: {vmsg}")
                filepath.unlink(missing_ok=True)
                results.append({"sample_id": sid, "company": name, "status": "failed",
                               "reason": f"validate: {vmsg}", "url": url})
                stats["failed"] += 1
        else:
            print(f"         ✗ {msg}")
            results.append({"sample_id": sid, "company": name, "status": "failed",
                           "reason": msg, "url": url})
            stats["failed"] += 1

    # 保存日志
    log["run_time"] = datetime.now().isoformat()
    log["results"] = results
    log["stats"] = stats
    save_log(log)

    # 统计
    print()
    print("=" * 70)
    print("  下载统计")
    print("=" * 70)
    print(f"  总计:  {stats['total']} 家")
    print(f"  成功:  {stats['success']} 家")
    print(f"  已存在: {stats['skipped']} 家")
    print(f"  失败:  {stats['failed']} 家")
    print(f"  无URL: {stats['no_url']} 家")
    print()
    print(f"  日志: {LOG_FILE}")

    # 列出失败/无URL的
    missing = [r for r in results if r["status"] in ("failed", "no_url")]
    if missing:
        print()
        print("  === 待处理（需手动获取URL后重试）===")
        for r in missing:
            reason = r.get("reason", "无URL")
            print(f"  [{r['sample_id']}] {r['company']}: {reason}")

    return stats["failed"]


if __name__ == "__main__":
    sys.exit(main())
