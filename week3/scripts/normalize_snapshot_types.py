#!/usr/bin/env python3
"""
统一 snapshot_type 为受控词汇

受控词汇:
  - 有限公司设立时 (t0, earliest identifiable equity structure)
  - XX轮增资后 (e.g., A轮增资后)
  - 股改后 / 整体变更后
  - 代持还原后
  - 股权转让后
  - IPO前 (pre-IPO snapshot)
  - 报告期初 (reporting period start)
  - 其他
"""
import sys
import json
import re
from pathlib import Path


def normalize_snapshot_type(raw: str, event_type: str, inferred_round: str = "") -> str:
    """将自由文本 snapshot_type 标准化为受控词汇"""
    raw = raw.strip()

    # IPO前
    if re.search(r'IPO前|发行前|招股说明书签署日', raw):
        return "IPO前"

    # 有限公司设立时
    if re.search(r'设立|设立时|公司设立|t0', raw) or (event_type == "设立" and not inferred_round):
        return "有限公司设立时"

    # 股改/整体变更
    if re.search(r'股改|股份改制|整体变更|变更为股份有限公司', raw):
        return "整体变更后"

    # 代持还原
    if re.search(r'代持还原|代持解除', raw):
        return "代持还原后"

    # 股权转让
    if re.search(r'股权转让', raw):
        return "股权转让后"

    # 各轮增资
    round_name = ""
    if inferred_round and inferred_round != "未披露":
        round_name = inferred_round
    elif re.search(r'天使轮|A轮|B轮|C轮|D轮|E轮|Pre-IPO', raw):
        m = re.search(r'(天使轮|A轮|B轮|C轮|D轮|E轮|Pre-IPO)', raw)
        round_name = m.group(1) if m else ""

    if round_name:
        return f"{round_name}增资后"

    # 增资
    if re.search(r'增资', raw):
        return "增资后"

    # 报告期初
    if re.search(r'报告期初', raw):
        return "报告期初"

    return raw


def normalize_jsonl(jsonl_path: str):
    """Normalize snapshot_type in a JSONL file"""
    path = Path(jsonl_path)
    with open(path, encoding="utf-8") as f:
        lines = [json.loads(ln) for ln in f if ln.strip()]

    fixed = 0
    for row in lines:
        if row.get("record_type") == "equity_snapshot":
            old = row.get("snapshot_type", "")
            new = normalize_snapshot_type(old, row.get("event_context", ""))
            if old != new:
                row["snapshot_type"] = new
                fixed += 1

    with open(path, "w", encoding="utf-8") as f:
        for row in lines:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    return fixed


if __name__ == "__main__":
    jsonl_dir = Path("/Users/zhaobingqing/GitHub/prospectus-pevc-project/outputs/week2_jsonl")
    total_fixed = 0
    for f in sorted(jsonl_dir.glob("*.jsonl")):
        fixed = normalize_jsonl(str(f))
        if fixed:
            print(f"  {f.stem}: {fixed} snapshot_type(s) normalized")
        total_fixed += fixed
    print(f"\nTotal: {total_fixed} snapshot_type(s) normalized across all companies")
