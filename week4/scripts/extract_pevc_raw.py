#!/usr/bin/env python3
"""
三协电机 PE/VC 原文提取 + 拼接

思路（闫老师建议: 先定位，再抽取，两步独立）:
  1. 用代码定位 PE/VC 相关的PDF页码范围
  2. 逐页提取原文
  3. 拼接成一个完整的 Markdown 文件，保留PDF页码标记

输出: week4/outputs/三协电机_PEVC_原文.md
      week4/outputs/三协电机_PEVC_原文.txt  (纯文本版)
"""
import sys
import re
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import *

try:
    import fitz
except ImportError:
    print("请安装: pip install PyMuPDF")
    sys.exit(1)


# ============================================================
# PE/VC 相关页面定义（手动精确定位，不是全量扫）
# ============================================================

# 三协电机招股书 PE/VC 关键页面映射
PEVC_PAGE_MAP = {
    # 第四节 发行人基本情况
    "公司基本信息": [30],           # 成立日期、注册资本、法定代表人
    "报告期内发行融资": [31, 32],    # 2022年定增 + 2023年定增（核心PE/VC章节）
    "股权结构": [33],               # 股权结构图
    "控股股东及实际控制人": [33, 34], # 盛祎、朱绶青
    "5%以上股东-稳正景明详情": [34, 35],  # PE基金: 稳正景明企业信息、GP/LP结构
    "IPO前股东持股表": [35, 36],     # 发行前/后股东持股明细表
    "股东限售/持股详情": [37, 38],   # 持股数量、股权比例
    "新增股东-私募基金备案": [38, 39], # 稳正景明SNG030 / 长泽创投SVU935
    "历史沿革-股权代持": [39],       # 2021年3月解除代持
}

# 合并去重，保持页码顺序
ALL_PEVC_PAGES = sorted(set(
    p for pages in PEVC_PAGE_MAP.values() for p in pages
))


def extract_page_text(doc, page_num: int) -> str:
    """提取单页文本，保留页码标记"""
    if page_num < 1 or page_num > len(doc):
        return ""
    page = doc[page_num - 1]  # fitz 0-indexed
    text = page.get_text("text")
    return f"\n## 第{page_num}页 (PDF p{page_num})\n\n{text}\n"


def extract_page_tables(doc, page_num: int) -> str:
    """提取单页表格为Markdown格式"""
    if page_num < 1 or page_num > len(doc):
        return ""
    page = doc[page_num - 1]
    tables = page.find_tables()
    if not tables or not tables.tables:
        return ""

    md_lines = []
    for t_idx, table in enumerate(tables.tables):
        data = table.extract()
        if not data or len(data) < 2:
            continue

        md_lines.append(f"\n### 表格 {t_idx + 1} (p{page_num})\n")

        for i, row in enumerate(data):
            cleaned = [str(c).strip().replace('\n', ' ') if c else '' for c in row]
            if any(cleaned):
                md_lines.append('| ' + ' | '.join(cleaned) + ' |')
                if i == 0:
                    md_lines.append('|' + '|'.join(['---' for _ in cleaned]) + '|')

        md_lines.append('')

    return '\n'.join(md_lines)


def main():
    pdf_path = PDF_DIR / TARGET["pdf"]
    if not pdf_path.exists():
        print(f"✗ PDF不存在: {pdf_path}")
        return 1

    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)

    print("=" * 60)
    print(f"三协电机 PE/VC 原文提取")
    print(f"  PDF: {pdf_path.name} ({total_pages}页)")
    print(f"  目标页码: {ALL_PEVC_PAGES}")
    print("=" * 60)

    # ── 1. 提取原文 ──
    md_sections = []
    txt_sections = []

    # 文件头
    header = f"""# 三协电机 PE/VC 相关原文提取

> 源文件: {TARGET['pdf']}
> 提取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
> 公司: {TARGET['full_name']} ({TARGET['code']})
> 总页数: {total_pages}
> PE/VC相关页数: {len(ALL_PEVC_PAGES)}

---

"""
    md_sections.append(header)
    txt_sections.append(re.sub(r'[#*>\-]', '', header))

    # 按章节分组输出
    for section_name, pages in PEVC_PAGE_MAP.items():
        page_range = f"p{pages[0]}-p{pages[-1]}" if len(pages) > 1 else f"p{pages[0]}"

        md_sections.append(f"\n---\n\n# {section_name} ({page_range})\n")
        txt_sections.append(f"\n{'='*60}\n{section_name} ({page_range})\n{'='*60}\n")

        for p in pages:
            # 原文
            text = extract_page_text(doc, p)
            if text.strip():
                md_sections.append(text)
                txt_sections.append(text)

            # 表格
            table_md = extract_page_tables(doc, p)
            if table_md.strip():
                md_sections.append(table_md)

        # 统计该章节字数
        section_text = ''.join(md_sections[-len(pages)*2:])
        char_count = len(section_text.replace('\n', '').replace(' ', ''))
        print(f"  ✓ {section_name:30s} ({page_range:8s}): {char_count:,} 字符")

    doc.close()

    # ── 2. 拼接输出 ──
    full_md = ''.join(md_sections)
    full_txt = ''.join(txt_sections)

    # Markdown版
    md_path = OUTPUTS_DIR / "三协电机_PEVC_原文.md"
    md_path.write_text(full_md, encoding='utf-8')

    # 纯文本版（方便直接投喂LLM）
    txt_path = OUTPUTS_DIR / "三协电机_PEVC_原文.txt"
    txt_path.write_text(full_txt, encoding='utf-8')

    # ── 3. 统计 ──
    total_chars = len(full_md.replace('\n', '').replace(' ', ''))
    total_lines = full_md.count('\n')

    print(f"\n{'='*60}")
    print(f"✓ 提取完成")
    print(f"  Markdown: {md_path} ({md_path.stat().st_size:,} bytes)")
    print(f"  纯文本:   {txt_path} ({txt_path.stat().st_size:,} bytes)")
    print(f"  总字符数: {total_chars:,}")
    print(f"  总行数:   {total_lines:,}")
    print(f"  覆盖页数: {len(ALL_PEVC_PAGES)}/{total_pages}")
    print(f"  章节数:   {len(PEVC_PAGE_MAP)}")

    # 估算token数 (1 token ≈ 2 中文字符)
    est_tokens = total_chars // 2
    print(f"  估算token: ~{est_tokens:,} (中文)")
    print(f"  DeepSeek费用: ~¥{est_tokens * 0.000002:.4f} (输入)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
