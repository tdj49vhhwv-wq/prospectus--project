"""Check the actual PDF, DOCX styles, five figures and report numbers."""
from __future__ import annotations

import json
import re
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import pymupdf
from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "report"


def main():
    settings = json.loads((REPORT / "版式与待办说明.json").read_text())
    doc = pymupdf.open(REPORT / settings["pdf"])
    assert len(doc) == 10, f"Expected cover + 8 body pages + references; got {len(doc)}"
    assert "小组名称：" in doc[0].get_text() and settings["team_name"] in doc[0].get_text()
    assert "参考文献与数据来源" in doc[9].get_text()
    text = "".join(page.get_text() for page in doc)
    normalized = re.sub(r"\s+", "", text)
    for term in ["赵秉清", "zbq2427635521", "tdj49vhhwv", "小组成员", "姓名", "学校"]:
        assert term not in text, "Identity-bearing text: " + term
    assert not doc.metadata.get("author")
    summary = json.loads((ROOT / "outputs/analysis_summary.json").read_text())
    base, enhanced = summary["baseline"], summary["primary"]
    delta = summary["metrics"][enhanced]["ap"] - summary["metrics"][base]["ap"]
    for expected in ["581", "229", "615", "99,441", "112,650", "99,224", "71.19%", "34.46%", f"{delta:.4f}", "MIT", "未来90天", "不等于银行", "同一固定模型"]:
        assert expected in normalized, "Missing result or limitation: " + expected
    assert "285小组" in normalized and "待填" not in normalized
    log = (REPORT / "build/report.log").read_text()
    assert "Missing character:" not in log
    assert "Overfull" not in log
    font_sizes, line_distances, indent_distances = [], [], []
    page_audit = []
    for index, page in enumerate(doc):
        spans = [span for block in page.get_text("dict")["blocks"] if block["type"] == 0 for line in block["lines"] for span in line["spans"]]
        if 1 <= index <= 8:
            assert str(index) == page.get_text().strip().splitlines()[-1]
            body_spans = [span for span in spans if span["font"] == "FandolSong-Regular" and abs(span["size"] - 10.5) < .05 and span["bbox"][1] < page.rect.height - 65]
            assert body_spans, f"No five-point body font on page {index+1}"
            font_sizes.extend(span["size"] for span in body_spans)
            # Text line origins identify the full-length paragraphs independently of figure labels.
            for block in page.get_text("dict")["blocks"]:
                if block["type"] != 0:
                    continue
                lines = [line for line in block["lines"] if line["spans"] and line["spans"][0]["font"] == "FandolSong-Regular" and abs(line["spans"][0]["size"] - 10.5) < .05]
                if len(lines) >= 2:
                    first, second = lines[:2]
                    left1 = first["spans"][0]["origin"][0]
                    left2 = second["spans"][0]["origin"][0]
                    if abs(left2 - 24 / 25.4 * 72) < .15 and abs(left1 - left2 - 21) < .15:
                        indent_distances.append(left1 - left2)
                        line_distances.append(second["spans"][0]["origin"][1] - first["spans"][0]["origin"][1])
            assert all(span["bbox"][2] <= page.rect.width - 24 / 25.4 * 72 + .5 for span in spans), f"Right-margin overflow on page {index+1}"
        page_audit.append({"pdf_page": index+1, "role": "cover" if index == 0 else "references" if index == 9 else "body", "text_characters": len(page.get_text())})
    assert len(indent_distances) >= 20
    assert all(abs(distance - 21) < .15 for distance in indent_distances)
    assert all(abs(distance - 15.75) < .15 for distance in line_distances)
    png_files = list((REPORT / "figures").glob("*.png"))
    pdf_files = list((REPORT / "figures").glob("*.pdf"))
    assert len(png_files) == len(pdf_files) == 5
    for i in range(1, 6):
        assert f"图{i}" in normalized
    for i in range(1, 7):
        assert f"表{i}" in normalized
    with ZipFile(REPORT / "报告可编辑稿.docx") as archive:
        root = etree.fromstring(archive.read("word/styles.xml"))
        namespaces = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        normal = root.xpath("//w:style[@w:styleId='Normal']", namespaces=namespaces)[0]
        assert normal.xpath("./w:rPr/w:sz/@w:val", namespaces=namespaces) == ["21"]
        assert normal.xpath("./w:rPr/w:rFonts/@w:eastAsia", namespaces=namespaces) == ["宋体"]
        assert normal.xpath("./w:pPr/w:spacing/@w:line", namespaces=namespaces) == ["360"]
        assert normal.xpath("./w:pPr/w:spacing/@w:before", namespaces=namespaces) == ["0"]
        assert normal.xpath("./w:pPr/w:spacing/@w:after", namespaces=namespaces) == ["0"]
        assert normal.xpath("./w:pPr/w:ind/@w:firstLine", namespaces=namespaces) == ["420"]
    metrics = pd.read_csv(ROOT / "outputs/model_metrics.csv", index_col="model")
    assert len(metrics) == 6
    assert abs(metrics.loc[base, "ap"] - summary["metrics"][base]["ap"]) < 1e-12
    assert abs(metrics.loc[enhanced, "ap"] - summary["metrics"][enhanced]["ap"]) < 1e-12
    assert metrics.loc[base, "captured"] == metrics.loc[enhanced, "captured"] == 42
    pair = json.loads((ROOT / "outputs/low_rating_comparison.json").read_text())
    assert pair["paired_ci95"][0] > 0 and summary["primary_minus_baseline"]["ap"][0] < 0
    later = json.loads((ROOT / "outputs/later_anchor_notes.json").read_text())
    assert later["same_fixed_models_verified"] and later["primary_minus_baseline_ap_ci95"][0] < 0
    results = {"status": "passed", "total_pdf_pages": len(doc), "body_pages": 8, "cover_pages": 1, "reference_pages": 1,
               "chinese_core_figures": 5, "numbered_tables": 6, "body_font": "embedded FandolSong-Regular", "body_size_pdf_pt": round(sum(font_sizes)/len(font_sizes), 3),
               "body_baseline_pdf_pt": round(sum(line_distances)/len(line_distances), 3), "body_paragraph_indent_pdf_pt": round(sum(indent_distances)/len(indent_distances), 3),
               "indented_paragraphs_checked": len(indent_distances), "identity_checks": "no member name, school or personal repository identity; blank PDF author", "latex_overflows_or_missing_glyphs": 0,
               "docx": "五号宋体、1.5倍行距、0段间距、2字符缩进；Word本机分页可能随字体环境变化", "pages": page_audit,
               "remaining": settings["remaining"]}
    (REPORT / "排版检查结果.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
