#!/usr/bin/env python3
"""
PDF → Markdown 解析 (PyMuPDF)

⚠ 人工环节: PDF下载需要人工从巨潮资讯网(cninfo.com.cn)获取

用法: python3 parse_pdf.py <pdf_file_or_dir> [output_dir]
输出: review/{pdf_name}.md (每页以 ## 第N页 标记)
"""
import sys
from pathlib import Path

try:
    import fitz
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False


def parse_pdf(pdf_path, output_dir):
    if not HAS_FITZ:
        raise ImportError("需要安装PyMuPDF: pip install PyMuPDF")
    doc = fitz.open(str(pdf_path))
    output_path = output_dir / (pdf_path.stem + ".md")
    with open(output_path, "w", encoding="utf-8") as f:
        for page_num in range(len(doc)):
            text = doc[page_num].get_text("text")
            f.write(f"\n## 第{page_num + 1}页\n\n{text}\n")
    doc.close()
    return output_path, len(doc)


def main():
    if not HAS_FITZ:
        print("请先安装: pip install PyMuPDF"); return 1
    if len(sys.argv) < 2:
        print("用法: python3 parse_pdf.py <pdf_file_or_dir> [output_dir]")
        print("示例: python3 parse_pdf.py ../data/week1PDF/ ../../review/")
        return 1

    pdf_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("../../review")
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = list(pdf_path.glob("*.pdf")) if pdf_path.is_dir() else [pdf_path]
    for pf in pdf_files:
        out, pages = parse_pdf(pf, output_dir)
        print(f"  {pf.name} → {out.name} ({pages}页)")
    print(f"\n✓ {len(pdf_files)} PDF(s) → {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
