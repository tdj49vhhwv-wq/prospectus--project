#!/usr/bin/env python3
"""汇总新公司候选层 A 的只读运行结果，生成 summary.csv 与 README.md。"""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = PROJECT_ROOT / "week6" / "auto_output_md_new"
BATCH_DIR = Path(__file__).resolve().parent

NEW_COMPANIES = {
    "688411": "海博思创", "688545": "兴福电子", "688583": "思看科技",
    "688727": "恒坤新材", "688729": "屹唐股份", "688755": "汉邦科技",
    "688757": "胜科纳米", "688759": "必贝特", "688765": "禾元生物",
    "688783": "西安奕材", "688790": "昂瑞微", "688796": "百奥赛图",
    "688805": "健信超导", "688807": "优迅股份", "688809": "强一股份",
}


def load_rows(layer: str) -> dict[str, list[dict]]:
    out = {}
    for code in NEW_COMPANIES:
        path = OUT_DIR / layer / f"{code}_subscription_flow.jsonl"
        rows = []
        if path.exists():
            with open(path, encoding="utf-8") as f:
                rows = [json.loads(line) for line in f if line.strip()]
        out[code] = rows
    return out


def main() -> None:
    candidates = load_rows("candidate")
    validated = load_rows("validated")
    summary = []
    for code, name in NEW_COMPANIES.items():
        cand = candidates[code]
        val = validated[code]
        no_date = sum(1 for r in cand if not r.get("subscription_date"))
        seen = set()
        dups = 0
        for r in cand:
            key = (r.get("subscription_date"), r.get("event_context"), r.get("subscriber_name"))
            if key in seen:
                dups += 1
            seen.add(key)
        dup_rate = dups / len(cand) if cand else 0
        types = Counter(r.get("event_context") for r in val)
        summary.append({
            "stock_code": code,
            "company_name": name,
            "candidate_rows": len(cand),
            "validated_rows": len(val),
            "missing_date_candidates": no_date,
            "duplicate_candidate_rate": round(dup_rate, 4),
            "validated_type_counts": ";".join(f"{k}:{v}" for k, v in sorted(types.items())),
        })

    with open(BATCH_DIR / "summary.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(summary)

    total_cand = sum(s["candidate_rows"] for s in summary)
    total_val = sum(s["validated_rows"] for s in summary)
    total_no_date = sum(s["missing_date_candidates"] for s in summary)
    lines = [
        "# 新公司候选层 A：只读运行汇总（Week 9 提前执行）",
        "",
        "**2026-08-07**：对 15 家可用 Markdown 新公司（19 家候选剔除 8 家开发与 2 家盲测）",
        "跑只读候选层，输出 `week6/auto_output_md_new/`（gitignore，不入库、不标 Gold、不进 Final）。",
        f"盲测两家 688795/688802 保持隔离，未运行规则。",
        "",
        f"总计：候选 {total_cand} 条 / validated {total_val} 条；缺日期候选 {total_no_date} 条。",
        "",
        "| 代码 | 公司 | 候选 | validated | 缺日期候选 | 重复候选率 | validated 类型分布 |",
        "|------|------|---:|---:|---:|---:|---|",
    ]
    for s in summary:
        lines.append(
            f"| {s['stock_code']} | {s['company_name']} | {s['candidate_rows']} | "
            f"{s['validated_rows']} | {s['missing_date_candidates']} | "
            f"{s['duplicate_candidate_rate']:.2%} | {s['validated_type_counts']} |"
        )
    lines += [
        "",
        "说明：该层为宽松正则候选，不能当作准确率；按决策只在 Week 10 后根据 Gold 评价。",
    ]
    (BATCH_DIR / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"total candidate={total_cand} validated={total_val} missing_date={total_no_date}")
    print(f"written: {BATCH_DIR / 'summary.csv'}, {BATCH_DIR / 'README.md'}")


if __name__ == "__main__":
    main()
