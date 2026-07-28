#!/usr/bin/env python3
"""
==========================================================================
 Week 2 批处理: PDF解析 → 章节定位 → JSON抽取
 处理2025年科创板全部19家公司的招股说明书
==========================================================================
用法:
  python3 batch_process_week2.py              # 完整流程
  python3 batch_process_week2.py --step 4     # 仅PDF解析
  python3 batch_process_week2.py --step 5     # 仅章节定位+JSON抽取
  python3 batch_process_week2.py --dry-run    # 预览不执行
==========================================================================
"""

import sys
import os
import re
import json
import time
import csv
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# 项目路径 - 通过 config 模块统一管理
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import PROJECT_ROOT, REVIEW_DIR, OUTPUTS_DIR, LOG_DIR, PDF_DIR

# PDF_DIR 可能指向 data/prospectus_pdfs，但 week2 使用 week2PDF 目录
PDF_DIR = PROJECT_ROOT / "week2PDF" if (PROJECT_ROOT / "week2PDF").exists() else PDF_DIR

LOG_DIR.mkdir(parents=True, exist_ok=True)
REVIEW_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = LOG_DIR / f"batch_week2_{RUN_ID}.log"
STEP_LOG_CSV = LOG_DIR / f"batch_step_log_{RUN_ID}.csv"

_step_log_rows = []


def record_step(step_name, status, detail=""):
    """记录步骤执行状态到 step_log.csv"""
    _step_log_rows.append({
        "timestamp": datetime.now().isoformat(),
        "step": step_name,
        "status": status,
        "detail": detail,
    })
    with open(STEP_LOG_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["timestamp", "step", "status", "detail"])
        w.writeheader()
        w.writerows(_step_log_rows)


def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ============================================================
# Step 4: PDF → Markdown (PyMuPDF)
# ============================================================
def parse_pdf_with_pymupdf(pdf_path, output_path):
    """使用PyMuPDF将PDF解析为Markdown文本"""
    import fitz
    doc = fitz.open(str(pdf_path))
    total_pages = doc.page_count

    lines = []
    lines.append(f"# {pdf_path.stem}\n")
    lines.append(f"> 源文件: {pdf_path.name} | 总页数: {total_pages}\n")

    for page_num in range(total_pages):
        page = doc[page_num]
        text = page.get_text()
        if text.strip():
            lines.append(f"\n## 第{page_num + 1}页\n")
            lines.append(text)

        if (page_num + 1) % 50 == 0:
            log(f"    解析进度: {page_num+1}/{total_pages} 页")

    doc.close()

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return total_pages


def step4_parse_pdfs():
    """Step 4: 批量解析PDF为Markdown"""
    step_name = "Step4_parse_pdfs"
    log("=" * 60)
    log("Step 4: PDF解析 → Markdown (PyMuPDF)")
    log("=" * 60)
    record_step(step_name, "START")

    pdf_files = sorted(PDF_DIR.glob("*.pdf"))
    # 排除非招股书的文件
    pdf_files = [f for f in pdf_files if f.stem.startswith("688")]
    log(f"发现 {len(pdf_files)} 个招股书PDF")

    stats = {"total": len(pdf_files), "success": 0, "failed": 0, "skipped": 0, "details": []}

    for i, pdf_path in enumerate(pdf_files, 1):
        name = pdf_path.stem
        output_path = REVIEW_DIR / f"{name}.md"

        log(f"\n[{i}/{len(pdf_files)}] {name}")

        if output_path.exists():
            size_kb = output_path.stat().st_size / 1024
            log(f"  ⊙ 已存在 ({size_kb:.0f} KB)，跳过")
            stats["skipped"] += 1
            stats["details"].append({"file": name, "status": "skipped"})
            continue

        try:
            log(f"  → 开始解析...")
            t0 = time.time()
            pages = parse_pdf_with_pymupdf(pdf_path, output_path)
            elapsed = time.time() - t0
            size_kb = output_path.stat().st_size / 1024
            log(f"  ✓ 成功: {pages}页, {size_kb:.0f} KB, 耗时 {elapsed:.0f}s")
            stats["success"] += 1
            stats["details"].append({
                "file": name, "status": "success",
                "pages": pages, "size_kb": round(size_kb, 1), "time_s": round(elapsed, 1)
            })
        except Exception as e:
            log(f"  ✗ 失败: {e}")
            stats["failed"] += 1
            stats["details"].append({"file": name, "status": "failed", "error": str(e)})

    # 保存步骤记录
    with open(LOG_DIR / f"step4_parse_{RUN_ID}.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    log(f"\nStep 4 完成: 成功={stats['success']}, 跳过={stats['skipped']}, 失败={stats['failed']}")
    record_step("Step4_parse_pdfs", "DONE",
                f"success={stats['success']}, skipped={stats['skipped']}, failed={stats['failed']}")
    return stats


# ============================================================
# Step 5+6: 章节定位 + JSON抽取
# ============================================================

# 融资历史相关章节关键词
FINANCING_KEYWORDS = [
    "发行人基本情况", "历史沿革", "股本演变", "历次增资",
    "股权转让", "股东变化", "股东情况", "公司设立", "发起人",
    "股本.*变化", "改制", "有限公司阶段", "股份公司阶段",
    "红筹架构", "VIE", "拆除", "搭建",
]


def group_files_by_company():
    """按公司代码/简称对review/*.md文件分组"""
    companies = defaultdict(list)
    for f in sorted(REVIEW_DIR.glob("*.md")):
        name = f.stem
        # 匹配 688xxx_公司名_招股书_正式稿_日期 格式
        m = re.match(r'(688\d{3})_(.+?)_招股书', name)
        if m:
            company_key = f"{m.group(1)}_{m.group(2)}"
        else:
            # 尝试直接提取公司名
            company_key = re.sub(r'\d+$', '', name).strip('_')
            if not company_key:
                continue
        companies[company_key].append(f)

    # 合并同一公司多个文件
    return companies


def find_chapter_boundaries(text):
    """找到所有章节/一级标题位置（兼容PyMuPDF输出和markdown heading）"""
    boundaries = []

    # 1. 尝试 markdown heading: ^# 标题
    for m in re.finditer(r'^# (.+)$', text, re.MULTILINE):
        boundaries.append((m.start(), m.group(1).strip()))

    # 2. 如果markdown heading很少（PyMuPDF输出），从文本中搜索中文章节标题
    #    匹配模式: 第X节 标题 或 第X章 标题
    if len(boundaries) <= 2:
        boundaries = []  # 重置，用文本级搜索
        for m in re.finditer(
            r'(?:^|\n)\s*(第[一二三四五六七八九十百\d]+[节章]\s*[^\n]{0,80})',
            text
        ):
            start = m.start()
            title = m.group(1).strip()
            boundaries.append((start, title))

        # 如果还是没有，降级到 ## 第N页 作为分割
        if not boundaries:
            for m in re.finditer(r'^## 第(\d+)页$', text, re.MULTILINE):
                boundaries.append((m.start(), m.group(0).strip()))

    return boundaries


def locate_financing_chapters(text, boundaries):
    """定位融资历史相关章节（适配PyMuPDF输出）"""
    target = []

    for i, (start, title) in enumerate(boundaries):
        matched = False
        for kw in FINANCING_KEYWORDS:
            if re.search(kw, title):
                matched = True
                break

        if matched:
            next_start = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(text)
            content = text[start:next_start].strip()
            if len(content) > 100:
                target.append({
                    "title": title,
                    "line_idx": text[:start].count('\n'),
                    "content": content,
                    "length": len(content),
                })

    # 如果没有匹配到章节，采用全文关键词精确定位策略
    if not target:
        target = _locate_by_keyword_search(text)

    return target


def _locate_by_keyword_search(text):
    """全文关键词搜索定位融资章节（PyMuPDF降级方案）"""
    target = []

    # 搜索"发行人基本情况"所在的区域
    core_patterns = [
        r'第[四4][节章][^\n]{0,30}发行人基本情况',
        r'发行人基本情况',
        r'股本演变|历次增资|历史沿革',
    ]

    for pattern in core_patterns:
        for m in re.finditer(pattern, text):
            idx = m.start()
            # 从找到位置向前后各扩展10000字符，覆盖完整章节
            start = max(0, idx - 500)
            end = min(len(text), idx + 15000)
            # 展开到最近的章节边界
            next_section = re.search(
                r'第[五六七八九十百\d]+[节章]',
                text[idx:idx + 20000]
            )
            if next_section:
                end = min(end, idx + next_section.start())

            prev_section = list(re.finditer(
                r'第[一二三四五六七八九十百\d]+[节章]',
                text[max(0, idx - 5000):idx]
            ))
            if prev_section:
                start = max(0, idx - 5000 + prev_section[-1].start())

            content = text[start:end].strip()
            if len(content) > 200:
                target.append({
                    "title": f"全文定位: {m.group(0)[:60]}",
                    "line_idx": text[:start].count('\n'),
                    "content": content,
                    "length": len(content),
                })
            break
        if target:
            break

    return target


def extract_financing_events(chapter_text):
    """从章节文本提取融资事件（优化PyMuPDF兼容性）"""
    events = []
    seen_dates = set()

    # 清理文本中的行内换行
    cleaned = re.sub(r'(?<!\n)\n(?!\n)', '', chapter_text)

    # 策略1: 按年份+关键词分段
    segments = re.split(r'(?=\d{4}\s*[年\.])', cleaned)

    # 策略2: 如果分段太少，按"第X次"分段
    if len(segments) < 3:
        segments = re.split(r'(?=(?:\d{4}\s*[年\.]|(?:第[一二三四五六七八九十\d]+次)))', cleaned)

    for para in segments:
        if len(para) < 30:
            continue

        # 检测事件类型
        event_type = None
        if re.search(r'增资', para):
            event_type = "增资"
        elif re.search(r'股权转让|股份转让', para):
            event_type = "股权转让"
        elif re.search(r'整体变更|变更为.*股份', para):
            event_type = "整体变更"
        elif re.search(r'吸收合并', para):
            event_type = "吸收合并"
        elif re.search(r'(?:有限公司|股份公司|有限责任公司)\s*设立', para):
            event_type = "设立"
        elif re.search(r'改制', para):
            event_type = "改制"
        else:
            continue

        # 提取日期
        date_str = None
        date_matches = re.findall(r'(\d{4})\s*年\s*(\d{1,2})\s*月', para)
        if date_matches:
            date_str = f"{date_matches[0][0]}-{date_matches[0][1]:0>2}"
            if date_str in seen_dates:
                continue
            seen_dates.add(date_str)

        # 提取金额（多种模式）
        amount = None
        amt_patterns = [
            r'(?:注册资本|出资额?|增资[金额]?|投资额?|估值).{0,10}?(\d+[\d,.]*\s*万?\s*(?:元|人民币|美元|港元))',
            r'(\d+[\d,.]+\s*万?\s*(?:元|人民币))',
        ]
        for pat in amt_patterns:
            amt_match = re.search(pat, para)
            if amt_match:
                amount = amt_match.group(1)
                break

        # 提取参与方
        participants = []
        investor_pattern = re.findall(
            r'([一-鿿\w]{2,20}(?:有限(?:责任)?公司|集团(?:有限)?公司|企业|合伙|创投|投资|资本|基金|管理|控股))',
            para
        )
        if investor_pattern:
            participants = list(set(investor_pattern))[:10]

        events.append({
            "event_type": event_type,
            "date": date_str,
            "amount": amount,
            "participants": participants,
            "description": para.strip()[:500],
        })

    return events[:30]


def extract_equity_timeline(chapter_text):
    """提取股权演变时间线"""
    timeline = []
    seen = set()

    lines = chapter_text.split('\n')
    for line in lines:
        # 匹配 2025年1月 或 2025.01 开头的事件行
        m = re.match(
            r'(\d{4})\s*[年\./]\s*(\d{1,2})\s*[月\./]?\s*(\d{1,2})?\s*[日]?\s*[,，]?\s*(.+)',
            line
        )
        if m and len(line) > 30:
            year, month, day, desc = m.groups()
            key = f"{year}-{month:0>2}"
            if key not in seen:
                seen.add(key)
                timeline.append({"date": key, "event": desc.strip()[:300]})
                continue

        # 宽松匹配: 行中有日期和融资关键词
        kw_match = re.search(r'(增资|股权转让|吸收合并|整体变更|设立|改制|注册资本|股东)', line)
        date_match = re.search(r'(\d{4})\s*[年\.]\s*(\d{1,2})\s*[月]', line)
        if kw_match and date_match and len(line) > 20:
            year, month = date_match.groups()
            key = f"{year}-{month:0>2}"
            if key not in seen:
                seen.add(key)
                timeline.append({"date": key, "event": line.strip()[:300]})

    return timeline[:40]


def step5_extract(company_key, files):
    """Step 5+6: 对单家公司执行章节定位和JSON抽取"""
    log(f"\n{'─'*50}")
    log(f"处理: {company_key} ({len(files)} 个文件)")

    # 合并所有文件内容
    all_text = ""
    for f in sorted(files):
        log(f"  读取: {f.name}")
        with open(f, "r", encoding="utf-8") as fh:
            all_text += fh.read() + "\n\n"

    # 找章节边界
    boundaries = find_chapter_boundaries(all_text)
    log(f"  一级标题: {len(boundaries)} 个")

    # 列出所有章节标题（供调试）
    for _, title in boundaries[:30]:
        log(f"    § {title[:100]}")

    # 定位融资相关章节
    financing_chapters = locate_financing_chapters(all_text, boundaries)
    log(f"  融资相关章节: {len(financing_chapters)} 个")

    if not financing_chapters:
        log(f"  ⚠️ 未找到融资相关章节! 尝试全文搜索关键词...")
        # 降级: 全文搜索
        for kw in ["股本演变", "历次增资", "历史沿革", "股权转让", "增资"]:
            idx = all_text.find(kw)
            if idx >= 0:
                snippet = all_text[max(0, idx-200):min(len(all_text), idx+2000)]
                financing_chapters.append({
                    "title": f"全文搜索: {kw}",
                    "line_idx": all_text[:idx].count('\n'),
                    "content": snippet,
                    "length": len(snippet),
                })
                line_num = all_text[:idx].count(chr(10))
                log(f"    找到关键词 '{kw}' 在行 {line_num}")
                break

    for ch in financing_chapters:
        log(f"    → {ch['title'][:80]} ({ch['length']:,} 字)")

    # 提取融资事件和股权时间线
    all_events = []
    all_timeline = []
    for ch in financing_chapters:
        events = extract_financing_events(ch["content"])
        for e in events:
            e["source_chapter"] = ch["title"][:80]
        all_events.extend(events)

        tl = extract_equity_timeline(ch["content"])
        all_timeline.extend(tl)

    # 去重时间线
    seen = set()
    unique_timeline = []
    for t in all_timeline:
        k = (t.get("date"), t.get("event", "")[:60])
        if k not in seen:
            seen.add(k)
            unique_timeline.append(t)

    # 构建输出
    output = {
        "company": company_key,
        "source_files": [f.name for f in sorted(files)],
        "extraction_time": datetime.now().isoformat(),
        "statistics": {
            "total_chapters": len(boundaries),
            "financing_chapters_found": len(financing_chapters),
            "timeline_entries": len(unique_timeline),
            "financing_events": len(all_events),
        },
        "financing_chapters": [ch["title"][:120] for ch in financing_chapters],
        "equity_timeline": unique_timeline[:30],
        "financing_events": all_events[:25],
    }

    return output


def save_company_output(company_key, data):
    """保存公司级别的输出"""
    company_dir = OUTPUTS_DIR / company_key
    company_dir.mkdir(parents=True, exist_ok=True)

    # JSON
    json_path = company_dir / f"{company_key}_融资历史.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Markdown报告
    md_path = company_dir / f"{company_key}_融资历史报告.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# {company_key} - 融资历史提取报告\n\n")
        f.write(f"> 提取时间: {data['extraction_time']}\n\n")

        s = data["statistics"]
        f.write(f"## 统计\n\n")
        f.write(f"- 总章节数: {s['total_chapters']}\n")
        f.write(f"- 融资相关章节: {s['financing_chapters_found']}\n")
        f.write(f"- 时间线条目: {s['timeline_entries']}\n")
        f.write(f"- 融资事件: {s['financing_events']}\n\n")

        f.write(f"## 发现的相关章节\n\n")
        for ch in data.get("financing_chapters", []):
            f.write(f"- {ch}\n")

        f.write(f"\n## 股权演变时间线\n\n")
        for t in data.get("equity_timeline", []):
            f.write(f"- **{t.get('date', '?')}**: {t.get('event', '')}\n")

        f.write(f"\n## 融资事件\n\n")
        for i, e in enumerate(data.get("financing_events", []), 1):
            f.write(f"### 事件 {i}: {e.get('event_type', '?')}\n\n")
            f.write(f"- 日期: {e.get('date', '未知')}\n")
            f.write(f"- 金额: {e.get('amount', '未知')}\n")
            f.write(f"- 参与方: {', '.join(e.get('participants', []))}\n")
            f.write(f"- 来源章节: {e.get('source_chapter', '')}\n")
            f.write(f"- 描述: {e.get('description', '')[:200]}...\n\n")

    return company_dir


def step5_and_6_process_all():
    """Step 5+6: 批量章节定位和JSON抽取"""
    step_name = "Step5_6_extract"
    log("=" * 60)
    log("Step 5+6: 章节定位 + JSON抽取")
    log("=" * 60)
    record_step(step_name, "START")

    companies = group_files_by_company()
    log(f"从review/中发现 {len(companies)} 家公司/文件组")

    summary = {}
    for company_key, files in sorted(companies.items()):
        try:
            data = step5_extract(company_key, files)
            out_dir = save_company_output(company_key, data)
            log(f"  ✓ 已保存: {out_dir}")

            summary[company_key] = data["statistics"]
        except Exception as e:
            log(f"  ✗ 处理失败 {company_key}: {e}")
            import traceback
            log(traceback.format_exc())

    # 汇总报告
    summary_path = OUTPUTS_DIR / f"week2_summary_{RUN_ID}.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    log(f"\n{'='*60}")
    log(f"Step 5+6 汇总 ({len(summary)} 家公司)")
    log(f"{'='*60}")
    for company_key, stats in sorted(summary.items()):
        log(f"  {company_key:30s} | 融资章节={stats['financing_chapters_found']:2d} | 时间线={stats['timeline_entries']:3d} | 事件={stats['financing_events']:3d}")

    log(f"\n汇总JSON: {summary_path}")

    record_step("Step5_6_extract", "DONE", f"companies={len(summary)}")
    return summary


# ============================================================
# Main
# ============================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Week 2 批处理")
    parser.add_argument("--step", type=int, choices=[4, 5], help="仅执行指定步骤")
    parser.add_argument("--dry-run", action="store_true", help="预览不执行")
    args = parser.parse_args()

    log("╔══════════════════════════════════════════╗")
    log("║  Week 2 批处理: PDF→MD→章节→JSON        ║")
    log(f"║  Run ID: {RUN_ID}              ║")
    log("╚══════════════════════════════════════════╝")
    log(f"PDF目录: {PDF_DIR}")
    log(f"输出目录: {REVIEW_DIR}")
    log(f"结果目录: {OUTPUTS_DIR}")

    if args.dry_run:
        pdf_files = sorted(PDF_DIR.glob("688*.pdf"))
        log(f"\n[Dry Run] 发现 {len(pdf_files)} 个PDF:")
        for f in pdf_files:
            md_path = REVIEW_DIR / f"{f.stem}.md"
            status = "已存在" if md_path.exists() else "待处理"
            log(f"  {f.name} → {status}")
        return

    if args.step == 4 or args.step is None:
        step4_parse_pdfs()

    if args.step == 5 or args.step is None:
        step5_and_6_process_all()

    log(f"\n✅ 批处理完成！日志: {LOG_FILE}")


if __name__ == "__main__":
    main()
