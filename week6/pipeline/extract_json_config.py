#!/usr/bin/env python3
"""
Week 6 – JSON配置驱动提取器 — 一套配置,跨公司复用
换公司只需改 located_sections, 不改代码
"""
import json, re, sys
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import *
import fitz

# ═══════════════════════════════════════════════
# JSON提取配置 — 换公司不改这里
# ═══════════════════════════════════════════════
EXTRACTION_RULES = {
    "增资_标准发行": {
        "anchors": ["发行价格","发行普通股","募集资金","增资价格","认购价格","定向发行","股票发行","增资.*元/股"],
        "extract": {
            "price": r"(?:发行价格|增资价格|认购价格)[为：:]?\s*([\d.]+)\s*元",
            "shares": r"(?:发行普通股|增发.*?股|新增.*?股|认购)\s*([\d,]+\.?\d*)\s*万股",
            "amount": r"(?:募集资金总额|增资.*?金额|认购金额)[为：:]?\s*([\d,]+\.?\d*)\s*万元",
            "date": r"(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)",
        }
    },
    "增资_验资报告": {
        "anchors": ["已收到","缴纳的出资款","验资报告","经审验","出资款"],
        "extract": {
            "investors_raw": r"已收到\s*(.+?)\s*(?:等?\d+名.*?认购|缴纳的出资款)",
            "amount": r"出资款\s*([\d,]+\.?\d*)\s*万元",
            "date": r"截至\s*(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)",
        }
    },
    "资本公积转增": {
        "anchors": ["资本公积","转增","每10股","权益分派"],
        "extract": {
            "ratio": r"每\s*10\s*股\s*转增\s*([\d.]+)\s*股",
            "shares": r"转增\s*([\d,]+\.?\d*)\s*万股",
            "date": r"(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)",
        }
    },
    "设立": {
        "anchors": ["成立日期","成立于","设立","注册资本"],
        "extract": {
            "date": r"(?:成立日期|成立于)\s*[:：]?\s*(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)",
            "registered_capital": r"注册资本\s*[:：]?\s*([\d,]+\.?\d*)\s*万",
        }
    },
    "股改": {
        "anchors": ["整体变更","折股","股份公司","股份有限公司"],
        "extract": {
            "net_assets": r"净资产[总计为]?\s*([\d,]+\.?\d*)\s*[万元]",
            "shares": r"折[为合].*?([\d,]+\.?\d*)\s*万股",
            "ratio_raw": r"按?\s*([\d.]+)\s*[:：]\s*([\d.]+)\s*[的]?比例折股",
            "date": r"(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日).*?(?:核准|登记|注册|营业执照)",
        }
    },
    "股权转让": {
        "anchors": ["股权转让","转让.*股权","代持.*解除","代持.*还原"],
        "extract": {
            "transferor": r"([一-龥]{2,20}(?:有限|合伙|企业|公司|投资|中心)?)\s*(?:将其所持|将其持有的)",
            "transferee": r"(?:转让给|转让予)\s*([一-龥]{2,20}(?:有限|合伙|企业|公司|投资|中心)?)",
            "date": r"(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)",
        }
    },
    "PE备案": {
        "anchors": ["备案编码","私募基金","基金管理人","SNG","SVU","P10"],
        "extract": {
            "filing_code": r"备案编码[为：:]?\s*(\w{6})",
            "fund_name": r"([一-龥]{2,20}(?:创业投资|创投|股权投资)[一-龥]{0,20}(?:企业|基金|合伙))",
            "manager": r"基金管理人[为：:]?\s*([一-龥]{2,30}(?:有限(?:责任)?公司|管理有限公司|资产管理))",
        }
    },
}

def normalize_date(s):
    m = re.match(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', s)
    if m: return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})', s)
    if m: return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return s.strip()

def extract_from_text(text, page):
    """用JSON配置从文本中提取"""
    rows = []
    for rule_name, rule in EXTRACTION_RULES.items():
        # 找到第一个锚点词的位置
        anchor_pos = None
        for a in rule["anchors"]:
            pos = text.find(a)
            if pos >= 0:
                anchor_pos = pos
                break
        if anchor_pos is None:
            continue

        # 只取锚点周围800字符的窗口
        window_start = max(0, anchor_pos - 200)
        window_end = min(len(text), anchor_pos + 600)
        window = text[window_start:window_end]

        extracted = {}
        for field, pattern in rule["extract"].items():
            matches = list(re.finditer(pattern, window))
            if not matches:
                continue
            vals = []
            for m in matches:
                if field in ("date",):
                    vals.append(normalize_date(m.group(1)))
                elif field in ("price","shares","amount","ratio","registered_capital","net_assets"):
                    try:
                        vals.append(float(m.group(1).replace(",","")))
                    except: pass
                elif field == "ratio_raw":
                    try:
                        vals.append(f"{m.group(1)}:{m.group(2)}")
                    except: pass
                elif field == "investors_raw":
                    raw = m.group(1).strip()
                    # 拆分投资人
                    names = []
                    for part in re.split(r'[、，]', raw):
                        part = part.strip()
                        if '和' in part and len(part) > 4:
                            for sub in part.split('和'):
                                sub = sub.strip()
                                if re.match(r'^[一-龥A-Za-z\s]{2,30}$', sub):
                                    names.append(sub)
                        elif re.match(r'^[一-龥A-Za-z\s]{2,30}$', part):
                            names.append(part)
                    vals.append(names if names else [raw])
                else:
                    vals.append(m.group(1).strip()[:60])

            if vals:
                # 取第一个（最接近锚点的）
                extracted[field] = vals[0]

        if len(extracted) >= 1:
            extracted["rule"] = rule_name
            extracted["page"] = page
            rows.append(extracted)

    # 去重：同类型+同页只保留最完整的行
    deduped = {}
    for r in rows:
        key = (r["rule"], r["page"])
        if key not in deduped or len(r) > len(deduped[key]):
            deduped[key] = r
    return list(deduped.values())

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", type=str, required=True)
    parser.add_argument("--out", type=str, default=None)
    args = parser.parse_args()

    code = args.code
    located_path = OUTPUTS_DIR / f"located_sections_{code}.json"
    if not located_path.exists():
        print(f"✗ 找不到 {located_path}")
        return 1

    with open(located_path) as f:
        located = json.load(f)

    company = located["company"]
    pdf_path = PDF_DIR / company["pdf"]
    doc = fitz.open(str(pdf_path))

    # 逐页提取
    all_rows = []
    covered = located["statistics"]["covered_pages"]
    for p in covered:
        if 1 <= p <= len(doc):
            rows = extract_from_text(doc[p-1].get_text("text"), p)
            all_rows.extend(rows)

    doc.close()

    # 去重 + 添加元数据
    seen = set()
    unique = []
    for r in all_rows:
        key = (r.get("rule",""), r.get("page",0), str(r.get("date",""))[:10])
        if key not in seen:
            seen.add(key)
            r["company"] = company["name"]
            r["stock_code"] = code
            r["extracted_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            unique.append(r)

    # 输出
    out_dir = Path(args.out) if args.out else OUTPUTS_DIR / "batch_results" / code
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "extracted_events.jsonl"

    with open(out_path, "w", encoding="utf-8") as f:
        for r in unique:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 按类型统计
    from collections import Counter
    type_ct = Counter(r["rule"] for r in unique)
    print(f"✅ {company['name']}({code}): {len(unique)}条")
    for t, c in type_ct.most_common():
        print(f"   {t}: {c}")
    print(f"   → {out_path}")

    return 0

if __name__ == "__main__":
    sys.exit(main())