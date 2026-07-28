#!/usr/bin/env python3
"""
候选文本提取: 从定位到的章节中截取候选文本片段供后续提取使用

输入: review/*.md
输出: 控制台输出候选文本片段
"""
import sys, re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import *

SECTION_KEYWORDS = [
    "发行人基本情况", "历史沿革", "股本演变", "历次增资",
]


def extract_candidates(text, keywords=None, context_radius=3000):
    """从MD文本中提取融资相关候选文本"""
    if keywords is None:
        keywords = SECTION_KEYWORDS
    candidates = []
    for kw in keywords:
        idx = text.find(kw)
        if idx < 0:
            continue
        start = max(0, idx - 200)
        end = min(len(text), idx + context_radius)
        # 扩展到一个自然段落结束
        while end < len(text) and not text[end:end+50].strip().startswith("## 第"):
            end = min(len(text), end + 500)
        candidates.append({
            "keyword": kw,
            "position": idx,
            "text": text[start:end]
        })
    return candidates


def main():
    print("=" * 60)
    print("[AUTO] extract_candidates — 候选文本提取")
    print("=" * 60)

    for name, info in TARGET_COMPANIES.items():
        md_files = list(REVIEW_DIR.glob(f"*{name}*.md"))
        if not md_files:
            md_files = list(REVIEW_DIR.glob(f"*{info['code']}*.md"))
        if not md_files:
            print(f"  {name}: ✗ MD文件不存在")
            continue

        text = ""
        for mdf in md_files[:2]:
            text += mdf.read_text(encoding="utf-8", errors="ignore") + "\n"

        candidates = extract_candidates(text)
        if candidates:
            lengths = [len(c["text"]) for c in candidates]
            print(f"  {name}: {len(candidates)}候选片段, 长度{min(lengths)}-{max(lengths)}字")
        else:
            print(f"  {name}: ✗ 未找到候选章节")

    print("\n✓ 候选文本提取完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
