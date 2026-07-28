#!/usr/bin/env python3
"""
Step 3: OCR + 结构化处理（PyMuPDF表格提取 + PaddleOCR备选）

用途:
  1. 对PDF中的表格进行精确提取（合并单元格、跨页表格拼接）
  2. 对扫描件/图片页进行OCR识别（PaddleOCR备选方案）
  3. 对PyMuPDF文本提取失败的页面进行兜底

设计原则（来自同学建议: OCR + 结构化处理）:
  - 主路径: PyMuPDF find_tables() → 结构化数据（速度快、确定性高）
  - 备选路径: PaddleOCR → 文本行检测 → 表格重建（扫描件/图片PDF）
  - 表格输出: 保留原始行列结构的JSON，不依赖LLM直接生成表格
  - 数据后处理: 在Excel中调整，而非LLM硬凑

输入: PDF文件 + located_sections.json
输出: week4/outputs/ocr_tables.json (结构化表格数据)
"""
import json
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import *

try:
    import fitz
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

# PaddleOCR 是可选依赖
try:
    from paddleocr import PaddleOCR
    HAS_PADDLE = True
except ImportError:
    HAS_PADDLE = False


def log_step(step_name: str, status: str, detail: str = ""):
    """记录步骤到 step_log.csv"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "step": step_name,
        "status": status,
        "detail": detail,
    }
    with open(STEP_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    symbol = {"success": "✓", "failed": "✗", "warning": "⚠"}
    print(f"  {symbol.get(status, '?')} {step_name}: {detail}")


# ============================================================
# 1. PyMuPDF 表格提取（主路径）
# ============================================================

def extract_tables_pymupdf(pdf_path: Path, pages: List[int]) -> List[Dict[str, Any]]:
    """
    PyMuPDF find_tables() 提取指定页码的表格

    返回结构化表格数据，保留行列结构
    """
    doc = fitz.open(str(pdf_path))
    all_tables = []

    for page_num in pages:
        if page_num < 0 or page_num >= len(doc):
            continue

        page = doc[page_num]
        tables = page.find_tables()

        if not tables or not tables.tables:
            continue

        page_text = page.get_text("text")

        for t_idx, table in enumerate(tables.tables):
            data = table.extract()

            if not data or len(data) < 2:
                continue

            # 清洗数据：去除空行、合并单元格占位符
            cleaned = []
            for row in data:
                cleaned_row = [
                    str(c).strip() if c and str(c).strip() else ""
                    for c in row
                ]
                # 跳过全空行
                if any(cleaned_row):
                    cleaned.append(cleaned_row)

            if len(cleaned) < 2:
                continue

            # 尝试识别表头
            header_row_idx = _find_header_row(cleaned)

            # 表头在前的处理
            if header_row_idx is not None and header_row_idx > 0:
                # 前面的行可能是标题/说明
                pass

            all_tables.append({
                "pdf_page": page_num + 1,
                "table_index": t_idx,
                "rows": len(cleaned),
                "cols": max(len(r) for r in cleaned),
                "header_row": header_row_idx,
                "header": cleaned[header_row_idx] if header_row_idx is not None else [],
                "data": cleaned[header_row_idx + 1:] if header_row_idx is not None else cleaned[1:],
                "raw_data": cleaned,
                "page_text_snippet": page_text[:200].strip(),
            })

    doc.close()
    return all_tables


def _find_header_row(rows: List[List[str]]) -> Optional[int]:
    """在表格行中找表头行（含'股东''持股'等关键词）"""
    for i, row in enumerate(rows):
        row_text = " ".join(row)
        if re.search(r'股东|持股|序号|数量|比例|名称|金额|日期', row_text):
            return i
    return 0  # 默认第一行为表头


# ============================================================
# 2. PaddleOCR 表格提取（备选路径，扫描件/图片PDF用）
# ============================================================

def extract_tables_paddleocr(pdf_path: Path, pages: List[int]) -> List[Dict[str, Any]]:
    """
    PaddleOCR 对指定页进行OCR识别，重建表格结构

    适用场景:
      - PDF是扫描件（无文本层）
      - PyMuPDF get_text() 返回空或乱码
      - 含复杂图片图表的页面

    方法:
      1. PyMuPDF 将页面渲染为高分辨率图片
      2. PaddleOCR 检测文本行 → 获得 (文本, bbox, 置信度)
      3. 基于y坐标聚类 → 分出行
      4. 基于x坐标排序 → 分出列
    """
    if not HAS_PADDLE:
        log_step("ocr_paddle", "warning", "PaddleOCR未安装，跳过。安装: pip install paddlepaddle paddleocr")
        return []

    doc = fitz.open(str(pdf_path))
    ocr = PaddleOCR(use_angle_cls=True, lang='ch', show_log=False)
    all_tables = []

    for page_num in pages:
        if page_num < 0 or page_num >= len(doc):
            continue

        page = doc[page_num]

        # 渲染为图片（300 DPI，保证OCR精度）
        mat = page.get_pixmap(dpi=300)
        img_bytes = mat.tobytes("png")

        # PaddleOCR 识别
        result = ocr.ocr(img_bytes, cls=True)

        if not result or not result[0]:
            continue

        # 提取文本行：(text, bbox, confidence)
        lines = []
        for line_info in result[0]:
            bbox = line_info[0]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            text = line_info[1][0]
            confidence = line_info[1][1]

            # 使用左上角和右下角坐标
            x1 = min(p[0] for p in bbox)
            y1 = min(p[1] for p in bbox)
            x2 = max(p[0] for p in bbox)
            y2 = max(p[1] for p in bbox)

            lines.append({
                "text": text,
                "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                "confidence": confidence,
            })

        if not lines:
            continue

        # 基于y坐标聚类 → 表格行
        rows = _cluster_by_y(lines, y_tolerance=15)

        # 每行内按x坐标排序 → 列
        table_rows = []
        for row_lines in rows:
            row_lines.sort(key=lambda l: l["x1"])
            table_rows.append([l["text"] for l in row_lines])

        if table_rows:
            header_row_idx = _find_header_row(table_rows)
            all_tables.append({
                "pdf_page": page_num + 1,
                "method": "paddleocr",
                "rows": len(table_rows),
                "cols": max(len(r) for r in table_rows),
                "header_row": header_row_idx,
                "header": table_rows[header_row_idx] if header_row_idx is not None else [],
                "data": table_rows[header_row_idx + 1:] if header_row_idx is not None else table_rows[1:],
                "ocr_confidence_avg": sum(l["confidence"] for l in lines) / len(lines) if lines else 0,
            })

    doc.close()
    return all_tables


def _cluster_by_y(lines: List[Dict], y_tolerance: int = 15) -> List[List[Dict]]:
    """
    基于y坐标（垂直位置）将OCR文本行聚类成表格行

    原理: 同一表格行的文本块具有相近的y坐标
    """
    if not lines:
        return []

    sorted_lines = sorted(lines, key=lambda l: (l["y1"], l["x1"]))
    clusters = []
    current_cluster = [sorted_lines[0]]
    current_y = sorted_lines[0]["y1"]

    for line in sorted_lines[1:]:
        if abs(line["y1"] - current_y) <= y_tolerance:
            current_cluster.append(line)
        else:
            clusters.append(current_cluster)
            current_cluster = [line]
            current_y = line["y1"]

    if current_cluster:
        clusters.append(current_cluster)

    return clusters


# ============================================================
# 3. 跨页表格拼接
# ============================================================

def merge_cross_page_tables(tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    拼接跨页断裂的表格

    识别条件:
      - 前页最后几行的列数与后页表头列数一致
      - 后页表格的表头与前页表头相似度 > 80%
    """
    if len(tables) < 2:
        return tables

    merged = []
    skip_indices = set()

    for i in range(len(tables) - 1):
        if i in skip_indices:
            continue

        t1 = tables[i]
        t2 = tables[i + 1]

        # 判断是否为连续页面
        if t2["pdf_page"] - t1["pdf_page"] != 1:
            merged.append(t1)
            continue

        # 判断表头相似度
        h1 = set(str(h).strip() for h in t1.get("header", []))
        h2 = set(str(h).strip() for h in t2.get("header", []))

        if h1 and h2:
            overlap = len(h1 & h2) / max(len(h1), len(h2)) if max(len(h1), len(h2)) > 0 else 0
            if overlap > 0.5:
                # 拼接：合并数据行
                merged_table = t1.copy()
                merged_table["data"] = t1["data"] + t2["data"]
                merged_table["rows"] = len(merged_table["data"])
                merged_table["pdf_page"] = f"{t1['pdf_page']}-{t2['pdf_page']}"
                merged_table["merged_from_pages"] = [t1["pdf_page"], t2["pdf_page"]]
                merged.append(merged_table)
                skip_indices.add(i + 1)
                continue

        merged.append(t1)

    # 最后一页
    if len(tables) - 1 not in skip_indices:
        merged.append(tables[-1])

    return merged


# ============================================================
# 4. 图片页面提取（如股权结构图）
# ============================================================

def extract_images_from_pages(pdf_path: Path, pages: List[int], output_dir: Path) -> List[Dict]:
    """
    提取PDF中图片页面（如股权结构图）并保存为PNG

    用于后续人工查看或OCR处理
    """
    doc = fitz.open(str(pdf_path))
    output_dir.mkdir(parents=True, exist_ok=True)
    extracted = []

    for page_num in pages:
        if page_num < 0 or page_num >= len(doc):
            continue

        page = doc[page_num]
        images = page.get_images()

        if not images:
            continue

        for img_idx, img in enumerate(images):
            xref = img[0]
            base_image = doc.extract_image(xref)
            img_bytes = base_image["image"]
            ext = base_image["ext"]

            img_name = f"page{page_num+1}_img{img_idx}.{ext}"
            img_path = output_dir / img_name
            img_path.write_bytes(img_bytes)

            extracted.append({
                "pdf_page": page_num + 1,
                "image_index": img_idx,
                "format": ext,
                "width": base_image["width"],
                "height": base_image["height"],
                "saved_path": str(img_path),
            })

    doc.close()
    return extracted


# ============================================================
# 5. 主函数：统一OCR+结构化处理入口
# ============================================================

def main():
    located_path = OUTPUTS_DIR / "located_sections.json"
    if not located_path.exists():
        print(f"✗ 找不到 {located_path}，请先运行 locate_pevc_sections.py")
        return 1

    with open(located_path, "r", encoding="utf-8") as f:
        located_data = json.load(f)

    pdf_path = PDF_DIR / located_data["company"]["pdf"]
    covered_pages = located_data["statistics"]["covered_pages"]

    print("=" * 60)
    print(f"[Step 3] OCR + 结构化表格提取")
    print(f"  PDF: {pdf_path}")
    print(f"  目标页码: {covered_pages}")
    print(f"  PyMuPDF: {'✓' if HAS_FITZ else '✗'}")
    print(f"  PaddleOCR: {'✓' if HAS_PADDLE else '✗ (备选，扫描件时需安装)'}")
    print("=" * 60)

    if not HAS_FITZ:
        log_step("ocr_extract", "failed", "PyMuPDF未安装")
        return 1

    # ── 3a: PyMuPDF表格提取（主路径） ──
    pymupdf_tables = extract_tables_pymupdf(pdf_path, covered_pages)
    log_step("table_extract_pymupdf", "success" if pymupdf_tables else "warning",
             f"{len(pymupdf_tables)}个表格 (PyMuPDF)")

    # ── 3b: PaddleOCR备选路径 ──
    paddle_tables = []
    if HAS_PADDLE:
        # 仅在PyMuPDF文本提取失败的页面试用PaddleOCR
        doc = fitz.open(str(pdf_path))
        low_text_pages = []
        for p in covered_pages:
            if p - 1 < len(doc):
                text = doc[p - 1].get_text("text").strip()
                if len(text) < 100:  # 文本过少可能是扫描件
                    low_text_pages.append(p - 1)
        doc.close()

        if low_text_pages:
            paddle_tables = extract_tables_paddleocr(pdf_path, low_text_pages)
            log_step("table_extract_paddleocr", "success" if paddle_tables else "warning",
                     f"{len(paddle_tables)}个表格 (PaddleOCR), 扫描{len(low_text_pages)}页")
    else:
        log_step("table_extract_paddleocr", "warning",
                 "PaddleOCR未安装，跳过。安装: pip install paddlepaddle paddleocr")

    # ── 3c: 合并PyMuPDF + PaddleOCR结果 ──
    all_tables = pymupdf_tables + paddle_tables

    # ── 3d: 跨页表格拼接 ──
    merged_tables = merge_cross_page_tables(all_tables)
    if len(merged_tables) < len(all_tables):
        log_step("merge_cross_pages", "success",
                 f"{len(all_tables)}→{len(merged_tables)} (拼接{len(all_tables)-len(merged_tables)}对)")

    # ── 3e: 图片提取 ──
    img_output_dir = OUTPUTS_DIR / "extracted_images"
    images = extract_images_from_pages(pdf_path, covered_pages, img_output_dir)
    if images:
        log_step("extract_images", "success", f"{len(images)}张图片 → {img_output_dir}")

    # ── 输出 ──
    output = {
        "schema_version": "4.0",
        "generated_at": datetime.now().isoformat(),
        "company": located_data["company"],
        "methods_used": {
            "pymupdf_tables": len(pymupdf_tables),
            "paddleocr_tables": len(paddle_tables),
            "merged_tables": len(merged_tables),
            "extracted_images": len(images),
        },
        "tables": merged_tables,
        "images": images,
    }

    output_path = OUTPUTS_DIR / "ocr_tables.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✓ 输出: {output_path}")
    print(f"  PyMuPDF表格: {len(pymupdf_tables)}")
    print(f"  PaddleOCR表格: {len(paddle_tables)}")
    print(f"  拼接后表格: {len(merged_tables)}")
    print(f"  提取图片: {len(images)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
