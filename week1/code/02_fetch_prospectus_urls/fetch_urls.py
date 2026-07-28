#!/usr/bin/env python3
"""
==========================================================================
 02_fetch_prospectus_urls — 从巨潮资讯搜索招股说明书URL
==========================================================================
功能:
  1. 读取企业清单CSV，对prospectus_url为空的行搜索巨潮资讯
  2. 通过巨潮资讯搜索API获取招股说明书PDF链接
  3. 更新CSV中的prospectus_title, prospectus_url, prospectus_version, prospectus_date
  4. 支持手动指定URL（通过--manual参数）
==========================================================================
"""
import csv
import json
import time
import argparse
import urllib.request
import urllib.parse
import ssl
import re
from pathlib import Path
from datetime import datetime

BASE_DIR = Path("/Users/zhaobingqing/Documents/GitHub/prospectus-pevc-project")
CSV_INPUT = BASE_DIR / "company_lists" / "week2_2025_company_list.csv"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 巨潮资讯搜索配置
CNINFO_SEARCH_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_BASE = "https://www.cninfo.com.cn"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.cninfo.com.cn/new/index",
    "X-Requested-With": "XMLHttpRequest",
}

# 版本优先级关键词（从高到低）
VERSION_KEYWORDS = [
    ("申报稿", "申报稿"),
    ("上会稿", "上会稿"),
    ("注册稿", "注册稿"),
    ("招股说明书", "正式稿"),  # 无特殊标注即正式稿
]


def search_cninfo(stock_code, company_name, max_retries=3):
    """
    在巨潮资讯搜索招股说明书
    返回: list[dict] 搜索结果
    """
    # 构造搜索参数
    params = {
        "pageNum": 1,
        "pageSize": 30,
        "column": "szse",  # 深交所板块
        "tabName": "fulltext",
        "plate": "",
        "stock": f"{stock_code},{company_name}",
        "searchkey": "",
        "secid": "",
        "category": "category_ndbg_szsh;",  # 招股说明书类别
        "trade": "",
        "seDate": "2024-01-01~2025-12-31",  # 时间范围
        "sortName": "declaredate",
        "sortType": "desc",
    }

    for attempt in range(max_retries):
        try:
            data = urllib.parse.urlencode(params).encode("utf-8")
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            req = urllib.request.Request(
                CNINFO_SEARCH_URL, data=data, headers=HEADERS, method="POST"
            )
            with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result.get("announcements", []) or result.get("data", [])
        except Exception as e:
            print(f"  [尝试 {attempt+1}/{max_retries}] 搜索失败: {e}")
            time.sleep(2)
    return []


def extract_prospectus_info(announcements):
    """
    从搜索结果中提取招股说明书信息
    按版本优先级选择最佳结果
    """
    prospectuses = []

    for ann in announcements:
        title = ann.get("announcementTitle", "")
        # 必须是招股说明书相关
        if not re.search(r"招股(?:意向)?书", title):
            continue
        # 排除非目标文件
        if re.search(r"(摘要|问询|回复|上市公告|发行公告|法律意见)", title):
            continue

        pdf_url = ann.get("adjunctUrl", "")
        if pdf_url and not pdf_url.startswith("http"):
            pdf_url = "https://static.cninfo.com.cn/" + pdf_url.lstrip("/")

        date_str = ann.get("announcementDate", "")
        date_str = date_str[:10] if date_str else ""  # YYYY-MM-DD

        # 判断版本
        version = "正式稿"
        for kw, label in VERSION_KEYWORDS:
            if kw in title:
                version = label
                break

        prospectuses.append({
            "title": title,
            "url": pdf_url,
            "version": version,
            "date": date_str,
            "priority": VERSION_KEYWORDS.index(
                next((v for k, v in VERSION_KEYWORDS if k in title), ("招股说明书", "正式稿"))
            ) if any(k in title for k, _ in VERSION_KEYWORDS) else 3,
        })

    # 按版本优先级排序（申报稿 > 上会稿 > 注册稿 > 正式稿）
    prospectuses.sort(key=lambda x: x["priority"])
    return prospectuses


def update_csv(input_path, output_path=None):
    """读取CSV，补充缺失的prospectus_url"""
    if output_path is None:
        output_path = input_path

    rows = []
    with open(input_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(row)

    updated = 0
    for row in rows:
        # 跳过已有URL的行
        if row.get("prospectus_url", "").strip():
            continue

        stock_code = row.get("stock_code", "")
        company_name = row.get("company_full_name", "")
        sample_id = row.get("sample_id", "")

        print(f"\n[{sample_id}] {company_name} ({stock_code})")

        # 搜索巨潮资讯
        announcements = search_cninfo(stock_code, company_name)
        if not announcements:
            # 用简称再试一次
            announcements = search_cninfo(
                stock_code, row.get("company_short_name", "")
            )

        if announcements:
            prospects = extract_prospectus_info(announcements)
            if prospects:
                best = prospects[0]
                row["prospectus_title"] = best["title"]
                row["prospectus_url"] = best["url"]
                row["prospectus_version"] = best["version"]
                row["prospectus_date"] = best["date"].replace("-", "/")
                print(f"  ✓ {best['version']}: {best['title'][:60]}...")
                print(f"    URL: {best['url'][:80]}...")
                updated += 1
            else:
                print(f"  ⚠ 未找到符合条件的招股说明书")
        else:
            print(f"  ✗ 搜索无结果")
        time.sleep(2)  # 礼貌延迟

    # 写回CSV
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n{'='*50}")
    print(f"更新完成: {updated}/{len(rows)} 条记录补充了URL")
    print(f"输出: {output_path}")
    return updated


def manual_fill_sample(output_path):
    """
    手动填充已确认的招股书URL（Week 1已验证的样本）
    避免重复搜索已成功下载的URL
    """
    manual_urls = {
        "STAR001": {
            "prospectus_title": "苏州赛分科技股份有限公司首次公开发行股票并在科创板上市招股说明书",
            "prospectus_url": "https://static.cninfo.com.cn/finalpage/2025-01-06/1222238930.PDF",
            "prospectus_version": "正式稿",
            "prospectus_date": "2025/01/06",
        },
        "STAR002": {
            "prospectus_title": "影石创新科技股份有限公司首次公开发行股票并在科创板上市招股说明书",
            "prospectus_url": "https://static.cninfo.com.cn/finalpage/2025-06-06/1223788474.PDF",
            "prospectus_version": "正式稿",
            "prospectus_date": "2025/06/06",
        },
    }

    rows = []
    with open(output_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(row)

    filled = 0
    for row in rows:
        sid = row.get("sample_id", "")
        if sid in manual_urls and not row.get("prospectus_url", "").strip():
            info = manual_urls[sid]
            row["prospectus_title"] = info["prospectus_title"]
            row["prospectus_url"] = info["prospectus_url"]
            row["prospectus_version"] = info["prospectus_version"]
            row["prospectus_date"] = info["prospectus_date"]
            filled += 1
            print(f"  [{sid}] 手动填充URL: {info['prospectus_title'][:50]}...")

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return filled


def main():
    parser = argparse.ArgumentParser(description="获取招股说明书URL")
    parser.add_argument("--input", default=str(CSV_INPUT), help="输入CSV路径")
    parser.add_argument("--output", help="输出CSV路径（默认覆盖输入）")
    parser.add_argument("--manual", action="store_true", help="仅手动填充已知URL")
    parser.add_argument("--search", action="store_true", help="通过巨潮API搜索URL")
    parser.add_argument("--sample-id", help="仅处理指定sample_id")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else input_path

    print(f"输入: {input_path}")
    print(f"输出: {output_path}")

    if args.manual:
        n = manual_fill_sample(input_path)
        print(f"\n手动填充: {n} 条")

    if args.search:
        n = update_csv(input_path, output_path)
        print(f"\n搜索更新: {n} 条")

    if not args.manual and not args.search:
        print("请指定 --manual 和/或 --search")
        print("示例:")
        print("  python3 fetch_urls.py --manual              # 仅填充已知URL")
        print("  python3 fetch_urls.py --search              # 通过巨潮API搜索")
        print("  python3 fetch_urls.py --manual --search     # 两者都做")


if __name__ == "__main__":
    main()
