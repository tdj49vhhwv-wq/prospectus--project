"""
Markdown 文本源 — 当 PDF 不可用时，从 MinerU markdown 提取文本段落

用法:
  from markdown_source import load_company_text
  snippets = load_company_text(code)  # → [{"text": "...", "pdf_page": 50}, ...]
"""
import re
from pathlib import Path

# MinerU markdown 文件路径
MD_DIR = Path('/Users/zhaobingqing/GitHub/prospectus-pevc-project/week1/review')

# 8家公司 → markdown 文件映射
MD_FILES = {
    "001282": ["三联锻造1.md", "三联锻造2.md", "三联锻造3.md"],
    "301563": ["云汉芯城1.md", "云汉芯城2.md", "云汉芯城3.md"],
    "301581": ["黄山谷捷1.md", "黄山谷捷2.md"],
    "603418": ["友升股份1.md", "友升股份2.md"],
    "688758": ["赛分科技1md.md", "赛分科技2.md", "赛分科技3.md"],
    "688775": ["影石创新1.md", "影石创新2.md", "影石创新3.md"],
    "920100": ["三协电机_招股书_正式稿_20250711.md"],
    "920116": ["星图测控1.md", "星图测控2.md"],
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
    for md_name in md_names:
        path = MD_DIR / md_name
        if not path.exists():
            continue

        text = path.read_text(encoding='utf-8')

        # 按 ## 第N页 分页
        pages = re.split(r'\n## 第(\d+)页\n', text)

        # pages[0] = 文件头, pages[1] = 第1个页码, pages[2] = 第1页内容...
        for i in range(1, len(pages), 2):
            if i + 1 >= len(pages):
                break
            try:
                page_num = int(pages[i])
                page_text = pages[i + 1]
            except ValueError:
                continue

            # 只看含PE/VC关键词的页
            if not any(kw in page_text for kw in SECTION_KEYWORDS):
                continue

            all_snippets.append({
                "text": page_text[:5000],  # 每页最多5000字
                "pdf_page": page_num,
                "keyword": _find_keyword(page_text),
            })

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
