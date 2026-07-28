#!/usr/bin/env python3
"""
Step 2: PE/VC 信息结构化提取（定位与抽取完全分离）

方法:
  1. 读取 Step1 输出的 located_sections.json
  2. 打开PDF，在定位到的页码范围进行精确提取
  3. PyMuPDF表格提取 + 正则文本提取 + PE基金详情
  4. 输出四类JSONL: subscription_flow / share_transfer_flow / equity_snapshot / pe_fund_detail

核心原则（来自老师要求）:
  - evidence_text 必须是PDF原文逐字摘录，不可概括
  - 数字只填PDF直接披露的，不强行倒推
  - 对不上的标记"待复核"
"""
import json
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import *

try:
    import fitz
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False


def log_step(step_name, status, detail=""):
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


# ── event_id 生成 ──
# 格式: {stock_code}_{prospectus_date}_{record_type_abbr}_{seq:03d}
# 例: 920100_20250711_sf_001

# 招股书日期（从TARGET配置提取）
PROSPECTUS_DATE = "20250711"  # 三协电机招股书签署日

def make_event_id(stock_code: str, record_type: str, seq: int) -> str:
    """生成统一 event_id"""
    abbr = RECORD_TYPE_ABBR.get(record_type, "xx")
    return f"{stock_code}_{PROSPECTUS_DATE}_{abbr}_{seq:03d}"

# 全局序列计数器（每个 record_type 独立）
_event_id_counters = {k: 0 for k in RECORD_TYPE_ABBR}

def next_event_id(stock_code: str, record_type: str) -> str:
    """生成下一个 event_id（自动递增序列号）"""
    _event_id_counters[record_type] += 1
    return make_event_id(stock_code, record_type, _event_id_counters[record_type])


def normalize_date(date_str: str) -> str:
    """中文日期 → YYYY-MM-DD"""
    m = re.match(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', date_str)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.match(r'(\d{4})\s*年\s*(\d{1,2})\s*月', date_str)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    # 尝试 YYYY-MM-DD
    m = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})', date_str)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return date_str.strip()


def classify_investor_type(name: str) -> str:
    """根据名称关键词分类投资人类型"""
    for itype, keywords in INVESTOR_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in name:
                return itype
    # 判断是否为机构
    if re.search(r'(有限|合伙|基金|创投|投资|集团|中心|公司|景明|长泽|资本|资产)', name):
        return "PE"  # 默认机构归PE
    # 纯自然人姓名（2-3个中文字符）
    if re.match(r'^[一-龥]{2,3}$', name):
        return "自然人"
    return "自然人"


def is_excluded_entity(name: str) -> bool:
    """判断是否为应排除的非投资人实体"""
    for kw in EXCLUDE_ENTITIES:
        if kw in name:
            return True
    return False


def extract_subscription_flows(doc, located_data: dict) -> list:
    """
    提取认缴流量 (SubscriptionFlow)

    从PE/VC候选片段中提取:
      - 2022年股票发行 (稳正景明 + 长泽创投 认购)
      - 2023年股票发行 (盛祎等15人 认购)
      - 设立出资 (盛祎 + 朱绶青)
      - 资本公积转增 (2023年权益分派)
    """
    rows = []
    company = located_data["company"]
    covered_pages = set(located_data["statistics"]["covered_pages"])

    # ── 从text snippet提取增资事件 ──
    patterns = [
        # 股票定向发行 (PE/VC重点)
        (r'(?:(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)|(\d{4}\s*年\s*\d{1,2}\s*月)).*?'
         r'股票定向发行.*?'
         r'发行价格[为：:]?\s*(\d+\.?\d*)\s*元/股.*?'
         r'发行普通股\s*(\d+[\d,]*\.?\d*)\s*万股.*?'
         r'募集资金总额[为：:]?\s*(\d+[\d,]*\.?\d*)\s*万元',
         '增资'),

        # 收到出资款 (验资报告描述)
        (r'截至\s*(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日).*?'
         r'已收到\s*(.+?)\s*缴纳的出资款\s*(\d+[\d,]*\.?\d*)\s*万元',
         '增资'),

        # 资本公积转增
        (r'(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日).*?'
         r'(?:资本公积|未分配利润).*?转增\s*(\d+[\d,]*\.?\d*)\s*万?股',
         '资本公积转增'),

        # 设立 (2002年成立)
        (r'(?:成立日期|成立于)\s*[:：]?\s*(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)',
         '设立'),
    ]

    for snippet in located_data["pevc_snippets"]:
        text = snippet["text"]
        page = snippet["pdf_page"]

        for pattern, ev_type in patterns:
            for m in re.finditer(pattern, text, re.DOTALL):
                groups = m.groups()
                # 找日期 (可能是group(1)或group(2))
                date_str = None
                for g in groups:
                    if g and re.search(r'\d{4}\s*年', g):
                        date_str = normalize_date(g)
                        break

                if not date_str:
                    continue

                # 提取数字字段（排除中文日期）
                amount = None
                shares = None
                price = None
                for g in groups:
                    if not g:
                        continue
                    # 排除日期（含中文字符）
                    if re.search(r'[年月日]', g):
                        continue
                    # 必须是纯数字（可含逗号和小数点）
                    if not re.match(r'^[\d,]+\.?\d*$', g.strip()):
                        continue
                    try:
                        val = float(g.replace(',', ''))
                    except ValueError:
                        continue

                    ctx = text[max(0, m.start()-100):m.end()]
                    if '万股' in ctx and shares is None:
                        shares = val
                    elif '元/股' in ctx and price is None:
                        price = val
                    elif amount is None:
                        amount = val

                # 对于设立事件，从原文中提取认缴额
                if ev_type == "设立" and amount is None:
                    reg_cap = re.search(r'注册资本\s*[:：]?\s*(\d+[\d,]*\.?\d*)\s*万', text)
                    if reg_cap:
                        amount = float(reg_cap.group(1).replace(',', ''))

                # 提取认购方
                investors = list(set(re.findall(
                    r'([一-龥a-zA-Z]{2,30}'
                    r'(?:有限(?:责任)?公司|合伙企业|基金|创投|投资|集团|中心|管理))',
                    text[m.start():m.end()]
                )))

                # 从受到出资款描述中提取认购方列表
                name_list = re.findall(
                    r'已收到\s*(.+?)\s*(?:等\d+名\s*认购人|缴纳)',
                    text[m.start():min(m.end()+200, len(text))]
                )
                if name_list:
                    raw_names = name_list[0]
                    # 拆分（中英文混合名称）
                    if '、' in raw_names or '，' in raw_names:
                        investors.extend(re.split(r'[、，]', raw_names))
                    else:
                        investors.append(raw_names)

                if not investors:
                    # 特殊处理：三协电机设立
                    if ev_type == "设立":
                        founders = re.findall(r'(盛[一-龥]{1,2})', text[:500])
                        investors.extend(founders)

                # 原文证据
                evidence = text[max(0, m.start()-20):min(len(text), m.end()+100)].strip()

                for inv in investors[:8]:  # 每事件最多8个投资人
                    inv = inv.strip()
                    if not inv or len(inv) < 2 or is_excluded_entity(inv):
                        continue

                    # 过滤：排除PE基金管理人/GP自身设立事件
                    # (如"稳正资产管理有限公司成立于2013年")
                    if ev_type == "设立":
                        if re.search(r'(资产管理|基金管理).*?成立于', evidence):
                            continue
                        # 排除注册资本明显不是三协电机的事件
                        # (三协电机注册资本5310.93万, PE基金注册资本通常不同)
                        if amount and amount < 6000 and re.search(r'(创业投资|股权投资|私募|基金管理|资产管理)', evidence):
                            continue

                    rows.append({
                        "event_id": next_event_id(company["code"], "subscription_flow"),
                        "processing_status": "EXTRACTED",
                        "status_detail": None,
                        "traceability": "pdf_disclosed",
                        "extracted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "record_type": "subscription_flow",
                        "company_name": company["name"],
                        "stock_code": company["code"],
                        "source_page": f"PDF p{page}",
                        "subscription_date": date_str,
                        "subscriber_name": inv,
                        "shares_subscribed": shares,
                        "amount_subscribed": amount,
                        "price_per_share": price,
                        "event_context": ev_type,
                        "investor_type": classify_investor_type(inv),
                        "evidence_text": evidence[:500],
                        "data_source": "pdf_disclosed",
                        "notes": f"auto_extracted_week4 | snippet_keyword={snippet['keyword']}",
                    })

    # ── 去重 ──
    seen = set()
    unique = []
    for r in rows:
        key = (r["subscription_date"], r["subscriber_name"], r["event_context"])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def extract_equity_snapshots_from_tables(doc, located_data: dict) -> list:
    """
    从PDF表格中提取股权结构快照 (EquitySnapshot)

    利用 PyMuPDF find_tables() 精确提取股东持股表格:
      - p35-36: IPO前/后股东持股表
      - p37-38: 股东限售/持股详情表
    """
    rows = []
    company = located_data["company"]
    covered_pages = set(located_data["statistics"]["covered_pages"])

    # 确定目标页面范围
    target_pages = sorted(covered_pages)

    for page_num in target_pages:
        if page_num < 1 or page_num > len(doc):
            continue

        page = doc[page_num - 1]  # fitz是0-indexed
        tables = page.find_tables()

        if not tables or not tables.tables:
            continue

        page_text = page.get_text("text")

        # 判断是否包含股东信息
        if not re.search(r'股东|持股|股权|持股比例', page_text[:500]):
            continue

        # 尝试找快照日期
        date_match = re.search(
            r'截至\s*(?:本招股说明书签署日|(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日))',
            page_text
        )
        if date_match:
            snap_date = "2025-07-11" if "招股说明书签署日" in date_match.group(0) else normalize_date(date_match.group(1))
        else:
            snap_date = "2025-07-11"  # 默认招股书签署日

        for table in tables.tables:
            data = table.extract()
            if not data or len(data) < 2:
                continue

            # 解析表格：找表头行判断列含义
            header_row = None
            for i, row in enumerate(data):
                row_text = "".join([str(c) if c else "" for c in row])
                if re.search(r'股东|持股比例|股数|持股数量', row_text):
                    header_row = i
                    break

            if header_row is None:
                continue

            # 确定列索引
            header = [str(c).strip() if c else "" for c in data[header_row]]
            name_col = None
            shares_col = None
            ratio_col = None

            for i, h in enumerate(header):
                if re.search(r'股东|姓名|名称', h):
                    name_col = i
                elif re.search(r'持股数量|股数|持股.*万股', h):
                    shares_col = i
                elif re.search(r'持股比例|比例.*%', h):
                    ratio_col = i

            if name_col is None:
                continue

            # 提取数据行
            for row in data[header_row + 1:]:
                if len(row) <= name_col:
                    continue

                name = str(row[name_col]).strip() if row[name_col] else ""
                if not name or len(name) < 2:
                    continue

                # 排除非股东行
                if re.search(r'合计|总计|序号|股东姓名|发行对象|现有其他股东', name):
                    continue
                # 排除关联关系表（含"、"的合并名称）
                if '、' in name or '，' in name:
                    continue
                # 排除非投资人实体
                if is_excluded_entity(name):
                    continue

                shares = None
                if shares_col is not None and len(row) > shares_col and row[shares_col]:
                    try:
                        val = str(row[shares_col]).replace(',', '').strip()
                        if val:
                            shares = float(val)
                    except ValueError:
                        pass

                ratio = None
                if ratio_col is not None and len(row) > ratio_col and row[ratio_col]:
                    ratio_val = str(row[ratio_col]).strip()
                    if ratio_val and re.search(r'\d', ratio_val):
                        if '%' not in ratio_val:
                            ratio_val += '%'
                        ratio = ratio_val

                # 如果所有列都没解析到，尝试从整行文本推断
                if ratio is None and shares is None:
                    # 遍历所有列找百分比和数字
                    for j, cell in enumerate(row):
                        if j == name_col:
                            continue
                        cell_str = str(cell).strip() if cell else ""
                        if re.match(r'^\d+\.?\d*%?$', cell_str):
                            if '%' in cell_str and ratio is None:
                                ratio = cell_str
                            elif shares is None:
                                try:
                                    shares = float(cell_str.replace(',', ''))
                                except ValueError:
                                    pass

                # 证据文本：取表格所在页的前500字符 + 表格行内容
                evidence = page_text[:500].strip()

                rows.append({
                    "event_id": next_event_id(company["code"], "equity_snapshot"),
                    "processing_status": "EXTRACTED",
                    "status_detail": None,
                    "traceability": "pdf_disclosed",
                    "extracted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "record_type": "equity_snapshot",
                    "company_name": company["name"],
                    "stock_code": company["code"],
                    "source_page": f"PDF p{page_num}",
                    "snapshot_date": snap_date,
                    "snapshot_type": "IPO前" if "发行前" in str(data[header_row]) else "招股书签署日",
                    "total_shares": 5310.93,  # 注册资本
                    "total_capital": 5310.93,  # 万元
                    "shareholder_name": name,
                    "shares_held": shares,
                    "capital_contribution": None,
                    "shareholding_ratio": ratio,
                    "shareholder_type_detail": classify_investor_type(name),
                    "evidence_text": evidence[:500],
                    "data_source": "pdf_disclosed",
                    "notes": f"table_extracted_p{page_num}",
                })

    # 去重（同股东名+同快照日期）
    seen = set()
    unique = []
    for r in rows:
        key = (r["snapshot_date"], r["shareholder_name"])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def extract_pe_fund_details(doc, located_data: dict) -> list:
    """
    提取PE基金详情 (PE Fund Detail)

    专门提取PE/VC机构的结构化信息:
      - 基金全称、备案编码
      - GP/LP结构
      - 管理人信息
      - 基金规模
    """
    rows = []
    company = located_data["company"]
    covered_pages = set(located_data["statistics"]["covered_pages"])

    # ── 从文本中提取PE基金备案信息 ──
    for snippet in located_data["pevc_snippets"]:
        text = snippet["text"]
        page = snippet["pdf_page"]

        # 基金备案信息
        fund_matches = re.findall(
            r'([一-龥]{2,30}(?:创业投资|股权投资|创投).{0,20}?(?:企业|基金|中心)'
            r'(?:有限合伙|有限公司)?).*?'
            r'备案编码[为：:]?\s*(\w{6})',
            text, re.DOTALL
        )

        for fund_name, filing_code in fund_matches:
            # 提取管理人
            mgr_match = re.search(
                r'基金管理人[为：:]?\s*([一-龥]{2,30}(?:有限(?:责任)?公司|管理有限公司))',
                text
            )
            manager = mgr_match.group(1) if mgr_match else None

            # 提取备案日期
            date_match = re.search(
                r'(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日).*?完成.*?备案',
                text
            )
            filing_date = normalize_date(date_match.group(1)) if date_match else None

            rows.append({
                "event_id": next_event_id(company["code"], "pe_fund_detail"),
                "processing_status": "EXTRACTED",
                "status_detail": None,
                "traceability": "pdf_disclosed",
                "extracted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "record_type": "pe_fund_detail",
                "company_name": company["name"],
                "stock_code": company["code"],
                "source_page": f"PDF p{page}",
                "fund_name": fund_name.strip(),
                "filing_code": filing_code,
                "filing_date": filing_date,
                "fund_manager": manager,
                "fund_type": classify_investor_type(fund_name),
                "gp_name": None,
                "lp_names": [],
                "fund_size": None,
                "evidence_text": text[:500].strip(),
                "data_source": "pdf_disclosed",
                "notes": f"auto_extracted_week4",
            })

    # ── 从PDF表格提取GP/LP结构（p35 table） ──
    if 34 < len(doc):  # page 35 = index 34
        page = doc[34]  # 0-indexed
        tables = page.find_tables()
        if tables and tables.tables:
            for table in tables.tables:
                data = table.extract()
                lp_entries = []
                for row in data:
                    row_text = "".join([str(c) if c else "" for c in row])
                    if re.search(r'有限合伙人|普通合伙人|管理有限公司', row_text):
                        lp_entries.append(row)

                if lp_entries:
                    # 将GP/LP信息附加到对应的PE基金记录
                    for fund_row in rows:
                        if "稳正" in fund_row["fund_name"]:
                            for entry in lp_entries:
                                entry_text = " | ".join([str(c).strip() if c else "" for c in entry])
                                if "普通合伙人" in entry_text:
                                    gp_match = re.search(r'([一-龥]{2,30}(?:有限(?:责任)?公司|管理有限公司))', entry_text)
                                    if gp_match:
                                        fund_row["gp_name"] = gp_match.group(1)
                                elif "有限合伙人" in entry_text:
                                    name_match = re.search(r'([一-龥]{2,10})\s*有限合伙人', entry_text)
                                    ratio_match = re.search(r'(\d+\.?\d*%)', entry_text)
                                    if name_match:
                                        fund_row["lp_names"].append({
                                            "name": name_match.group(1),
                                            "ratio": ratio_match.group(1) if ratio_match else None
                                        })

    # 去重
    seen = set()
    unique = []
    for r in rows:
        key = (r["fund_name"], r["filing_code"])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def extract_share_transfers(doc, located_data: dict) -> list:
    """
    提取股权转让流量 (ShareTransferFlow)

    三协电机特有：历史沿革中的股权代持还原
    """
    rows = []
    company = located_data["company"]

    # 股权代持解除（从公开转让说明书引用中得知）
    for snippet in located_data["pevc_snippets"]:
        text = snippet["text"]
        page = snippet["pdf_page"]

        if "代持" in text or "股权转让" in text:
            # 匹配转让模式
            for m in re.finditer(
                r'(\d{4}\s*年\s*\d{1,2}\s*月).*?'
                r'(?:股权代持已解除|转让).*?',
                text
            ):
                evidence = text[max(0, m.start()-20):min(len(text), m.end()+100)].strip()

                date_str = normalize_date(m.group(1)) if m.group(1) else ""

                rows.append({
                    "event_id": next_event_id(company["code"], "share_transfer_flow"),
                    "processing_status": "EXTRACTED",
                    "status_detail": "代持详情见《公开转让说明书》",
                    "traceability": "external_required",
                    "extracted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "record_type": "share_transfer_flow",
                    "company_name": company["name"],
                    "stock_code": company["code"],
                    "source_page": f"PDF p{page}",
                    "transfer_date": date_str,
                    "transferor_name": None,  # 代持还原，具体转让方需查公开转让说明书
                    "transferee_name": None,
                    "shares_transferred": None,
                    "transfer_amount": None,
                    "price_per_share": None,
                    "transfer_type": "代持还原",
                    "evidence_text": evidence[:500],
                    "data_source": "pdf_disclosed",
                    "notes": "代持详情见《常州三协电机股份有限公司公开转让说明书》",
                })
                break  # 每snippet只取一条

    return rows


def main():
    # 读取 Step1 输出
    located_path = OUTPUTS_DIR / "located_sections.json"
    if not located_path.exists():
        print(f"✗ 找不到 {located_path}，请先运行 locate_pevc_sections.py")
        return 1

    with open(located_path, "r", encoding="utf-8") as f:
        located_data = json.load(f)

    company = located_data["company"]
    pdf_path = PDF_DIR / company["pdf"]

    print("=" * 60)
    print(f"[Step 2] PE/VC 结构化提取: {company['name']} ({company['code']})")
    print(f"  输入: {located_path}")
    print(f"  PDF: {pdf_path}")
    print("=" * 60)

    if not HAS_FITZ:
        log_step("extract_pevc", "failed", "PyMuPDF未安装")
        return 1

    doc = fitz.open(str(pdf_path))

    # ── 2a: 认缴流量 ──
    sf_rows = extract_subscription_flows(doc, located_data)
    log_step("extract_subscription_flows", "success" if sf_rows else "warning",
             f"{len(sf_rows)}条认缴记录")

    # ── 2b: 股权结构快照 ──
    es_rows = extract_equity_snapshots_from_tables(doc, located_data)
    log_step("extract_equity_snapshots", "success" if es_rows else "warning",
             f"{len(es_rows)}条快照记录")

    # ── 2c: PE基金详情 ──
    pe_rows = extract_pe_fund_details(doc, located_data)
    log_step("extract_pe_fund_details", "success" if pe_rows else "warning",
             f"{len(pe_rows)}条PE基金记录")

    # ── 2d: 股权转让 ──
    st_rows = extract_share_transfers(doc, located_data)
    log_step("extract_share_transfers", "success" if st_rows else "warning",
             f"{len(st_rows)}条转让记录")

    doc.close()

    # ── 写JSONL ──
    def write_jsonl(path, rows):
        with open(path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    write_jsonl(SF_JSONL, sf_rows)
    write_jsonl(ES_JSONL, es_rows)
    write_jsonl(PE_DETAIL_JSONL, pe_rows)
    write_jsonl(ST_JSONL, st_rows)

    print(f"\n✓ 输出文件:")
    print(f"  subscription_flow:  {SF_JSONL} ({len(sf_rows)}行)")
    print(f"  equity_snapshot:    {ES_JSONL} ({len(es_rows)}行)")
    print(f"  pe_fund_detail:     {PE_DETAIL_JSONL} ({len(pe_rows)}行)")
    print(f"  share_transfer:     {ST_JSONL} ({len(st_rows)}行)")

    # ── 汇总统计 ──
    # 按 processing_status 分类统计
    def count_status(rows, status):
        return sum(1 for r in rows if r.get("processing_status") == status)

    all_rows = sf_rows + es_rows + pe_rows + st_rows
    summary = {
        "schema_version": "4.1",
        "generated_at": datetime.now().isoformat(),
        "company": company,
        "prospectus_date": PROSPECTUS_DATE,
        "statistics": {
            "total_records": len(all_rows),
            "subscription_flow_count": len(sf_rows),
            "equity_snapshot_count": len(es_rows),
            "pe_fund_detail_count": len(pe_rows),
            "share_transfer_flow_count": len(st_rows),
            "status_breakdown": {
                "EXTRACTED": count_status(all_rows, "EXTRACTED"),
                "MANUAL_REVIEW": count_status(all_rows, "MANUAL_REVIEW"),
                "VERIFIED": count_status(all_rows, "VERIFIED"),
                "ERROR": count_status(all_rows, "ERROR"),
            },
            "traceability_breakdown": {
                "pdf_disclosed": sum(1 for r in all_rows if r.get("traceability") == "pdf_disclosed"),
                "calculated": sum(1 for r in all_rows if r.get("traceability") == "calculated"),
                "inferred": sum(1 for r in all_rows if r.get("traceability") == "inferred"),
                "external_required": sum(1 for r in all_rows if r.get("traceability") == "external_required"),
            },
            "pe_investors": list(set(
                r["subscriber_name"] for r in sf_rows
                if classify_investor_type(r.get("subscriber_name", "")) == "PE"
            )),
            "vc_investors": list(set(
                r["subscriber_name"] for r in sf_rows
                if classify_investor_type(r.get("subscriber_name", "")) == "VC"
            )),
        },
    }

    summary_path = OUTPUTS_DIR / "extraction_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n  PE投资人: {summary['statistics']['pe_investors']}")
    print(f"  状态分布: EXTRACTED={summary['statistics']['status_breakdown']['EXTRACTED']} | "
          f"MANUAL_REVIEW={summary['statistics']['status_breakdown']['MANUAL_REVIEW']} | "
          f"VERIFIED={summary['statistics']['status_breakdown']['VERIFIED']}")
    print(f"  溯源分布: pdf_disclosed={summary['statistics']['traceability_breakdown']['pdf_disclosed']} | "
          f"external_required={summary['statistics']['traceability_breakdown']['external_required']}")
    print(f"  汇总: {summary_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
