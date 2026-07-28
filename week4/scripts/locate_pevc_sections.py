#!/usr/bin/env python3
"""
Step 1: PE/VC 章节定位（代码定位 + 关键词截取，两步独立）

核心思路（来自闫老师建议）：
  - Step 1a: 用代码定位章节页码范围（不要全量投喂LLM）
  - Step 1b: 在定位到的章节内，用关键词截取PE/VC相关段落
  - 输出: 每个PE/VC候选片段的精确PDF页码 + 文本内容

方法: PyMuPDF 逐页扫描 → 章节标题匹配 → PE/VC关键词匹配 → 上下文扩展

输入: PDF文件
输出: week4/outputs/located_sections.json (章节范围 + PE/VC候选片段)
"""
import json
import re
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import *

try:
    import fitz
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False


def log_step(step_name, status, detail="", step_log_path=None):
    """记录每一步到 step_log.csv"""
    if step_log_path is None:
        step_log_path = STEP_LOG
    entry = {
        "timestamp": datetime.now().isoformat(),
        "step": step_name,
        "status": status,  # success / failed / warning
        "detail": detail,
    }
    with open(step_log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    symbol = {"success": "✓", "failed": "✗", "warning": "⚠"}
    print(f"  {symbol.get(status, '?')} {step_name}: {detail}")


def locate_chapters_by_toc(doc):
    """
    Step 1a: 通过目录/章节标题定位PE/VC相关章节的页码范围

    策略:
      1. 先扫描PDF全文，匹配章节标题关键词
      2. 对每个匹配位置，向前后扩展找到章节边界
      3. 返回每个目标章节的页码范围
    """
    chapters = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")

        for kw in SECTION_KEYWORDS["chapter"]:
            if kw in text:
                # 找到匹配位置的行上下文
                lines = text.split("\n")
                for i, line in enumerate(lines):
                    if kw in line:
                        ctx_start = max(0, i - 1)
                        ctx_end = min(len(lines), i + 3)
                        context = "\n".join(lines[ctx_start:ctx_end])

                        chapters.append({
                            "keyword": kw,
                            "page": page_num + 1,
                            "line_context": context.strip()[:200],
                            "match_line": line.strip()[:100],
                        })
                        break  # 每页每个关键词只匹配一次

    # 去重同页同关键词
    seen = set()
    unique = []
    for ch in chapters:
        key = (ch["keyword"], ch["page"])
        if key not in seen:
            seen.add(key)
            unique.append(ch)

    # 按页码排序
    unique.sort(key=lambda x: x["page"])
    return unique


def extract_pevc_snippets(doc, chapter_locations):
    """
    Step 1b: 在已定位章节范围内，用PE/VC内容关键词截取候选片段

    每个候选片段包含:
      - PDF页码
      - 匹配关键词
      - 上下文文本（前后各300字）
      - 所在章节
    """
    snippets = []

    # 构建章节页码范围映射
    chapter_pages = {}
    for loc in chapter_locations:
        chapter_pages.setdefault(loc["keyword"], []).append(loc["page"])

    # 确定需要扫描的页码范围（所有章节相关页 + 相邻页）
    pages_to_scan = set()
    for loc in chapter_locations:
        for dp in range(-2, 5):  # 前后扩展
            p = loc["page"] + dp
            if 0 <= p < len(doc):
                pages_to_scan.add(p)

    for page_num in sorted(pages_to_scan):
        page = doc[page_num]
        text = page.get_text("text")

        # 判断当前页属于哪个章节
        current_chapter = "未知"
        for kw, pages in chapter_pages.items():
            if page_num + 1 in pages or any(abs(page_num + 1 - p) <= 1 for p in pages):
                current_chapter = kw
                break

        for kw in SECTION_KEYWORDS["pevc_content"]:
            if kw not in text:
                continue

            # 找到所有匹配位置
            for m in re.finditer(re.escape(kw), text):
                start = max(0, m.start() - 300)
                end = min(len(text), m.end() + 500)
                snippet_text = text[start:end].strip()

                # 截取完整行
                lines = text[:m.start()].count("\n")
                snippet_lines = snippet_text.count("\n")

                snippets.append({
                    "pdf_page": page_num + 1,
                    "keyword": kw,
                    "chapter": current_chapter,
                    "char_position": m.start(),
                    "context_chars_before": 300,
                    "context_chars_after": 500,
                    "text": snippet_text,
                })

    # 按页码+位置排序
    snippets.sort(key=lambda x: (x["pdf_page"], x["char_position"]))

    # 合并重叠片段
    merged = _merge_overlapping_snippets(snippets)

    return merged


def _merge_overlapping_snippets(snippets):
    """合并同页重叠的候选片段"""
    if not snippets:
        return []

    merged = []
    current = None

    for s in snippets:
        if current is None:
            current = s.copy()
            continue

        if s["pdf_page"] == current["pdf_page"]:
            # 同页，检查是否重叠
            overlap_threshold = 200  # 字符重叠阈值
            s_start = s["char_position"] - s["context_chars_before"]
            c_start = current["char_position"] - current["context_chars_before"]
            s_end = s["char_position"] + s["context_chars_after"]
            c_end = current["char_position"] + current["context_chars_after"]

            if s_start <= c_end + overlap_threshold:
                # 重叠，合并关键词和扩展范围
                current["keyword"] = current["keyword"] + " / " + s["keyword"]
                current["context_chars_after"] = max(
                    current["context_chars_after"],
                    s["char_position"] + s["context_chars_after"] - current["char_position"]
                )
                continue

        merged.append(current)
        current = s.copy()

    if current:
        merged.append(current)

    # 清理 char_position（内部使用，不输出）
    for m in merged:
        del m["char_position"]
        del m["context_chars_before"]
        del m["context_chars_after"]

    return merged


def main():
    pdf_path = PDF_DIR / TARGET["pdf"]

    print("=" * 60)
    print(f"[Step 1] PE/VC 章节定位: {TARGET['name']} ({TARGET['code']})")
    print(f"  PDF: {pdf_path}")
    print("=" * 60)

    # 初始化 step_log
    STEP_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(STEP_LOG, "w", encoding="utf-8") as f:
        f.write("timestamp,step,status,detail\n")

    if not HAS_FITZ:
        log_step("locate_chapters", "failed", "PyMuPDF未安装: pip install PyMuPDF")
        return 1

    if not pdf_path.exists():
        log_step("locate_chapters", "failed", f"PDF不存在: {pdf_path}")
        return 1

    # ── Step 1a: 章节定位 ──
    doc = fitz.open(str(pdf_path))
    chapters = locate_chapters_by_toc(doc)

    if not chapters:
        log_step("locate_chapters", "warning", "未匹配到章节标题，使用全文扫描")
        # 兜底：扫描前50页（招股书核心章节通常在前50页）
        chapters = [{"keyword": "全文扫描(兜底)", "page": p, "line_context": ""}
                     for p in range(1, min(51, len(doc) + 1))]

    chapter_summary = {}
    for ch in chapters:
        chapter_summary.setdefault(ch["keyword"], []).append(ch["page"])

    print(f"\n  章节定位结果:")
    for kw, pages in chapter_summary.items():
        page_range = f"p{pages[0]}-p{pages[-1]}" if len(pages) > 1 else f"p{pages[0]}"
        print(f"    {kw}: {page_range} ({len(pages)}处)")

    log_step("locate_chapters", "success",
             f"匹配{len(chapters)}处，覆盖{len(chapter_summary)}个章节")

    # ── Step 1b: PE/VC 候选片段截取 ──
    snippets = extract_pevc_snippets(doc, chapters)
    doc.close()

    if not snippets:
        log_step("extract_snippets", "warning", "未截取到PE/VC候选片段")
        snippets = []
    else:
        log_step("extract_snippets", "success",
                 f"截取{len(snippets)}个候选片段, 覆盖{len(set(s['pdf_page'] for s in snippets))}页")

    # ── 输出: located_sections.json ──
    output = {
        "schema_version": "4.0",
        "generated_at": datetime.now().isoformat(),
        "company": {
            "name": TARGET["full_name"],
            "code": TARGET["code"],
            "pdf": TARGET["pdf"],
        },
        "chapters": [
            {
                "keyword": kw,
                "pages": pages,
                "page_range": f"PDF p{pages[0]}-p{pages[-1]}" if len(pages) > 1 else f"PDF p{pages[0]}",
            }
            for kw, pages in chapter_summary.items()
        ],
        "pevc_snippets": snippets,
        "statistics": {
            "total_chapter_matches": len(chapters),
            "total_snippets": len(snippets),
            "covered_pages": sorted(set(s["pdf_page"] for s in snippets)),
        },
    }

    output_path = OUTPUTS_DIR / "located_sections.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✓ 输出: {output_path}")
    print(f"  章节数: {len(chapter_summary)}")
    print(f"  候选片段: {len(snippets)}")
    print(f"  覆盖页码: {output['statistics']['covered_pages']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
