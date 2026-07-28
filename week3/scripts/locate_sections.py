#!/usr/bin/env python3
"""
章节定位: 在PDF解析MD中定位"发行人基本情况"→"股本演变"等融资相关章节

输入: review/*.md (PyMuPDF输出)
输出: 控制台输出各公司定位到的章节范围
"""
import sys, re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import *

SECTION_KEYWORDS = [
    "发行人基本情况", "历史沿革", "股本演变", "历次增资",
    "股权转让", "股东变化", "公司设立", "发起人",
    "注册资本.*增加", "融资", "改制", "VIE", "红筹",
]


def locate(text, keywords=None):
    """在MD文本中定位融资相关章节"""
    if keywords is None:
        keywords = SECTION_KEYWORDS
    results = []
    for kw in keywords:
        for m in re.finditer(kw, text):
            start = max(0, m.start() - 300)
            end = min(len(text), m.end() + 2000)
            # 找PDF页码
            pm = re.search(r'##\s*第(\d+)页', text[:m.start()])
            page = int(pm.group(1)) if pm else 1
            results.append({
                "keyword": kw,
                "position": m.start(),
                "pdf_page": page,
                "context": text[start:end][:200]
            })
    return results


def main():
    print("=" * 60)
    print("[AUTO] locate_sections — 章节定位")
    print("=" * 60)

    for name, info in TARGET_COMPANIES.items():
        # 找对应MD文件
        md_files = list(REVIEW_DIR.glob(f"*{name}*.md"))
        if not md_files:
            md_files = list(REVIEW_DIR.glob(f"*{info['code']}*.md"))

        if not md_files:
            print(f"  {name}: ✗ MD文件不存在")
            continue

        text = ""
        for mdf in md_files[:2]:
            text += mdf.read_text(encoding="utf-8", errors="ignore") + "\n"

        locs = locate(text)
        pages = sorted(set(l["pdf_page"] for l in locs))
        print(f"  {name} ({info['code']}): {len(locs)}处匹配, PDF页码: {pages[:10]}")

    print("\n✓ 章节定位完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
