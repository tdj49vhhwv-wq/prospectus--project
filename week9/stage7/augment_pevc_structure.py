#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from collections import defaultdict

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "week6" / "pipeline"))
from markdown_source import make_located_data  # noqa

COMPANIES = [
    ("001282", "三联锻造"), ("301563", "云汉芯城"), ("301581", "黄山谷捷"),
    ("603418", "友升股份"), ("688758", "赛分科技"), ("688775", "影石创新"),
    ("920100", "三协电机"), ("920116", "星图测控"),
]

BAD = (
    "议案","审议","认购人","认购数量","认购金额","新增股本","新增股份",
    "注册资本","股本","股东大会","董事会","协议","报告","合计","总计",
    "发行人","本公司","公司网址","互联网网址","营业执照","净资产",
)

LEGAL_OR_FUND = (
    "有限公司","股份有限公司","合伙企业","投资中心","管理中心","基金",
    "创投","投资","资本","私募","FUND","LLC","LIMITED","L.P.","LP",
)

def norm(s):
    s = str(s or "").strip().replace("（","(").replace("）",")")
    s = re.sub(r"\s+", " ", s)
    return s.strip(" ，。；、|:：")

def event_month(d):
    return str(d or "")[:7]

def month_patterns(ym):
    if not ym or len(ym) < 7:
        return []
    y, m = ym.split("-")
    mi = str(int(m))
    return [
        f"{y}年{mi}月", f"{y} 年 {mi} 月",
        f"{y}年 {mi} 月", f"{y} 年{mi}月",
    ]

def plausible_name(name):
    n = norm(name)
    if len(n) < 2 or len(n) > 100:
        return False
    if any(x in n for x in BAD):
        return False
    if re.fullmatch(r"[\d\s,.\-%/]+", n):
        return False
    if n in ("名称","姓名","股东","新增股东","投资人","认购方","出资方","（待识别）"):
        return False
    # full legal/institution name
    if any(x.upper() in n.upper() for x in LEGAL_OR_FUND):
        return True
    # English investment entity
    if re.search(r"[A-Za-z]", n) and re.search(r"(FUND|LLC|LIMITED|CAPITAL|VENTURE|INVEST)", n, re.I):
        return True
    # short Chinese entity name is allowed only when directly attached to an investment action
    if re.fullmatch(r"[一-龥A-Za-z0-9·&\-]{4,30}", n):
        return True
    return False

def split_names(chunk):
    c = norm(chunk)
    c = re.sub(r"(?:共同)?(?:增资|认购|认缴|出资).*$", "", c)
    parts = re.split(r"[、；;]|(?:，|,)(?=[一-龥A-Za-z])|(?:和|及|与)(?=[一-龥A-Za-z])", c)
    out = []
    for p in parts:
        p = norm(p)
        if plausible_name(p):
            out.append(p)
    return out

def parse_num(s):
    try:
        return float(str(s).replace(",",""))
    except Exception:
        return None

def parse_clause_fields(clause):
    amount = shares = price = None
    ma = re.search(r"(?:认购金额|投资金额|出资金额)?\s*([\d,]+(?:\.\d+)?)\s*万元", clause)
    if ma:
        amount = parse_num(ma.group(1))
    ms = re.search(r"(?:认购|新增|取得)?\s*([\d,]+(?:\.\d+)?)\s*万股", clause)
    if ms:
        shares = parse_num(ms.group(1))
    else:
        ms = re.search(r"(?:认购|新增|取得)?\s*([\d,]+(?:\.\d+)?)\s*股", clause)
        if ms:
            v = parse_num(ms.group(1))
            shares = v/10000 if v is not None else None
    mp = re.search(r"(?:股份价格|认购价格|每股价格|发行价格)[约为：:\s]*([\d,]+(?:\.\d+)?)\s*元/股", clause)
    if mp:
        price = parse_num(mp.group(1))
    return amount, shares, price

def extract_from_block(text):
    """Structure-first: return [(name, amount, shares, price, evidence)]."""
    text = str(text or "").replace("\r","")
    facts = []

    # A. Semicolon / sentence clauses with one investor per clause.
    clauses = [c.strip() for c in re.split(r"[；;\n]|(?<=万元)。|(?<=万股)。", text) if c.strip()]
    for clause in clauses:
        # name + amount + investment action
        patterns = [
            r"([一-龥A-Za-z0-9&（）()·,\.\-\s]{2,100}?)\s*以(?:现金)?\s*([\d,]+(?:\.\d+)?)\s*万元(?:等值美元)?\s*(?:认缴|认购|出资)",
            r"([一-龥A-Za-z0-9&（）()·,\.\-\s]{2,100}?)\s*(?:认购|认缴)\s*([\d,]+(?:\.\d+)?)\s*(?:股|万股)",
            r"([一-龥A-Za-z0-9&（）()·,\.\-\s]{2,100}?)\s*(?:认购|认缴|出资)[^。；]{0,100}?认购金额\s*([\d,]+(?:\.\d+)?)\s*万元",
        ]
        matched = False
        for pat in patterns:
            mm = re.search(pat, clause)
            if not mm:
                continue
            name = norm(mm.group(1))
            # strip discourse prefixes and table headers
            name = re.sub(r"^(?:本次增资具体情况如下[:：]?|上述新增股东|其中|由|新增股东)", "", name).strip()
            if plausible_name(name):
                amount, shares, price = parse_clause_fields(clause)
                # first pattern's numeric is amount if parser did not capture it due wording
                if amount is None and "万元" in clause and "认购" in clause:
                    amount = parse_num(mm.group(2))
                facts.append((name, amount, shares, price, clause[:500]))
                matched = True
                break

        if matched:
            continue

        # B. coordinated list before "共同增资/共同出资"
        mm = re.search(r"([一-龥A-Za-z0-9&（）()·、，,\.\-\s]{4,260}?)\s*(?:共同增资|共同出资)", clause)
        if mm:
            amount, shares, price = parse_clause_fields(clause)
            for name in split_names(mm.group(1)):
                facts.append((name, amount, shares, price, clause[:500]))

    # C. Markdown pipe-table rows.
    for line in text.splitlines():
        if "|" not in line:
            continue
        cells = [norm(x) for x in line.strip().strip("|").split("|")]
        if not cells:
            continue
        name = cells[0]
        if not plausible_name(name):
            continue
        joined = " ".join(cells[1:])
        amount, shares, price = parse_clause_fields(joined)
        facts.append((name, amount, shares, price, line[:500]))

    # D. HTML table rows.
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", text, flags=re.I|re.S):
        cells = [norm(re.sub(r"<[^>]+>", "", x)) for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.I|re.S)]
        if not cells:
            continue
        name = cells[0]
        if not plausible_name(name):
            continue
        joined = " ".join(cells[1:])
        amount, shares, price = parse_clause_fields(joined)
        facts.append((name, amount, shares, price, norm(re.sub(r"<[^>]+>", " ", tr))[:500]))

    # E. Dense enumeration like "源峰磐赛认购...；珠海峦恒认购..."
    dense_pat = re.compile(
        r"([一-龥A-Za-z0-9&（）()·,\.\-\s]{2,100}?)"
        r"(?:认购|认缴)\s*([\d,]+(?:\.\d+)?)\s*(股|万股)"
        r"[^；。\n]{0,100}?"
        r"(?:认购金额\s*([\d,]+(?:\.\d+)?)\s*万元)?"
    )
    for mm in dense_pat.finditer(text):
        name = norm(mm.group(1))
        # prevent swallowing previous sentence prefix
        name = re.split(r"[：:。；;]", name)[-1].strip()
        if not plausible_name(name):
            continue
        q = parse_num(mm.group(2))
        shares = q if mm.group(3) == "万股" else (q/10000 if q is not None else None)
        amount = parse_num(mm.group(4)) if mm.group(4) else None
        # local price may be global for whole event
        local = text[max(0, mm.start()-80):min(len(text), mm.end()+120)]
        _, _, price = parse_clause_fields(local)
        facts.append((name, amount, shares, price, mm.group(0)[:500]))

    # deterministic dedupe
    out, seen = [], set()
    for f in facts:
        k = (norm(f[0]).upper(), f[1], f[2], f[3])
        if k in seen:
            continue
        seen.add(k)
        out.append(f)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    for code, cname in COMPANIES:
        p = args.base / f"{code}_subscription_flow.jsonl"
        if not p.exists():
            continue
        rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]

        located = make_located_data(code, cname)
        snippets = (located or {}).get("pevc_snippets", [])
        by_month = defaultdict(list)
        for r in rows:
            if r.get("event_context") in ("增资","增资及股权转让") and r.get("subscription_date"):
                by_month[event_month(r["subscription_date"])].append(r)

        added = []
        for ym, event_rows in by_month.items():
            pats = month_patterns(ym)
            blocks = []
            for i, sn in enumerate(snippets):
                txt = sn.get("text","")
                if any(p.replace(" ","") in txt.replace(" ","") for p in pats):
                    block = txt
                    if i + 1 < len(snippets):
                        block += "\n" + snippets[i+1].get("text","")
                    blocks.append((block, sn.get("pdf_page")))
            if not blocks:
                continue

            ev_type = event_rows[0].get("event_context")
            ev_date = event_rows[0].get("subscription_date")
            existing_names = {norm(r.get("subscriber_name")).upper() for r in rows
                              if event_month(r.get("subscription_date")) == ym and r.get("event_context") == ev_type}

            for block, page in blocks:
                for name, amount, shares, price, evidence in extract_from_block(block):
                    nk = norm(name).upper()
                    if nk in existing_names:
                        continue
                    existing_names.add(nk)
                    added.append({
                        "event_id": f"{code}_{ev_date.replace('-','')}_{ev_type}_S7_{len(added):03d}",
                        "company_name": cname,
                        "stock_code": code,
                        "subscription_date": ev_date,
                        "subscriber_name": name,
                        "shares_subscribed": shares,
                        "amount_subscribed": amount,
                        "price_per_share": price,
                        "event_context": ev_type,
                        "investor_type": "PE_candidate",
                        "source_page": f"MD p{page}" if page else "MD",
                        "evidence_text": evidence,
                        "data_source": "markdown_extracted",
                        "extraction_method": "stage7_structure_first",
                        "rule_id": "S7_BLOCK",
                        "processing_status": "extracted",
                        "validation_status": "validated",
                        "confidence": "high",
                    })

        out_rows = rows + added
        out_rows.sort(key=lambda r: (r.get("subscription_date",""), r.get("event_context",""), r.get("subscriber_name","")))
        (args.out / p.name).write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out_rows),
            encoding="utf-8"
        )
        print(f"{code}: base={len(rows)} added={len(added)} total={len(out_rows)}")

if __name__ == "__main__":
    main()
