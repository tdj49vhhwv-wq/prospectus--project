#!/usr/bin/env python3
"""
==========================================================================
 01_build_company_list — 构建2025年科创板企业清单
==========================================================================
功能:
  1. 从硬编码数据构建2025年科创板19家企业清单
  2. 输出CSV到 company_lists/week2_2025_company_list.csv
  3. 支持 --market 参数扩展至其他市场 (star/gem/main/bse)
==========================================================================
"""
import csv
import argparse
from pathlib import Path
from datetime import datetime

BASE_DIR = Path("/Users/zhaobingqing/Documents/GitHub/prospectus-pevc-project")
OUTPUT_DIR = BASE_DIR / "company_lists"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 2025年科创板上市公司完整清单（19家）
# 数据来源: 上交所科创板官网 + 巨潮资讯 + 同花顺iFinD
# 更新日期: 2026-06-07
STAR_MARKET_2025 = [
    ("STAR001", "赛分科技", "苏州赛分科技股份有限公司", "688758", "上海证券交易所", "科创板", "2025-01-10", 2025),
    ("STAR002", "影石创新", "影石创新科技股份有限公司", "688775", "上海证券交易所", "科创板", "2025-06-11", 2025),
    ("STAR003", "思看科技", "思看科技（杭州）股份有限公司", "688583", "上海证券交易所", "科创板", "2025-01-15", 2025),
    ("STAR004", "兴福电子", "湖北兴福电子材料股份有限公司", "688545", "上海证券交易所", "科创板", "2025-01-22", 2025),
    ("STAR005", "海博思创", "北京海博思创科技股份有限公司", "688411", "上海证券交易所", "科创板", "2025-01-27", 2025),
    ("STAR006", "胜科纳米", "胜科纳米（苏州）股份有限公司", "688757", "上海证券交易所", "科创板", "2025-03-25", 2025),
    ("STAR007", "汉邦科技", "江苏汉邦科技股份有限公司", "688755", "上海证券交易所", "科创板", "2025-05-16", 2025),
    ("STAR008", "屹唐股份", "北京屹唐半导体科技股份有限公司", "688729", "上海证券交易所", "科创板", "2025-07-08", 2025),
    ("STAR009", "必贝特", "广州必贝特医药股份有限公司", "688759", "上海证券交易所", "科创板", "2025-10-28", 2025),
    ("STAR010", "禾元生物", "武汉禾元生物科技股份有限公司", "688765", "上海证券交易所", "科创板", "2025-10-28", 2025),
    ("STAR011", "西安奕材", "西安奕斯伟材料科技股份有限公司", "688783", "上海证券交易所", "科创板", "2025-10-28", 2025),
    ("STAR012", "恒坤新材", "厦门恒坤新材料科技股份有限公司", "688727", "上海证券交易所", "科创板", "2025-11-18", 2025),
    ("STAR013", "摩尔线程", "摩尔线程智能科技（北京）股份有限公司", "688795", "上海证券交易所", "科创板", "2025-12-05", 2025),
    ("STAR014", "百奥赛图", "百奥赛图（北京）医药科技股份有限公司", "688796", "上海证券交易所", "科创板", "2025-12-10", 2025),
    ("STAR015", "昂瑞微", "北京昂瑞微电子技术股份有限公司", "688790", "上海证券交易所", "科创板", "2025-12-16", 2025),
    ("STAR016", "沐曦股份", "沐曦集成电路（上海）股份有限公司", "688802", "上海证券交易所", "科创板", "2025-12-17", 2025),
    ("STAR017", "优迅股份", "厦门优迅芯片股份有限公司", "688807", "上海证券交易所", "科创板", "2025-12-19", 2025),
    ("STAR018", "健信超导", "宁波健信超导科技股份有限公司", "688805", "上海证券交易所", "科创板", "2025-12-24", 2025),
    ("STAR019", "强一股份", "强一半导体（苏州）股份有限公司", "688809", "上海证券交易所", "科创板", "2025-12-30", 2025),
]

CSV_HEADER = [
    "sample_id", "company_short_name", "company_full_name", "stock_code",
    "exchange", "board", "listing_date", "ipo_year",
    "source_platform", "source_page_url", "prospectus_title", "prospectus_url",
    "prospectus_version", "prospectus_date",
    "download_status", "parse_status", "locate_status", "extract_status", "review_status", "notes"
]


def build_star_market_csv(output_path=None):
    """构建科创板2025年企业清单CSV"""
    if output_path is None:
        output_path = OUTPUT_DIR / "week2_2025_company_list.csv"

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)
        for row in STAR_MARKET_2025:
            # 填充完整行: 基础信息 + 空字段(来源/下载状态等)
            full_row = list(row) + [
                "巨潮资讯",                                    # source_platform
                "https://www.cninfo.com.cn/new/index",         # source_page_url
                "", "", "", "",                                # prospectus_title/url/version/date
                "", "", "", "", "", ""                         # download/parse/locate/extract/review/notes
            ]
            writer.writerow(full_row)

    print(f"✓ 科创板2025年企业清单已生成: {output_path}")
    print(f"  共 {len(STAR_MARKET_2025)} 家公司")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="构建企业清单")
    parser.add_argument("--market", choices=["star", "gem", "main", "bse", "all"],
                        default="star", help="目标市场")
    parser.add_argument("--year", type=int, default=2025, help="上市年份")
    parser.add_argument("-o", "--output", help="输出路径")
    args = parser.parse_args()

    if args.market == "star":
        build_star_market_csv(args.output)
    else:
        print(f"市场 '{args.market}' 的清单尚未实现，请先配置数据源")
        print("当前仅支持: --market star")

    print(f"\n构建完成: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
