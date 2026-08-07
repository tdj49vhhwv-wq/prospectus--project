"""
Markdown 文本源 — 当 PDF 不可用时，从 MinerU markdown 提取文本段落

用法:
  from markdown_source import load_company_text
  snippets = load_company_text(code)  # → [{"text": "...", "pdf_page": 50}, ...]
"""
import os
import re
from pathlib import Path


def get_md_dir() -> Path:
    """Return the Markdown source directory, with an optional local override."""
    configured = os.environ.get("PROSPECTUS_MD_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "week1" / "review"

# 8家公司 → markdown 文件映射
MD_FILES = {
    "001282": ["三联锻造_招股书_PyMuPDF.md", "三联锻造3.md"],  # PyMuPDF版 + 历史沿革流程图
    "301563": ["云汉芯城_招股书_PyMuPDF.md", "云汉芯城2.md"],  # PyMuPDF版 + 历史沿革流程图
    "301581": ["黄山谷捷_招股书_PyMuPDF.md"],  # PyMuPDF版
    "603418": ["友升股份1.md", "友升股份2.md"],  # 分段合并
    "688758": ["688758_赛分科技_招股书_正式稿_20250106.md"],
    "688775": ["688775_影石创新_招股书_正式稿_20250606.md"],
    "920100": ["三协电机_招股书_正式稿_20250711.md"],
    "920116": ["星图测控_招股书_正式稿_20241220.md"],
}

# PE/VC 相关章节定位关键词（同 config.py SECTION_KEYWORDS）
SECTION_KEYWORDS = [
    "发行人基本情况", "发行融资情况", "股权结构",
    "股东及实际控制人", "历史沿革", "股本演变",
    "设立及报告期内", "股本和股东变化", "历次增资",
    "整体变更", "出资", "增资", "股权转让",
]


def load_company_text(code: str) -> list[dict]:
    """加载一家公司的所有文本段落"""
    md_names = MD_FILES.get(code, [])
    if not md_names:
        return []

    all_snippets = []
    md_dir = get_md_dir()
    page_offset = 0

    for md_name in md_names:
        path = md_dir / md_name
        if not path.exists():
            continue
        full_text = path.read_text(encoding='utf-8')
        pages = re.split(r'\n## 第(\d+)页\n', full_text)

        # 没找到分页标记 → 分块处理（每3000字一块）
        if len(pages) < 3:
            # 按行分块：目标 3000 字，优先在空行（段落/代码块边界）截断，
            # 超过 6000 字才硬切，避免把 mermaid 流程图拦腰截断
            chunks = []
            buf = []
            buf_len = 0
            for line in full_text.splitlines(keepends=True):
                buf.append(line)
                buf_len += len(line)
                if buf_len >= 3000 and line.strip() == "":
                    chunks.append("".join(buf))
                    buf, buf_len = [], 0
                elif buf_len >= 6000:
                    chunks.append("".join(buf))
                    buf, buf_len = [], 0
            if buf:
                chunks.append("".join(buf))
            for i, chunk in enumerate(chunks):
                if not any(kw in chunk for kw in SECTION_KEYWORDS):
                    continue
                all_snippets.append({
                    "text": chunk,
                    "pdf_page": page_offset + i + 1,
                    "keyword": _find_keyword(chunk),
                })
            page_offset += len(chunks)
            continue

        for i in range(1, len(pages), 2):
            if i + 1 >= len(pages):
                break
            try:
                page_num = int(pages[i]) + page_offset
                page_text = pages[i + 1]
            except ValueError:
                continue
            if not any(kw in page_text for kw in SECTION_KEYWORDS):
                continue
            all_snippets.append({
                "text": page_text[:5000],
                "pdf_page": page_num,
                "keyword": _find_keyword(page_text),
            })
        if pages[1::2]:
            page_offset += max(int(x) for x in pages[1::2])

    return all_snippets


def _find_keyword(text: str) -> str:
    """找到第一个匹配的关键词"""
    for kw in SECTION_KEYWORDS:
        if kw in text:
            return kw
    return "其他"


def make_located_data(code: str, company_name: str) -> dict:
    """生成兼容 extract_pevc.py 的 located_data 结构"""
    snippets = load_company_text(code)
    if not snippets:
        return None

    pages = set(s["pdf_page"] for s in snippets)

    return {
        "company": {
            "name": company_name,
            "code": code,
            "pdf": f"{company_name}_招股书.md",  # markdown路径
        },
        "pevc_snippets": snippets,
        "statistics": {
            "total_pages": max(pages) if pages else 0,
            "covered_pages": list(pages),
            "snippet_count": len(snippets),
        },
    }


if __name__ == "__main__":
    # 测试：加载三协电机
    for code in ["920100", "688758"]:
        data = make_located_data(code, code)
        if data:
            print(f"{code}: {len(data['pevc_snippets'])} snippets, pages {data['statistics']['covered_pages'][:10]}...")
