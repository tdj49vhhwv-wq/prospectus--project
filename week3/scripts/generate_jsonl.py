#!/usr/bin/env python3
"""
生成 Week 2 JSONL — 两类基础事实记录（行级粒度）

1. subscription_flow — 认缴流量: 每行 = 一个认购方在一次增资中的认购
2. equity_snapshot  — 股权存量: 每行 = 一个股东在一个时点的持仓

8 家公共样本: MB001/MB002/GEM001/GEM002/STAR001/STAR002/BSE001/BSE002
"""
import sys
import json
import re
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

# 优先使用自动提取
try:
    from auto_extract import auto_extract_all as auto_extract
    HAS_AUTO = True
except ImportError:
    HAS_AUTO = False

OUTPUTS_DIR = PROJECT_ROOT / "outputs"
JSONL_DIR = OUTPUTS_DIR / "week2_jsonl"
JSONL_DIR.mkdir(parents=True, exist_ok=True)

# 8 家
TARGET = {
    "三联锻造": {"code": "001282", "full": "芜湖三联锻造股份有限公司", "src": "manual"},
    "友升股份": {"code": "603418", "full": "上海友升铝业股份有限公司", "src": "manual"},
    "黄山谷捷": {"code": "301581", "full": "黄山谷捷股份有限公司", "src": "manual"},
    "云汉芯城": {"code": "301563", "full": "云汉芯城（上海）互联网科技股份有限公司", "src": "manual"},
    "赛分科技": {"code": "688758", "full": "苏州赛分科技股份有限公司", "src": "manual"},
    "影石创新": {"code": "688775", "full": "影石创新科技股份有限公司", "src": "manual"},
    "三协电机": {"code": "920100", "full": "常州三协电机股份有限公司", "src": "manual"},
    "星图测控": {"code": "920116", "full": "中科星图测控技术股份有限公司", "src": "manual"},
}

def load_structured(name):
    """加载手动提取的结构化 JSON"""
    path = OUTPUTS_DIR / name / f"{name}_融资历史_结构化.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("financing_events", [])



def build_subscription_flows(events, info):
    """从融资事件拆出认缴流量（每投资人一行）"""
    rows = []
    for ev in events:
        date_str = ev.get("event_date", "")
        evidence = ev.get("evidence_text", "")
        src_page = ev.get("source_page", "待补充")
        investors = ev.get("investors", [])
        total_amt = ev.get("total_investment_amount")
        share_price = ev.get("share_price")
        ev_type = ev.get("event_type", "")
        post_val = ev.get("post_money_valuation")

        for inv in investors:
            inv_amt = inv.get("investment_amount")
            if inv_amt is None and len(investors) == 1 and total_amt:
                inv_amt = total_amt

            # 尝试从 evidence 提取增资后总股本
            post_shares = None
            post_capital = None
            cap_match = re.search(r'(?:增资后.*?股本|注册资本)[^\d]*?([\d,]+\.?\d*)\s*万', evidence)
            if cap_match:
                post_capital = float(cap_match.group(1).replace(",", ""))

            rows.append({
                "record_type": "subscription_flow",
                "company_name": info["full"],
                "stock_code": info["code"],
                "source_page": src_page,
                "subscription_date": date_str,
                "subscriber_name": inv.get("investor_original_name", inv.get("investor_short_name", "未知")),
                "shares_subscribed": inv.get("shares_acquired"),
                "amount_subscribed": inv_amt,
                "price_per_share": share_price,
                "event_context": ev_type,
                "post_event_total_shares": post_shares,
                "post_event_total_capital": post_capital,
                "subscription_ratio": inv.get("shareholding_ratio_after_event"),
                "evidence_text": evidence[:800],
                "notes": ev.get("notes", ""),
            })
    return rows


def build_equity_snapshots(events, info):
    """从融资事件中抽取股权结构快照（有持股比例的行）"""
    rows = []
    seen_snapshots = set()

    for ev in events:
        investors = ev.get("investors", [])
        # 只抽取有持股比例的事件（说明PDF披露了该时点的股权结构）
        has_ratios = any(inv.get("shareholding_ratio_after_event") for inv in investors)
        if not has_ratios:
            continue

        date_str = ev.get("event_date", "")
        ev_type = ev.get("event_type", "")
        inferred = ev.get("inferred_round", "")
        if inferred and inferred != "未披露":
            snap_type = f"{ev_type}后（{inferred}）"
        else:
            snap_type = f"{ev_type}后"

        snap_key = f"{date_str}_{snap_type}"
        if snap_key in seen_snapshots:
            continue
        seen_snapshots.add(snap_key)

        src_page = ev.get("source_page", "待补充")
        evidence = ev.get("evidence_text", "")

        # 尝试从 evidence 中提取总股本/注册资本
        total_shares = None
        total_capital = None

        post_val = ev.get("post_money_valuation")
        if post_val:
            cap_match = re.search(r'注册资本[^\d]*?([\d,]+\.?\d*)\s*万', evidence)
            if cap_match:
                total_capital = float(cap_match.group(1).replace(",", ""))

        snap_order = len(seen_snapshots)  # t0=0, t1=1, ...

        for inv in investors:
            ratio = inv.get("shareholding_ratio_after_event")
            if not ratio:
                continue
            # 推断股东类型
            inv_name = inv.get("investor_original_name", "")
            inv_type = "其他"
            if "有限合伙" in inv_name or "基金" in inv_name or "创投" in inv_name or "投资" in inv_name:
                inv_type = "外部PE"
            elif "员工" in inv_name or "持股平台" in inv_name:
                inv_type = "员工持股平台"
            elif inv.get("investor_type") == "自然人":
                inv_type = "自然人"
            elif inv.get("investor_type") == "PE":
                inv_type = "外部PE"
            elif inv.get("investor_type") == "VC":
                inv_type = "外部VC"
            elif inv.get("investor_type") == "产业资本":
                inv_type = "产业资本"
            elif inv.get("investor_type") == "政府基金":
                inv_type = "政府基金"

            rows.append({
                "record_type": "equity_snapshot",
                "company_name": info["full"],
                "stock_code": info["code"],
                "source_page": src_page,
                "snapshot_date": date_str,
                "snapshot_type": snap_type,
                "total_shares": total_shares,
                "total_capital": total_capital,
                "shareholder_name": inv.get("investor_original_name", inv.get("investor_short_name", "未知")),
                "shares_held": inv.get("shares_acquired"),
                "capital_contribution": inv.get("investment_amount"),
                "shareholding_ratio": ratio,
                "snapshot_order": snap_order,
                "shareholder_type_detail": inv_type,
                "is_original_founder": "yes" if snap_order == 0 else "unknown",
                "evidence_text": evidence[:800],
                "notes": ev.get("notes", ""),
            })

    return rows


def main():
    print("=" * 60)
    print("Week 2 JSONL 生成 (subscription_flow + equity_snapshot)")
    if HAS_AUTO:
        print("数据源: 自动提取 (auto_extract) + 手动补充")
    else:
        print("数据源: 手动结构化数据")
    print("=" * 60)

    # 先跑自动提取
    auto_results = {}
    if HAS_AUTO:
        print("\n>>> 自动提取中...")
        auto_results = auto_extract()

    stats = {}

    for name, info in TARGET.items():
        print(f"\n处理: {name} ({info['code']}) [{info['src']}]")

        # 自动提取结果 (作为兜底)
        auto_flows = auto_results.get(name, {}).get("flows", []) if name in auto_results else []
        auto_snaps = auto_results.get(name, {}).get("snaps", []) if name in auto_results else []

        # 所有8家公司统一从结构化JSON加载
        events = load_structured(name)

        if events:
            sub_flows = build_subscription_flows(events, info)
            eq_snaps = build_equity_snapshots(events, info)
        elif auto_flows or auto_snaps:
            all_rows = auto_flows + auto_snaps
            out = JSONL_DIR / f"{info['code']}_{name}.jsonl"
            with open(out, "w", encoding="utf-8") as f:
                for row in all_rows:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            stats[name] = {"code": info["code"], "subscription_flow": len(auto_flows),
                          "equity_snapshot": len(auto_snaps), "src": "auto_fallback"}
            print(f"  -> {out.name}: {len(auto_flows)} flows + {len(auto_snaps)} snaps (自动兜底)")
            continue

        all_rows = sub_flows + eq_snaps

        out = JSONL_DIR / f"{info['code']}_{name}.jsonl"
        with open(out, "w", encoding="utf-8") as f:
            for row in all_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

        stats[name] = {
            "code": info["code"],
            "subscription_flow": len(sub_flows),
            "equity_snapshot": len(eq_snaps),
            "src": info["src"],
        }
        print(f"  -> {out.name}: {len(sub_flows)} 认缴流量 + {len(eq_snaps)} 股权存量")

    # 汇总
    total_sub = sum(s["subscription_flow"] for s in stats.values())
    total_eq = sum(s["equity_snapshot"] for s in stats.values())
    print(f"\n汇总: {len(stats)} 家公司, {total_sub} 条认缴流量, {total_eq} 条股权存量")

    summary_path = JSONL_DIR / "_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "record_types": ["subscription_flow", "equity_snapshot"],
            "total_companies": len(stats),
            "companies": stats,
        }, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
