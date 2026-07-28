#!/usr/bin/env python3
"""
自动生成批注PDF: 通过MD文件定位evidence → 在原始PDF对应页面添加高亮+批注

策略: 在PyMuPDF解析的MD文件中搜索evidence_text(匹配率接近100%)
      然后通过 ## 第N页 标记定位PDF页码 → 用PyMuPDF标注整页

用法: python3 scripts/build_annotations_pdf.py
输入: data/week1PDF/*.pdf (原始PDF)
      review/*.md (PyMuPDF解析的MD)
      outputs/*/融资历史_结构化.json (evidence)
输出: annotations_pdf/{code}_{name}_关键页批注.pdf
"""
import sys, re, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import fitz
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CODES = {
    "三联锻造": "001282", "友升股份": "603418", "黄山谷捷": "301581",
    "云汉芯城": "301563", "赛分科技": "688758", "影石创新": "688775",
    "三协电机": "920100", "星图测控": "920116",
}


def find_pdf(name, code):
    """找原始PDF"""
    for pdf_dir in [PROJECT_ROOT / "data" / "week1PDF",
                     PROJECT_ROOT / "data" / "week2PDF"]:
        if not pdf_dir.exists(): continue
        for pf in pdf_dir.glob("*.pdf"):
            if name in pf.stem or code in pf.stem:
                return pf
    return None


def search_md(evidence_text, md_dir):
    """
    在MD文件中搜索evidence_text,返回(list of (md_file, pdf_page, line_number))
    策略: 逐句搜索,返回所有匹配位置
    """
    results = []
    # 取evidence的前40-80个字符作为搜索片段(去特殊字符)
    snippet = evidence_text[:80].replace('\n', '').replace('\r', '').strip()
    # 去掉首尾引号、括号等
    snippet = re.sub(r'^["\'\s]+|["\'\s]+$', '', snippet)

    for mdf in sorted(Path(md_dir).glob("*.md")):
        if not mdf.exists(): continue
        try:
            with open(mdf, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except:
            continue

        current_page = 1
        for i, line in enumerate(lines, 1):
            # 跟踪页码
            pm = re.match(r'##\s*第(\d+)页', line)
            if pm:
                current_page = int(pm.group(1))

            # 逐字符搜索
            clean_line = line.replace('\n', '').replace('\r', '').strip()
            if len(clean_line) < 10:
                continue

            # 搜索: 尝试证据的前60字,前40字,前20字
            for length in [60, 40, 20]:
                query = snippet[:length]
                if len(query) < 10:
                    continue
                if query in clean_line:
                    results.append({
                        "md_file": mdf.name,
                        "pdf_page": current_page,
                        "line_number": i,
                        "matched_text": clean_line[:100],
                        "query_length": length
                    })
                    break  # 找到就停

            if len(results) > 0 and results[-1]["pdf_page"] == current_page:
                # 同一页面已找到,继续但不重复添加
                pass

    return results


def annotate_page(pdf_path, page_num, evidence_text, output_path):
    """在指定PDF页上添加高亮+批注"""
    if not HAS_FITZ: return False

    doc = fitz.open(str(pdf_path))
    if page_num < 1 or page_num > len(doc):
        doc.close()
        return False

    page = doc[page_num - 1]

    # 搜索evidence中的关键片段在PDF页面上高亮
    snippets = []
    # 数字+单位
    snippets.extend(re.findall(r'\d+[\d,]*\.?\d*\s*[万亿美港元人]', evidence_text)[:5])
    # 中文实体名
    snippets.extend(re.findall(r'[一-龥]{4,15}(?:有限(?:责任)?公司|合伙|企业|基金)', evidence_text)[:3])
    # 日期
    for m in re.finditer(r'(\d{4})-(\d{2})-(\d{2})', evidence_text):
        y, mth, d = m.group(1), int(m.group(2)), int(m.group(3))
        snippets.append(f"{y}年{mth}月{d}日" if d != 1 else f"{y}年{mth}月")

    highlighted = 0
    for kw in snippets[:8]:
        if len(kw) < 3: continue
        try:
            insts = page.search_for(kw)
            for inst in insts:
                annot = page.add_highlight_annot(inst)
                annot.set_colors({"stroke": (1, 0, 0), "fill": (1, 1, 0, 0.3)})
                annot.update()
                highlighted += 1
        except:
            pass

    # 页面顶部加批注框
    short_ev = evidence_text[:150].replace('\n', ' ')
    page.insert_text((20, 20), f"[批注] {short_ev}...",
                     fontname="china-s", fontsize=8, color=(0.8, 0, 0))

    doc.save(str(output_path), incremental=False)
    doc.close()
    return True


def build():
    ann_dir = PROJECT_ROOT / "annotations_pdf"
    ann_dir.mkdir(parents=True, exist_ok=True)

    success, failed, skipped = 0, 0, 0

    for name, code in CODES.items():
        # 加载结构化JSON
        sp = PROJECT_ROOT / "outputs" / name / f"{name}_融资历史_结构化.json"
        if not sp.exists():
            print(f"  ✗ {code} {name}: 无结构化JSON")
            skipped += 1
            continue

        with open(sp, encoding="utf-8") as f:
            data = json.load(f)

        # 找PDF
        pdf_path = find_pdf(name, code)
        if not pdf_path:
            print(f"  ✗ {code} {name}: PDF不存在")
            # 仍然尝试只做MD标注
            pass

        # 为每个event生成批注页
        for ev in data.get("financing_events", []):
            et = ev.get("event_type", "")
            if et == "股权转让" and name == "赛分科技" and ev.get("event_date") == "2011-10":
                continue

            evidence = ev.get("evidence_text", "")
            if len(evidence) < 20:
                failed += 1
                continue

            ev_order = ev["event_order"]
            out_name = f"{code}_{name}_event{ev_order}.pdf"
            out_path = ann_dir / out_name

            # 第一步: 从source_page提取正确PDF页码(优先)
            sp_match = re.search(r'PDF p(\d+)', ev.get("source_page", ""))
            correct_page = int(sp_match.group(1)) if sp_match else None

            # 第二步: MD文件中验证evidence存在
            matches = search_md(evidence, PROJECT_ROOT / "review")
            md_found = len(matches) > 0

            # 第三步: 用正确页码生成批注
            page = correct_page or (matches[0]["pdf_page"] if matches else None)
            if not page:
                print(f"  ✗ {code} {name} event{ev_order}: 无法确定PDF页码")
                failed += 1
                continue

            md_status = f"MD✓({matches[0]['matched_text'][:30]}...)" if md_found else "MD✗"
            status_mark = "✓" if md_found and correct_page else ("~" if correct_page else "✗")
            print(f"  {status_mark} {code} {name} event{ev_order}: PDF p{page} {md_status}")

            if pdf_path and page:
                annotate_page(pdf_path, page, evidence, out_path)
                success += 1
            elif not pdf_path:
                print(f"     (无PDF,跳过批注)")
                skipped += 1

    print(f"\n完成: {success}成功, {failed}失败, {skipped}跳过 ({success}/{success+failed}匹配率)")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    if not HAS_FITZ:
        print("请安装: pip install PyMuPDF")
        sys.exit(1)
    sys.exit(build())
