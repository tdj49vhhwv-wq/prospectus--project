#!/usr/bin/env python3
"""
招股书融资历史提取脚本
步骤:
  1. 读取所有md文件，按公司归类
  2. 提取目录/章节标题
  3. 定位融资历史相关章节
  4. 截取候选文本
  5. 输出JSON
"""
import re
import json
import os
from pathlib import Path
from collections import defaultdict

import sys
from pathlib import Path

# 项目根目录：code/ 的上级
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import REVIEW_DIR, OUTPUTS_DIR, FINANCING_KEYWORDS

COMPANY_FILES = defaultdict(list)


def group_files():
    """按公司名对md文件分组"""
    for f in sorted(REVIEW_DIR.glob("*.md")):
        name = f.stem
        # 清理前缀
        name = name.replace("MinerU_markdown_", "")
        # 清理尾部的 md (如 赛分科技1md -> 赛分科技1)
        name = re.sub(r'md$', '', name)
        # 去掉末尾数字得到公司名 (如 赛分科技1 -> 赛分科技)
        company = re.sub(r'\d+$', '', name)
        if company:
            COMPANY_FILES[company].append(f)
    return COMPANY_FILES


def extract_toc(text, max_lines=200):
    """提取前max_lines行中的目录标题"""
    lines = text.split('\n')[:max_lines]
    toc_entries = []
    for line in lines:
        # 匹配目录条目: # 第四节 发行人基本情况.... 49
        m = re.match(r'^#\s+(第[一二三四五六七八九十]+节.*)', line)
        if m:
            toc_entries.append(m.group(1).strip())
        # 也匹配详细的子目录
        m2 = re.match(r'^#\s+(一、|二、|三、|四、|五、|六、).*', line)
        if m2:
            toc_entries.append(f"  {m2.group(0).strip()}")
    return toc_entries


def find_chapter_boundaries(text):
    """找到所有一级标题(# xxx)的位置"""
    boundaries = []
    for m in re.finditer(r'^# (.+)$', text, re.MULTILINE):
        boundaries.append((m.start(), m.group(1).strip(), m.end()))
    return boundaries


def locate_financing_chapters(text, boundaries):
    """定位融资历史相关章节的起止位置"""
    target_chapters = []
    for i, (start, title, end) in enumerate(boundaries):
        # 检查标题是否匹配融资关键词
        for kw in FINANCING_KEYWORDS:
            if re.search(kw, title):
                # 找到下一章的起始位置
                if i + 1 < len(boundaries):
                    next_start = boundaries[i + 1][0]
                else:
                    next_start = len(text)
                target_chapters.append({
                    "title": title,
                    "line_idx": text[:start].count('\n'),
                    "content": text[start:next_start].strip(),
                })
                break
    return target_chapters


def extract_candidate_text(chapters, min_length=200):
    """从目标章节中提取候选文本"""
    candidates = []
    for ch in chapters:
        content = ch['content']
        if len(content) >= min_length:
            candidates.append({
                "chapter": ch['title'],
                "text": content[:5000],  # 限制最大长度
            })
    return candidates


def extract_financing_json(text, company_name):
    """尝试从文本中提取融资事件结构化数据"""
    # 搜索增资/股权转让相关记录
    events = []

    # 找日期 + 金额的模式
    date_patterns = [
        r'(\d{4}\s*年\s*\d{1,2}\s*月)',
        r'(\d{4}\.\d{1,2})',
        r'(\d{4}/\d{1,2})',
    ]

    # 找金额模式
    amount_pattern = r'(\d+[\d,.]*\s*万元|\d+[\d,.]*\s*元|\d+[\d,.]*\s*美元|\d+[\d,.]*\s*万人民币)'

    # 找投资方
    investor_patterns = [
        r'(\S+(?:创投|投资|资本|基金|私募|有限合伙|有限公司))',
        r'(红杉|高瓴|IDG|经纬|深创投|达晨|同创|毅达|中金|中信|启明)',
    ]

    for date_pat in date_patterns:
        for m in re.finditer(date_pat, text):
            events.append({"date": m.group(1), "source": "date_pattern"})

    # 简化版：提取包含增资关键词的段落
    paragraphs = text.split('\n')
    for i, p in enumerate(paragraphs):
        if re.search(r'(增资|股权转让|引入.*投资|融资|注册资本.*增加)', p):
            context = '\n'.join(paragraphs[max(0, i-2):min(len(paragraphs), i+5)])
            if len(context) > 50:
                events.append({
                    "type": "financing_event",
                    "context": context[:500],
                })

    return events[:20]  # 限制数量


def build_structured_output(company, candidates):
    """构建结构化JSON输出"""
    output = {
        "company_name": company,
        "source_files": [str(f.name) for f in COMPANY_FILES[company]],
        "financing_chapters": [],
        "candidate_texts": [],
        "financing_events": [],
    }

    for ch in candidates:
        output["financing_chapters"].append(ch["chapter"])
        output["candidate_texts"].append({
            "chapter": ch["chapter"],
            "text_preview": ch["text"][:1000],
            "text_length": len(ch["text"]),
        })
        events = extract_financing_json(ch["text"], company)
        output["financing_events"].extend(events)

    return output


def save_results(company, data):
    """保存结果到公司文件夹"""
    company_dir = OUTPUTS_DIR / company
    company_dir.mkdir(parents=True, exist_ok=True)

    # 保存候选文本
    text_file = company_dir / f"{company}_候选文本.md"
    with open(text_file, "w", encoding="utf-8") as f:
        f.write(f"# {company} - 融资历史候选文本\n\n")
        for ct in data.get("candidate_texts", []):
            f.write(f"## {ct['chapter']}\n\n")
            f.write(f"```\n{ct['text_preview']}\n```\n\n")
            f.write("---\n\n")

    # 保存结构化JSON
    json_file = company_dir / f"{company}_融资历史.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 保存章节列表
    toc_file = company_dir / f"{company}_章节列表.md"
    with open(toc_file, "w", encoding="utf-8") as f:
        f.write(f"# {company} - 章节列表\n\n")
        for ch in data.get("financing_chapters", []):
            f.write(f"- {ch}\n")

    return company_dir


def process_all():
    """主处理流程"""
    group_files()
    print(f"共发现 {len(COMPANY_FILES)} 家公司")

    all_results = {}

    for company, files in sorted(COMPANY_FILES.items()):
        print(f"\n{'='*60}")
        print(f"处理: {company} ({len(files)} 个文件)")

        all_text = ""
        for f in sorted(files):
            print(f"  读取: {f.name}")
            with open(f, "r", encoding="utf-8") as fh:
                all_text += fh.read() + "\n\n"

        # 提取目录
        toc = extract_toc(all_text)
        print(f"  目录条目: {len(toc)} 条")

        # 找章节边界
        boundaries = find_chapter_boundaries(all_text)
        print(f"  一级标题: {len(boundaries)} 个")

        # 定位融资历史章节
        financing_chapters = locate_financing_chapters(all_text, boundaries)
        print(f"  融资相关章节: {len(financing_chapters)} 个")
        for ch in financing_chapters:
            print(f"    -> {ch['title'][:80]}")

        # 截取候选文本
        candidates = extract_candidate_text(financing_chapters)
        print(f"  候选文本: {len(candidates)} 段")

        # 构建输出
        data = build_structured_output(company, candidates)
        all_results[company] = data

        # 保存
        out_dir = save_results(company, data)
        print(f"  -> 已保存到: {out_dir}")

    # 汇总报告
    summary = {
        "total_companies": len(COMPANY_FILES),
        "companies": {},
    }
    for company, data in all_results.items():
        summary["companies"][company] = {
            "files": data["source_files"],
            "financing_chapter_count": len(data["financing_chapters"]),
            "event_count": len(data["financing_events"]),
        }

    summary_file = OUTPUTS_DIR / "summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"汇总报告: {summary_file}")

    # 打印汇总
    for company, info in summary["companies"].items():
        print(f"  {company}: {info['financing_chapter_count']}个相关章节, {info['event_count']}条事件")


if __name__ == "__main__":
    process_all()
