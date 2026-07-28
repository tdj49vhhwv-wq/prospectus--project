#!/usr/bin/env python3
"""
MD 行号 → PDF 页码映射工具

解析 PyMuPDF 输出的 `## 第N页` 标记，将 MD 行号范围映射为 PDF 页码。
"""
import re
import sys
from pathlib import Path


def build_page_map(md_path: str) -> dict:
    """构建 {行号: PDF页码} 映射表"""
    page_map = {}
    current_page = 1

    with open(md_path, encoding="utf-8", errors="ignore") as f:
        for line_no, line in enumerate(f, 1):
            m = re.match(r'^##\s*第(\d+)页', line)
            if m:
                current_page = int(m.group(1))
            page_map[line_no] = current_page
    return page_map


def lines_to_pages(md_path: str, start_line: int, end_line: int = None) -> str:
    """将 MD 行号范围转换为 PDF 页码范围"""
    page_map = build_page_map(md_path)
    if end_line is None:
        end_line = start_line

    start_page = page_map.get(start_line, page_map.get(min(page_map.keys()), 1))
    end_page = page_map.get(end_line, start_page)

    if start_page == end_page:
        return f"PDF p{start_page}"
    return f"PDF p{start_page}-{end_page}"


def parse_source_page(source_page: str, md_dir: str) -> str:
    """解析 source_page 字符串，将 MD 行号转为 PDF 页码

    输入格式: "友升股份2.md 第695-730行" 或 "PDF p43-45"
    """
    if source_page.startswith("PDF p"):
        return source_page

    m = re.match(r'(.+?\.md)\s*第(\d+)[-–—](\d+)行', source_page)
    if not m:
        m = re.match(r'(.+?\.md)\s*第(\d+)行', source_page)
    if not m:
        return source_page

    md_file = m.group(1)
    start_line = int(m.group(2))
    end_line = int(m.group(3)) if m.lastindex >= 3 else start_line

    md_path = Path(md_dir) / md_file
    if not md_path.exists():
        return source_page

    return lines_to_pages(str(md_path), start_line, end_line)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python md_to_pdf_page.py <md_file> [start_line] [end_line]")
        sys.exit(1)

    md_file = sys.argv[1]
    if len(sys.argv) >= 4:
        result = lines_to_pages(md_file, int(sys.argv[2]), int(sys.argv[3]))
    elif len(sys.argv) == 3:
        result = lines_to_pages(md_file, int(sys.argv[2]))
    else:
        result = str(build_page_map(md_file))

    print(result)
