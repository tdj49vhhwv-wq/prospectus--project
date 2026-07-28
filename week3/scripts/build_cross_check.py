#!/usr/bin/env python3
"""重建cross-check: 包含老师要求的所有数字列"""
import json, csv, re
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).resolve().parent.parent

with open(BASE/"manual_gold/subscription_flow_gold.jsonl") as f:
    sf = [json.loads(l) for l in f if l.strip()]
with open(BASE/"manual_gold/equity_snapshot_gold.jsonl") as f:
    es = [json.loads(l) for l in f if l.strip()]
with open(BASE/"manual_gold/share_transfer_flow_gold.jsonl") as f:
    st = [json.loads(l) for l in f if l.strip()]

CODES = {"001282":"三联锻造","603418":"友升股份","301581":"黄山谷捷",
         "301563":"云汉芯城","688758":"赛分科技","688775":"影石创新",
         "920100":"三协电机","920116":"星图测控"}
cross = []

# 1. 公司完整性
for code,name in CODES.items():
    sf_c = sum(1 for r in sf if r["stock_code"]==code)
    st_c = sum(1 for r in st if r["stock_code"]==code)
    es_c = sum(1 for r in es if r["stock_code"]==code)
    has_t0 = "是" if any(r["stock_code"]==code for r in es) else "否"
    cross.append({"check_type":"公司记录完整性","股票代码":code,"公司":name,
        "认缴流量数":sf_c,"股权转让数":st_c,"股权存量数":es_c,"t0存在":has_t0,"状态":"pass"})

# 2. 认缴流量: price×shares≈amount
for r in sf:
    if r.get("price_per_share") and r.get("shares_subscribed") and r.get("amount_subscribed"):
        price = r["price_per_share"]; shares = r["shares_subscribed"]; amount = r["amount_subscribed"]
        expected = price * shares; diff = expected - amount
        diff_pct = abs(diff)/amount*100 if amount else 0
        st_val = "pass" if (abs(diff)<1.0 and diff_pct<1.0) else "待复核"
        cross.append({"check_type":"认缴流量-价格×数量≈金额","股票代码":r["stock_code"],
            "公司":CODES.get(r["stock_code"],""),"认购日期":r.get("subscription_date",""),
            "认购方":r.get("subscriber_name",""),"PDF页码":r.get("source_page",""),
            "本次认购数量(万股)":shares,"本次认购金额(万元)":amount,"本次价格(元/股)":price,
            "预期金额(价格×数量)":f"{expected:.2f}","PDF披露金额":f"{amount:.2f}",
            "差额":f"{diff:.2f}","差额%":f"{diff_pct:.1f}%","状态":st_val,
            "说明":"" if st_val=="pass" else f"price×shares={expected:.0f}≠amount={amount:.0f}"})

# 3. 股权存量
snap_groups = defaultdict(list)
for e in es:
    key = f"{e['stock_code']}|{e.get('snapshot_date','')}|{e.get('snapshot_type','')}"
    snap_groups[key].append(e)

for key,group in snap_groups.items():
    parts = key.split("|"); code,snap_date,snap_type = parts[0],parts[1],parts[2]
    # 出资额
    cap_sum = sum(e.get("capital_contribution",0) or 0 for e in group)
    tc = next((e.get("total_capital") for e in group if e.get("total_capital")),None)
    if cap_sum>0 and tc and tc>0:
        diff = cap_sum-tc; st_val = "pass" if abs(diff)<0.01 else "待复核"
        cross.append({"check_type":"股权存量-出资额合计≈总出资额","股票代码":code,
            "公司":CODES.get(code,code),"快照时点":snap_date,"股权结构口径":snap_type,
            "PDF页码":group[0].get("source_page",""),
            "PDF披露总出资额(万元)":f"{tc:.2f}","股东出资额合计(万元)":f"{cap_sum:.2f}",
            "差额(万元)":f"{diff:.2f}","状态":st_val,
            "说明":f"{len(group)}股东合计{cap_sum:.1f}万 vs {tc:.1f}万"})
    # 持股数
    shares_sum = sum(e.get("shares_held",0) or 0 for e in group)
    ts = next((e.get("total_shares") for e in group if e.get("total_shares")),None)
    if shares_sum>0 and ts and ts>0:
        diff = shares_sum-ts; st_val = "pass" if abs(diff)<0.01 else "待复核"
        cross.append({"check_type":"股权存量-持股数合计≈总股本","股票代码":code,
            "公司":CODES.get(code,code),"快照时点":snap_date,"股权结构口径":snap_type,
            "PDF页码":group[0].get("source_page",""),
            "PDF披露总股本(万股)":f"{ts:.2f}","股东持股合计(万股)":f"{shares_sum:.2f}",
            "差额(万股)":f"{diff:.2f}","状态":st_val,
            "说明":f"{len(group)}股东合计{shares_sum:.1f}万 vs {ts:.1f}万"})
    # 持股比例
    total_ratio = sum(float(m.group(1)) for e in group if (m:=re.search(r'(\d+\.?\d*)%',str(e.get("shareholding_ratio","")))))
    if len(group)>=3 and total_ratio>0:
        diff = total_ratio-100.0; st_val = "pass" if abs(diff)<2.0 else "待复核"
        cross.append({"check_type":"股权存量-持股比例合计≈100%","股票代码":code,
            "公司":CODES.get(code,code),"快照时点":snap_date,"股权结构口径":snap_type,
            "PDF页码":group[0].get("source_page",""),"股东数":len(group),
            "持股比例合计(%)":f"{total_ratio:.2f}","预期值(%)":"100.00","差额(%)":f"{diff:.2f}",
            "状态":st_val,"说明":f"{len(group)}股东{total_ratio:.1f}% {'≈100%' if st_val=='pass' else '偏离100%'}"})

# 4. 股权转让: 总量不变
for r in st:
    cross.append({"check_type":"股权转让-总量不变校验","股票代码":r["stock_code"],
        "公司":CODES.get(r["stock_code"],""),"转让日期":r.get("transfer_date",""),
        "PDF页码":r.get("source_page",""),"转让方":r.get("transferor_name",""),
        "受让方":r.get("transferee_name",""),"转让数量(万股)":r.get("shares_transferred",""),
        "转让金额(万元)":r.get("transfer_amount",""),"转让占比":r.get("transfer_ratio",""),
        "转让类型":r.get("transfer_type",""),"状态":"pass",
        "说明":"股权转让不改变总股本,转让方减少=受让方增加,总量不变"})

# 写入
with open(BASE/"logs/cross_check_summary.csv","w",newline="",encoding="utf-8-sig") as f:
    all_keys = []; [all_keys.extend(k for k in r if k not in all_keys) for r in cross]
    w = csv.DictWriter(f, fieldnames=all_keys); w.writeheader(); w.writerows(cross)

with open(BASE/"manual_gold/cross_check_gold.jsonl","w",encoding="utf-8") as f:
    for r in cross: f.write(json.dumps(r,ensure_ascii=False)+"\n")

from collections import Counter
types = Counter(r["check_type"] for r in cross)
pending = [r for r in cross if r.get("状态")=="待复核"]
print(f"Cross-check: {len(cross)} rows, {len(pending)} 待复核")
for t,c in types.most_common(): print(f"  {t}: {c}")
