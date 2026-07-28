#!/usr/bin/env python3
"""
改进版：从候选文本中提取结构化融资历史JSON
"""
import re
import json
import os
from pathlib import Path
from collections import defaultdict

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import REVIEW_DIR, OUTPUTS_DIR

# 需要关注的融资事件关键词
EVENT_PATTERNS = {
    "增资": r'(?:第[一二三四五六七八九十\d]+次)?\s*增资',
    "股权转让": r'(?:第[一二三四五六七八九十\d]+次)?\s*股权转让',
    "吸收合并": r'吸收合并',
    "整体变更": r'整体变更(?:为|设立|成)\s*(?:股份有限公司|股份公司)',
    "设立": r'(?:有限公司|股份公司|股份有限公司)设立',
    "改制": r'改制',
}

COMPANY_FILES = defaultdict(list)


def group_files():
    for f in sorted(REVIEW_DIR.glob("*.md")):
        name = f.stem
        name = name.replace("MinerU_markdown_", "")
        name = re.sub(r'md$', '', name)
        company = re.sub(r'\d+$', '', name)
        if company:
            COMPANY_FILES[company].append(f)
    return COMPANY_FILES


def clean_text(text):
    """清理文本，去除图片引用和HTML标签"""
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'#+\s*', '', text)
    return text.strip()


def parse_events_from_text(text):
    """从文本中提取融资事件"""
    events = []
    seen_dates = set()

    # 按段落分割
    paragraphs = re.split(r'\n(?=\d{4}[\.年])', text)

    for para in paragraphs:
        if len(para) < 30:
            continue

        event = {"type": None, "date": None, "description": None, "amount": None, "participants": []}

        # 找事件类型
        for event_type, pattern in EVENT_PATTERNS.items():
            if re.search(pattern, para):
                event["type"] = event_type
                break

        if not event["type"]:
            continue

        # 找日期
        date_matches = re.findall(r'(\d{4})\s*年\s*(\d{1,2})\s*月', para)
        if date_matches:
            event["date"] = f"{date_matches[0][0]}-{date_matches[0][1]:0>2}"
            if event["date"] in seen_dates:
                continue
            seen_dates.add(event["date"])

        # 找金额 (注册资本)
        amount_match = re.search(r'(?:注册资本|出资额?|增资)\D*?(\d+[\d,.]*\s*万元)', para)
        if amount_match:
            event["amount"] = amount_match.group(1)

        # 找参与方
        investor_match = re.findall(r'([一-鿿]{2,10}(?:有限(?:责任)?公司|集团(?:有限)?公司|企业|合伙|创投|投资|资本))', para)
        if investor_match:
            event["participants"] = list(set(investor_match))[:8]

        # 生成描述
        event["description"] = clean_text(para)[:300]
        events.append(event)

    return events


def build_equity_timeline(text):
    """构建股权演变时间线"""
    timeline = []
    current_section = None

    lines = text.split('\n')
    for line in lines:
        # 找事件标题
        title_match = re.match(r'^#+\s*(.+)', line)
        if title_match:
            current_section = title_match.group(1).strip()
            continue

        # 找日期开头的行
        date_match = re.match(r'(\d{4})\s*[年\./]\s*(\d{1,2})\s*[月\./]?\s*(\d{1,2})?\s*[日]?\s*[,，]?\s*(.+)', line)
        if date_match and len(line) > 30:
            year, month, day, content = date_match.groups()
            timeline.append({
                "date": f"{year}-{month:0>2}",
                "section": current_section,
                "event": content.strip()[:200],
            })

    # 如果没有精确匹配，尝试找包含日期+关键词的行
    if not timeline:
        for line in lines:
            kw_match = re.search(r'(增资|股权转让|吸收合并|设立|整体变更)', line)
            date_match = re.search(r'(\d{4})\s*[年\.]\s*(\d{1,2})\s*[月]', line)
            if kw_match and date_match:
                year, month = date_match.groups()
                timeline.append({
                    "date": f"{year}-{month:0>2}",
                    "event": clean_text(line)[:200],
                })

    return timeline[:30]


def extract_shareholder_table(text):
    """提取股东表格信息"""
    shareholders = []
    # 匹配表格中的股东行
    rows = re.findall(
        r'<tr><td[^>]*>(?:(\d+)\s*)?</td><td[^>]*>([一-鿿（）()a-zA-Z]+(?:有限(?:责任)?公司|集团|企业|合伙)?)</td><td[^>]*>([\d,.]+\s*万?\w*)</td><td[^>]*>([\d.]+%?)</td>',
        text
    )
    for row in rows:
        shareholders.append({
            "rank": row[0],
            "name": row[1],
            "shares": row[2],
            "ratio": row[3],
        })
    return shareholders[:10]


def process_company(company, files):
    """处理单家公司"""
    print(f"\n处理: {company}")

    all_text = ""
    for f in sorted(files):
        with open(f, "r", encoding="utf-8") as fh:
            all_text += fh.read() + "\n\n"

    # 找章节
    boundaries = []
    for m in re.finditer(r'^# (.+)$', all_text, re.MULTILINE):
        boundaries.append((m.start(), m.group(1).strip()))

    # 定位融资章节
    FINANCING_KW = [
        "发行人基本情况", "历史沿革", "股本演变", "历次增资",
        "股权转让", "股东变化", "股东情况", "公司设立", "股本.*变化"
    ]

    target_chapters = []
    for i, (start, title) in enumerate(boundaries):
        for kw in FINANCING_KW:
            if re.search(kw, title):
                next_start = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(all_text)
                target_chapters.append({
                    "title": title,
                    "content": all_text[start:next_start].strip(),
                })
                break

    # 只保留发行人基本情况章节中最核心的内容
    core_chapters = [ch for ch in target_chapters if len(ch["content"]) > 100]

    # 提取融资事件
    all_events = []
    all_shareholders = []
    timeline = []

    for ch in core_chapters:
        events = parse_events_from_text(ch["content"])
        for e in events:
            e["source_chapter"] = ch["title"][:80]
        all_events.extend(events)

        sh = extract_shareholder_table(ch["content"])
        all_shareholders.extend(sh)

        tl = build_equity_timeline(ch["content"])
        timeline.extend(tl)

    # 去重时间线
    seen = set()
    unique_timeline = []
    for t in timeline:
        key = (t.get("date"), t.get("event", "")[:50])
        if key not in seen:
            seen.add(key)
            unique_timeline.append(t)

    # 构建输出
    output = {
        "company_name": company,
        "source_files": [f.name for f in sorted(files)],
        "financing_chapters_found": [ch["title"][:100] for ch in core_chapters],
        "equity_timeline": unique_timeline[:30],
        "financing_events": all_events[:20],
        "key_shareholders": all_shareholders[:15],
        "statistics": {
            "total_chapters_scanned": len(boundaries),
            "financing_chapters": len(core_chapters),
            "timeline_entries": len(unique_timeline),
            "financing_events_found": len(all_events),
        },
    }

    return output


def save_company_output(company, data):
    """保存公司输出"""
    company_dir = OUTPUTS_DIR / company
    company_dir.mkdir(parents=True, exist_ok=True)

    # 保存JSON
    json_path = company_dir / f"{company}_融资历史.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 保存Markdown报告
    md_path = company_dir / f"{company}_融资历史报告.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# {company} - 融资历史提取报告\n\n")

        f.write(f"## 基本信息\n\n")
        f.write(f"- 源文件: {', '.join(data['source_files'])}\n")
        f.write(f"- 扫描章节数: {data['statistics']['total_chapters_scanned']}\n")
        f.write(f"- 融资相关章节: {data['statistics']['financing_chapters']}\n")
        f.write(f"- 时间线条目: {data['statistics']['timeline_entries']}\n")
        f.write(f"- 融资事件: {data['statistics']['financing_events_found']}\n\n")

        f.write(f"## 发现的相关章节\n\n")
        for ch in data["financing_chapters_found"]:
            f.write(f"- {ch}\n")

        f.write(f"\n## 股权演变时间线\n\n")
        for t in data.get("equity_timeline", []):
            f.write(f"- **{t.get('date', '未知')}**: {t.get('event', '')}\n")

        f.write(f"\n## 融资事件\n\n")
        for i, e in enumerate(data.get("financing_events", [])):
            f.write(f"### 事件 {i+1}: {e.get('type', '未知类型')}\n\n")
            f.write(f"- 日期: {e.get('date', '未知')}\n")
            f.write(f"- 金额: {e.get('amount', '未知')}\n")
            f.write(f"- 参与方: {', '.join(e.get('participants', []))}\n")
            f.write(f"- 描述: {e.get('description', '')}\n\n")

        f.write(f"\n## 主要股东\n\n")
        for s in data.get("key_shareholders", [])[:10]:
            f.write(f"- {s.get('name', '')}: {s.get('shares', '')} ({s.get('ratio', '')})\n")

    return company_dir


def main():
    group_files()
    print(f"共 {len(COMPANY_FILES)} 家公司")

    summary = {}
    for company, files in sorted(COMPANY_FILES.items()):
        data = process_company(company, files)
        out_dir = save_company_output(company, data)
        print(f"  -> {out_dir}")

        summary[company] = data["statistics"]

    # 保存汇总
    summary_path = OUTPUTS_DIR / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n汇总已保存: {summary_path}")
    for company, stats in summary.items():
        print(f"  {company}: 融资章节={stats['financing_chapters']}, 时间线={stats['timeline_entries']}, 事件={stats['financing_events_found']}")


if __name__ == "__main__":
    main()
