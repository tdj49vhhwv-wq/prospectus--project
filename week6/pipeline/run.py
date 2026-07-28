#!/usr/bin/env python3
"""
统一运行入口 — 8家公司 PE/VC 融资历史自动提取

用法:
  python pipeline/run.py                  # 跑全部8家
  python pipeline/run.py --code 920100    # 只跑三协电机
  python pipeline/run.py --code 688775    # 只跑影石创新

输入: data/ 目录下的 PDF 文件 + validation/ 下的 located_sections_{code}.json
输出: auto_output/{code}/ 下的四类 JSONL + extraction_summary.json

人工介入位置:
  - auto_output/ 为纯自动结果，不可人工修改
  - 人工修订在 final/ 中完成，保留修改前后值和原因
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# 路径设置
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PIPELINE_DIR))

from config import (
    PDF_DIR, SECTION_KEYWORDS, INVESTOR_TYPE_KEYWORDS,
    EXCLUDE_ENTITIES, RECORD_TYPE_ABBR, GENERIC_EXTRACTION_RULES,
)

# ── 8家公司清单（manifest） ──
COMPANIES = [
    {"name": "三联锻造", "code": "001282", "pdf": "三联锻造_招股书_正式稿_20230517.pdf"},
    {"name": "云汉芯城", "code": "301563", "pdf": "云汉芯城_招股书_正式稿_20250925.pdf"},
    {"name": "黄山谷捷", "code": "301581", "pdf": "黄山谷捷_招股书_正式稿_20241219.pdf"},
    {"name": "友升股份", "code": "603418", "pdf": "友升股份_招股书_正式稿_20250918.pdf"},
    {"name": "赛分科技", "code": "688758", "pdf": "赛分科技_招股书_正式稿_20250106.pdf"},
    {"name": "影石创新", "code": "688775", "pdf": "影石创新_招股书_正式稿_20250606.pdf"},
    {"name": "三协电机", "code": "920100", "pdf": "三协电机_招股书_正式稿_20250711.pdf"},
    {"name": "星图测控", "code": "920116", "pdf": "星图测控_招股书_正式稿_20241220.pdf"},
]


def run_single_company(company: dict, project_root: Path) -> dict:
    """对单家公司执行完整提取流程"""
    code = company["code"]
    name = company["name"]
    print(f"\n{'='*60}")
    print(f"[Pipeline] {name} ({code})")
    print(f"{'='*60}")

    # 检查 located_sections 是否存在
    located_path = project_root / "validation" / f"located_sections_{code}.json"
    if not located_path.exists():
        # fallback: week5 outputs
        located_path = project_root / "week5" / "outputs" / f"located_sections_{code}.json"
    if not located_path.exists():
        print(f"  SKIP: 找不到 {located_path}")
        return {"code": code, "name": name, "status": "skipped", "reason": "no located_sections"}

    with open(located_path, "r", encoding="utf-8") as f:
        located_data = json.load(f)

    # 检查 PDF 是否存在
    pdf_path = project_root / "week1" / "data" / "week1PDF" / company["pdf"]
    if not pdf_path.exists():
        print(f"  SKIP: PDF不存在 {pdf_path}")
        return {"code": code, "name": name, "status": "skipped", "reason": "no pdf"}

    # 导入提取模块
    try:
        import fitz
    except ImportError:
        print("  ERROR: PyMuPDF未安装，请运行 pip install PyMuPDF")
        return {"code": code, "name": name, "status": "error", "reason": "no pymupdf"}

    import pdfplumber
    from extract_pevc import (
        extract_subscription_flows,
        extract_equity_snapshots_from_tables,
        extract_pe_fund_details,
        extract_share_transfers,
        detect_vie_events,
        detect_flowchart_pages,
        apply_a2_combined_amount_fix,
        apply_f_type_detection,
        classify_english_investor,
        filter_subsidiary_transfers,
        apply_d_subtype_priority,
        normalize_date,
    )

    # 打开 PDF
    doc = fitz.open(str(pdf_path))

    # 流程图页检测
    flowchart_pages = detect_flowchart_pages(doc)
    if flowchart_pages:
        print(f"  WARNING: 检测到流程图页 p{flowchart_pages}，需PaddleOCR补充")

    # 提取四类数据
    sf_rows = extract_subscription_flows(doc, located_data)
    es_rows = extract_equity_snapshots_from_tables(doc, located_data)
    pe_rows = extract_pe_fund_details(doc, located_data)
    st_rows = extract_share_transfers(doc, located_data)
    vie_rows = detect_vie_events(doc, company)

    # 收集全文（post-processing用）
    full_text = {}
    for pg in range(len(doc)):
        full_text[pg + 1] = doc[pg].get_text("text")
    doc.close()

    # Post-processing
    apply_a2_combined_amount_fix(sf_rows)
    apply_f_type_detection(sf_rows, full_text)
    for r in sf_rows + es_rows:
        classify_english_investor(r)
    st_rows = filter_subsidiary_transfers(st_rows)
    apply_d_subtype_priority(st_rows)

    # 输出到 auto_output/{code}/
    output_dir = project_root / "auto_output" / code
    output_dir.mkdir(parents=True, exist_ok=True)

    def write_jsonl(path, rows):
        with open(path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    write_jsonl(output_dir / "subscription_flow.jsonl", sf_rows)
    write_jsonl(output_dir / "equity_snapshot.jsonl", es_rows)
    write_jsonl(output_dir / "pe_fund_detail.jsonl", pe_rows)
    write_jsonl(output_dir / "share_transfer_flow.jsonl", st_rows)
    if vie_rows:
        write_jsonl(output_dir / "vie_events.jsonl", vie_rows)

    # 汇总统计
    all_rows = sf_rows + es_rows + pe_rows + st_rows + vie_rows
    summary = {
        "schema_version": "6.0",
        "generated_at": datetime.now().isoformat(),
        "company": company,
        "statistics": {
            "total_records": len(all_rows),
            "subscription_flow": len(sf_rows),
            "equity_snapshot": len(es_rows),
            "pe_fund_detail": len(pe_rows),
            "share_transfer_flow": len(st_rows),
            "vie_events": len(vie_rows),
            "flowchart_pages": flowchart_pages,
        },
    }
    with open(output_dir / "extraction_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"  OK: SF={len(sf_rows)} ES={len(es_rows)} PE={len(pe_rows)} "
          f"ST={len(st_rows)} VIE={len(vie_rows)} → {output_dir}")
    return {"code": code, "name": name, "status": "success", "total": len(all_rows)}


def main():
    parser = argparse.ArgumentParser(description="PE/VC融资历史自动提取 — 8家公司统一入口")
    parser.add_argument("--code", type=str, default=None,
                        help="只跑指定股票代码，如 --code 920100")
    args = parser.parse_args()

    print("=" * 60)
    print("PE/VC 招股说明书融资历史提取 — Week 6 统一入口")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 确定要处理的公司
    targets = COMPANIES
    if args.code:
        targets = [c for c in COMPANIES if c["code"] == args.code]
        if not targets:
            print(f"ERROR: 未找到代码 {args.code}，可选: {[c['code'] for c in COMPANIES]}")
            return 1

    results = []
    for company in targets:
        result = run_single_company(company, PROJECT_ROOT)
        results.append(result)

    # 汇总
    print(f"\n{'='*60}")
    print("运行汇总")
    print(f"{'='*60}")
    success = sum(1 for r in results if r["status"] == "success")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    errors = sum(1 for r in results if r["status"] == "error")
    print(f"  成功: {success} | 跳过: {skipped} | 错误: {errors}")
    for r in results:
        status_icon = {"success": "OK", "skipped": "SKIP", "error": "ERR"}[r["status"]]
        print(f"  [{status_icon}] {r['name']} ({r['code']}): {r.get('total', r.get('reason', ''))}")

    # 写运行日志
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "command": f"python pipeline/run.py {'--code ' + args.code if args.code else ''}",
        "results": results,
    }
    log_path = PROJECT_ROOT / "logs" / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_entry, f, ensure_ascii=False, indent=2)
    print(f"\n  日志: {log_path}")

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
