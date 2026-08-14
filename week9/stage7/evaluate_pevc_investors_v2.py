#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json, re
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]

PEVC_TYPES = ("PE","VC","CVC","产业资本","战略投资","券商直投","政府引导基金","国有资本","创投","私募")
EXCLUDED = ("自然人","控股股东","实际控制人","员工持股平台","其他")

ALIAS_GROUPS = [
    ["深圳市创新投资集团有限公司","深创投"],
    ["上海复星惟盈股权投资基金合伙企业(有限合伙)","复星惟盈"],
    ["上海金浦临港智能科技股权投资基金合伙企业(有限合伙)","金浦临港基金","金浦临港"],
    ["上海金浦科技创业股权投资基金合伙企业(有限合伙)","金浦科创基金","金浦科创"],
    ["深圳市稳正景明创业投资企业(有限合伙)","稳正景明"],
    ["深圳市稳正长泽创业投资企业(有限合伙)","长泽创投","稳正长泽"],
    ["武汉力源信息技术股份有限公司","力源信息"],
    ["丰利财富(北京)国际资本管理股份有限公司","丰利财富"],
    ["镇江红土创业投资有限公司","镇江红土"],
    ["昆山红土高新创业投资有限公司","昆山红土"],
    ["富海深湾(深圳)移动创新私募创业投资基金合伙企业(有限合伙)","富海深湾"],
    ["国科瑞华(北京)创业投资合伙企业(有限合伙)","国科瑞华"],
    ["中科贵银(贵州)创业投资中心(有限合伙)","中科贵银"],
    ["深圳南山富海中小企业发展基金合伙企业(有限合伙)","南山富海"],
    ["珠海拓域投资合伙企业(有限合伙)","珠海拓域"],
    ["火炬电子科技股份有限公司","火炬电子"],
    ["厦门西堤股权投资合伙企业(有限合伙)","厦门西堤"],
    ["中小企业发展基金(深圳有限合伙)","中小企业基金","中小企业发展基金"],
    ["源峰磐赛(深圳)股权投资中心(有限合伙)","源峰磐赛"],
    ["珠海峦恒投资合伙企业(有限合伙)","珠海峦恒"],
    ["高瓴祈睿医疗健康私募投资基金(有限合伙)","高瓴祈睿"],
    ["国药中生(上海)生物股权投资基金合伙企业(有限合伙)","国药中生"],
    ["国药二期(上海)生物医药投资中心(有限合伙)","国药二期"],
    ["珠海夏尔巴二期股权投资合伙企业(有限合伙)","夏尔巴二期"],
    ["甘李药业股份有限公司","甘李药业"],
    ["深圳市杉晖创业投资合伙企业(有限合伙)","杉晖创业"],
    ["上海杉创智至创业投资合伙企业(有限合伙)","杉创智至"],
    ["江西赣江新区财投晨源股权投资中心(有限合伙)","财投晨源"],
    ["深圳市达晨创程私募股权投资基金企业(有限合伙)","达晨创程"],
    ["杭州达晨创程股权投资基金合伙企业(有限合伙)","杭州达晨创程"],
    ["海南三亚达晨财汇私募股权投资基金合伙企业(有限合伙)","达晨财汇"],
]

BAD_AUTO = ("议案","审议","认购人","认购数量","认购金额","新增股本","新增股份","注册资本","股本","股东大会","董事会","协议","报告","合计","总计","（待识别）")

def norm(s):
    s = str(s or "").strip().upper().replace("（","(").replace("）",")")
    return re.sub(r"[\s\u3000]+","",s).strip("，。；、,;:")

A2C = {}
for g in ALIAS_GROUPS:
    c = norm(g[0])
    for x in g:
        A2C[norm(x)] = c

def canon(s):
    n = norm(s)
    return A2C.get(n, n)

def pevc_type(t):
    u = str(t or "").upper()
    if any(x.upper() in u for x in EXCLUDED):
        return False
    return any(x.upper() in u for x in PEVC_TYPES)

def date_ok(a,b):
    return str(a or "")[:7] == str(b or "")[:7] and bool(str(a or "")[:7])

def match_name(g,a):
    ng, na = canon(g), canon(a)
    if ng == na and ng:
        return True, "canonical_exact"
    # conservative same-event abbreviation containment
    if min(len(ng), len(na)) >= 4 and (ng in na or na in ng):
        return True, "same_event_containment"
    return False, ""

def load_master(path):
    out=[]
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r=json.loads(line)
            if pevc_type(r.get("investor_type")):
                out.append(r)
    return out

def in_master_event(r, master):
    for m in master:
        if str(m.get("stock_code")) != str(r.get("stock_code")):
            continue
        if not date_ok(r.get("event_date") or r.get("subscription_date"), m.get("date")):
            continue
        if str(r.get("event_type") or r.get("event_context")) != str(m.get("type")):
            continue
        return True
    return False

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--gold-details", type=Path, required=True)
    ap.add_argument("--auto-dir", type=Path, required=True)
    ap.add_argument("--master", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args=ap.parse_args()

    master=load_master(args.master)
    with args.gold_details.open(encoding="utf-8") as f:
        old=list(csv.DictReader(f))

    gold=[r for r in old if r.get("role")=="gold" and in_master_event(r,master)
          and not re.fullmatch(r"[一-龥]{2,4}", r.get("subscriber_name",""))]

    auto=[]
    for p in sorted(args.auto_dir.glob("*_subscription_flow.jsonl")):
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip(): continue
            x=json.loads(line)
            r={
                "stock_code":x.get("stock_code",""),
                "event_date":x.get("subscription_date",""),
                "event_type":x.get("event_context",""),
                "subscriber_name":x.get("subscriber_name",""),
                "amount":x.get("amount_subscribed",""),
                "shares":x.get("shares_subscribed",""),
                "price":x.get("price_per_share",""),
                "method":x.get("extraction_method",""),
            }
            if not in_master_event(r,master):
                continue
            if any(b in r["subscriber_name"] for b in BAD_AUTO):
                continue
            auto.append(r)

    used=set(); matches=[]
    for gi,g in enumerate(gold):
        for ai,a in enumerate(auto):
            if ai in used: continue
            if g["stock_code"]!=a["stock_code"] or g["event_type"]!=a["event_type"] or not date_ok(g["event_date"],a["event_date"]):
                continue
            ok,method=match_name(g["subscriber_name"],a["subscriber_name"])
            if ok:
                used.add(ai); matches.append((gi,ai,method)); break

    tp=len(matches); fp=len(auto)-tp; fn=len(gold)-tp
    p=tp/(tp+fp) if tp+fp else None
    r=tp/(tp+fn) if tp+fn else None
    f1=2*p*r/(p+r) if p and r else None

    rows=[]
    mg={gi:(ai,m) for gi,ai,m in matches}
    ma={ai:(gi,m) for gi,ai,m in matches}
    for gi,g in enumerate(gold):
        ai_m=mg.get(gi)
        rows.append({
            "role":"gold","status":"TP" if ai_m else "FN","stock_code":g["stock_code"],
            "event_date":g["event_date"],"event_type":g["event_type"],"raw_name":g["subscriber_name"],
            "canonical_name":canon(g["subscriber_name"]),
            "matched_name":auto[ai_m[0]]["subscriber_name"] if ai_m else "",
            "match_method":ai_m[1] if ai_m else "",
        })
    for ai,a in enumerate(auto):
        gi_m=ma.get(ai)
        rows.append({
            "role":"auto","status":"TP" if gi_m else "FP","stock_code":a["stock_code"],
            "event_date":a["event_date"],"event_type":a["event_type"],"raw_name":a["subscriber_name"],
            "canonical_name":canon(a["subscriber_name"]),
            "matched_name":gold[gi_m[0]]["subscriber_name"] if gi_m else "",
            "match_method":gi_m[1] if gi_m else "",
        })

    args.out.mkdir(parents=True,exist_ok=True)
    with (args.out/"pevc_eval_details.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    summary={"gold":len(gold),"auto":len(auto),"matched":tp,"precision":p,"recall":r,"f1":f1}
    (args.out/"pevc_eval_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")

    pct=lambda x:"N/A" if x is None else f"{x:.2%}"
    print("========================================")
    print(" Stage 7 PE/VC Evaluation v2")
    print("========================================")
    print("Gold PE/VC :",len(gold))
    print("Auto PE/VC :",len(auto))
    print("Matched    :",tp)
    print("Precision  :",pct(p))
    print("Recall     :",pct(r))
    print("F1         :",pct(f1))
    print("PE/VC F1>=90%:","PASS" if f1 is not None and f1>=.90 else "FAIL")

if __name__=="__main__":
    main()
