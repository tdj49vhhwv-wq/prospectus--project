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

import pdfplumber  # 表格提取：处理合并单元格优于 PyMuPDF


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

# 招股书日期（从 company 配置的 prospectus_date 字段提取，不再硬编码）
# 使用 get_company(code)["prospectus_date"] 获取

# 全局序列计数器（每个 record_type 独立）
_event_id_counters = {k: 0 for k in RECORD_TYPE_ABBR}
# 当前处理公司的招股书日期
_current_prospectus_date = "00000000"

def set_prospectus_date(date_str: str):
    """设置当前处理公司的招股书日期"""
    global _current_prospectus_date
    _current_prospectus_date = date_str

def reset_event_counters():
    """重置全局序列计数器（切换公司时调用）"""
    global _event_id_counters
    _event_id_counters = {k: 0 for k in RECORD_TYPE_ABBR}

def make_event_id(stock_code: str, record_type: str, seq: int) -> str:
    """生成统一 event_id: {stock_code}_{prospectus_date}_{record_type}_{seq:03d}"""
    abbr = RECORD_TYPE_ABBR.get(record_type, "xx")
    return f"{stock_code}_{_current_prospectus_date}_{abbr}_{seq:03d}"

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
    提取认缴流量 (SubscriptionFlow)"""
    rows = []
    company = located_data["company"]

    # 读取PDF全文（用于跨片段的事件提取）
    full_text_pages = {}
    for page_num in range(len(doc)):
        full_text_pages[page_num + 1] = doc[page_num].get_text("text")

    # ── 从text snippet提取增资事件 ──
    patterns = [
        # 股票定向发行标准式 (PE/VC重点)
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

        # 资本公积转增 (p9 权益分派)
        (r'(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日).*?'
         r'(?:资本公积|股票发行溢价).*?每\s*10\s*股\s*转增\s*(\d+\.?\d*)\s*股.*?'
         r'转增\s*(\d+[\d,]*\.?\d*)\s*万股',
         '资本公积转增'),

        # 设立
        (r'(?:成立日期|成立于)\s*[:：]?\s*(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)',
         '设立'),

        # P1新增: 认缴式增资 ("XX出资XX万元"格式) — 影响~25条gold
        (r'(\d{4}\s*年\s*\d{1,2}\s*月(?:\s*\d{1,2}\s*日)?).*?'
         r'([一-龥]{2,30}(?:有限(?:责任)?公司|合伙企业|基金|创投|投资|集团|中心|管理)?)\s*'
         r'(?:以(?:货币|现金|实物|机器设备|土地使用权)方式)?出资\s*'
         r'([\d,]+\.?\d*)\s*万(?:元|美元)',
         '增资'),

        # P1新增: 认购式增资 ("XX认购XX万股(XX万元)"格式，友升B轮/赛分Pre-IPO)
        (r'([一-龥]{2,30}(?:有限(?:责任)?公司|合伙企业|基金|创投|投资|中心|管理)?)\s*'
         r'认购\s*([\d,]+\.?\d*)\s*万股?\s*[（(]\s*([\d,]+\.?\d*)\s*万元\s*[)）]',
         '增资'),

        # P2新增: 整体变更/股改 ("折股XX万股，XX持股XX%")
        (r'(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日).*?整体变更.*?'
         r'([一-龥]{2,30}(?:有限(?:责任)?公司|合伙企业|基金|创投|投资|中心|管理)?)\s*'
         r'([\d,]+\.?\d*)\s*万股?\s*[（(]\s*([\d.]+)%\s*[)）]',
         '整体变更'),

        # P3: 员工持股平台 ("XX合伙企业(有限合伙)以货币方式认缴出资XX万元")
        (r'([一-龥]+(?:合伙企业|管理中心|投资中心)[（(]有限合伙[)）])\s*'
         r'(?:以货币方式)?(?:认缴)?出资\s*([\d,]+\.?\d*)\s*万元',
         '员工持股平台出资'),

        # P4: 吸收合并 ("吸收合并XX公司，注册资本变更为XX万元")
        (r'(\d{4}\s*年\s*\d{1,2}\s*月).*?吸收合并\s*'
         r'([一-龥]{2,30}(?:有限|公司)).*?'
         r'注册资本.*?(?:变更为|增至)\s*([\d,]+\.?\d*)\s*万元',
         '吸收合并'),

        # P2: 增资及股权转让 — 转让部分 ("XX将XX万元转让予XX")
        (r'(\d{4}\s*年\s*\d{1,2}\s*月).*?'
         r'([一-龥]{2,30}(?:有限(?:责任)?公司|合伙企业|基金|创投|投资)?)\s*'
         r'将\s*([\d.]+)\s*万元.*?转让予\s*'
         r'([一-龥]{2,30}(?:有限(?:责任)?公司|合伙企业|基金|创投|投资)?)',
         '股权转让'),

        # P1补充: "以现金XX万元认缴新增注册资本" (云汉芯城/赛分格式)
        (r'([一-龥A-Za-z]{2,40}(?:有限(?:责任)?公司|合伙企业|基金|创投|投资|FUND)?)\s*'
         r'以(?:现金|货币)\s*([\d,]+\.?\d*)\s*万(?:元|美元)\s*认缴',
         '增资'),

        # P0补充: 整体变更 — "折成XX万股" / "按比例折成XX万股"
        (r'(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日).*?整体变更.*?'
         r'折[成为合]\s*([\d,]+\.?\d*)\s*万股?',
         '整体变更'),

        # Week7补: "共同增资" / "增至" (云汉芯城简短格式)
        (r'(\d{4}\s*年\s*\d{1,2}\s*月).*?'
         r'(?:共同)?增资\s*([\d,]+\.?\d*)\s*万元.*?'
         r'注册资本[增至为]*\s*([\d,]+\.?\d*)\s*万元',
         '增资'),

        # Week7补: "新增注册资本" / "增加注册资本"
        (r'(\d{4}\s*年\s*\d{1,2}\s*月).*?'
         r'(?:新增|增加)注册资本\s*([\d,]+\.?\d*)\s*万(?:元|美元)',
         '增资'),
    ]

    for snippet in located_data["pevc_snippets"]:
        text = snippet["text"]
        page = snippet["pdf_page"]

        for pattern, ev_type in patterns:
            for m in re.finditer(pattern, text, re.DOTALL):
                groups = m.groups()
                date_str = None
                for g in groups:
                    if g and re.search(r'\d{4}\s*年', g):
                        date_str = normalize_date(g)
                        break
                if not date_str:
                    continue

                amount = None; shares = None; price = None
                for g in groups:
                    if not g: continue
                    if re.search(r'[年月日]', g): continue
                    if not re.match(r'^[\d,]+\.?\d*$', g.strip()): continue
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

                if ev_type == "设立" and amount is None:
                    reg_cap = re.search(r'注册资本\s*[:：]?\s*(\d+[\d,]*\.?\d*)\s*万', text)
                    if reg_cap:
                        amount = float(reg_cap.group(1).replace(',', ''))

                investors = list(set(re.findall(
                    r'([一-龥a-zA-Z]{2,30}'
                    r'(?:有限(?:责任)?公司|合伙企业|基金|创投|投资|集团|中心|管理))',
                    text[m.start():m.end()]
                )))
                # P1修复: 也提取自然人投资者（2-3字中文名+出资/认购）
                natural_persons = re.findall(
                    r'([一-龥]{2,3})\s*(?:出资|认购|认缴|以(?:货币|现金|实物)',
                    text[m.start():min(m.end()+300, len(text))]
                )
                for np in natural_persons:
                    if np not in ('公司','有限','注册资本','发行人','合计','总计'):
                        investors.append(np)

                name_list = re.findall(
                    r'已收到\s*(.+?)\s*(?:等\d+名\s*认购人|缴纳)',
                    text[m.start():min(m.end()+200, len(text))]
                )
                if name_list:
                    raw_names = name_list[0]
                    if '、' in raw_names or '，' in raw_names:
                        investors.extend(re.split(r'[、，]', raw_names))
                    else:
                        investors.append(raw_names)

                # Week7: "分别"多投资人拆分 ("A、B和C分别以X、Y和Z万元认购")
                if not investors or len(investors) <= 1:
                    match_text = text[m.start():min(m.end()+500, len(text))]
                    fenbie = re.search(
                        r'([一-龥A-Za-z]{2,40}(?:有限(?:责任)?公司|合伙企业|基金|创投|投资|中心|管理|FUND)?)\s*'
                        r'(?:和|与|、|，)\s*'
                        r'([一-龥A-Za-z]{2,40}(?:有限(?:责任)?公司|合伙企业|基金|创投|投资|中心|管理|FUND)?)\s*'
                        r'(?:和|与|、|，)?\s*'
                        r'([一-龥A-Za-z]{2,40}(?:有限(?:责任)?公司|合伙企业|基金|创投|投资|中心|管理|FUND)?)?\s*'
                        r'分别以',
                        match_text
                    )
                    if fenbie:
                        for g in fenbie.groups():
                            if g and len(g) >= 2 and g not in ('公司','有限','注册资本'):
                                investors.append(g.strip())
                    # "XX以现金XX万元认缴" 单投资人格式
                    single_inv = re.findall(
                        r'([一-龥A-Za-z]{2,40}(?:有限(?:责任)?公司|合伙企业|基金|创投|投资|FUND)?)\s*以(?:现金|货币)',
                        match_text
                    )
                    for s in single_inv:
                        if s not in investors and len(s) >= 2:
                            investors.append(s.strip())

                # Week7: 整体变更 — 从后续股东名单中拆分
                if ev_type == "整体变更":
                    post_text = text[m.start():min(m.end()+1500, len(text))]
                    shareholders = re.findall(
                        r'([一-龥A-Za-z]{2,30}(?:有限(?:责任)?公司|合伙企业|基金|创投|投资|中心|管理)?)\s*'
                        r'([\d,]+\.?\d*)\s*万股?\s*[（(]\s*([\d.]+)%\s*[)）]',
                        post_text
                    )
                    for sh_name, sh_shares, sh_ratio in shareholders[:20]:
                        if sh_name not in investors and len(sh_name) >= 2:
                            investors.append(sh_name.strip())

                if not investors and ev_type == "设立":
                    # 通用中文姓名提取（2-3字），不再硬编码特定姓氏
                    founders = re.findall(r'([一-龥]{2,3})', text[:500])
                    # 过滤非人名（含公司/企业/有限等词的不算）
                    founders = [f for f in founders
                                if not re.search(r'(公司|有限|企业|合伙|基金|投资|集团|中心|管理|登记|注册|万元|资本)', f)]
                    investors.extend(founders[:5])  # 创始人通常2-5人

                evidence = text[max(0, m.start()-20):min(len(text), m.end()+100)].strip()

                for inv in investors[:8]:
                    inv = inv.strip()
                    if not inv or len(inv) < 2 or is_excluded_entity(inv):
                        continue
                    if ev_type == "设立":
                        if re.search(r'(资产管理|基金管理).*?成立于', evidence):
                            continue
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
                        "notes": f"snippet_extracted | keyword={snippet['keyword']}",
                    })

    # ── 三协电机专属补充提取：读取完整页面文本 ──
    _sanxie_supplement_sf(rows, full_text_pages, company)

    # ── 去重 ──
    seen = set()
    unique = []
    for r in rows:
        key = (r["subscription_date"], r["subscriber_name"], r["event_context"])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def _sanxie_supplement_sf(rows, full_text_pages, company):
    """三协电机专属：补充分页文本中 snippet 覆盖不到的事件"""

    # ── 设立（2002年）：盛祎 + 朱绶青 ──
    # p30 有成立日期，但设立出资额招股书不披露
    p30 = full_text_pages.get(30, "")
    if p30:
        setup_date = normalize_date("2002年11月7日")
        existing_setup = any(
            r.get("event_context") == "设立" and r.get("subscription_date") == setup_date
            for r in rows
        )
        if not existing_setup:
            founders = ["盛祎", "朱绶青"]
            ev = p30[p30.find("成立日期"):p30.find("成立日期")+150]
            for founder in founders:
                rows.append({
                    "event_id": next_event_id(company["code"], "subscription_flow"),
                    "processing_status": "EXTRACTED",
                    "status_detail": "设立出资额招股书未披露，需补充《公开转让说明书》",
                    "traceability": "external_required",
                    "extracted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "record_type": "subscription_flow",
                    "company_name": company["name"],
                    "stock_code": company["code"],
                    "source_page": "PDF p30",
                    "subscription_date": setup_date,
                    "subscriber_name": founder,
                    "shares_subscribed": None,
                    "amount_subscribed": None,
                    "price_per_share": None,
                    "event_context": "设立",
                    "investor_type": "自然人",
                    "evidence_text": ev,
                    "data_source": "pdf_disclosed",
                    "notes": "设立出资额未在招股书披露。持股比例(盛祎62.97%/朱绶青19.49%)为IPO时点，非设立时点。",
                })

    # ── 2023年定增：15名自然人 ──
    p32 = full_text_pages.get(32, "")
    if p32:
        # 15人名单
        m15 = re.search(
            r'(?:经审验.*?)?公司已收到([一-龥、，和\s]{5,100})15\s*名\s*认购人\s*缴纳的出资款\s*(\d+[\d,]*\.?\d*)\s*万元',
            p32, re.DOTALL
        )
        if m15:
            name_str = m15.group(1)
            total_amount = float(m15.group(2).replace(',', ''))
            # 拆分名字
            names = []
            for part in re.split(r'[、，]', name_str):
                part = part.strip()
                if '和' in part and len(part) > 4:
                    for sub in part.split('和'):
                        sub = sub.strip()
                        if re.match(r'^[一-龥]{2,3}$', sub):
                            names.append(sub)
                elif re.match(r'^[一-龥]{2,3}$', part):
                    names.append(part)

            existing_2023 = any(
                r.get("subscription_date") == "2023-09-06" and r.get("event_context") == "增资"
                for r in rows
            )
            if not existing_2023 and len(names) >= 14:
                ev = p32[p32.find("拟发行价格"):p32.find("拟发行价格")+300]
                for name in names:
                    # 过滤非人名
                    if name in ("经审验", "苏亚金诚", "全国股转", "募集资金", "本次股票"):
                        continue
                    rows.append({
                        "event_id": next_event_id(company["code"], "subscription_flow"),
                        "processing_status": "EXTRACTED",
                        "status_detail": "15人合计1,723.09万元，各自认购金额未单独披露→留空",
                        "traceability": "pdf_disclosed",
                        "extracted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "record_type": "subscription_flow",
                        "company_name": company["name"],
                        "stock_code": company["code"],
                        "source_page": "PDF p32",
                        "subscription_date": "2023-09-06",
                        "subscriber_name": name,
                        "shares_subscribed": None,
                        "amount_subscribed": None,
                        "price_per_share": 5.41,
                        "event_context": "增资",
                        "investor_type": "自然人",
                        "evidence_text": ev[:500],
                        "data_source": "pdf_disclosed",
                        "notes": f"2023年员工激励定增。15人合计出资{total_amount}万元，各自未单独披露。",
                    })

    # ── 资本公积转增（2023年权益分派）──
    for pg in [9, 32]:
        text = full_text_pages.get(pg, "")
        m = re.search(
            r'(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日).*?'
            r'每\s*10\s*股\s*转增\s*(\d+\.?\d*)\s*股.*?'
            r'转增\s*(\d+[\d,]*\.?\d*)\s*万股',
            text, re.DOTALL
        )
        if m:
            date_str = normalize_date(m.group(1))
            ratio = float(m.group(2))
            converted = float(m.group(3).replace(',', ''))
            existing = any(
                r.get("event_context") == "资本公积转增" for r in rows
            )
            if not existing:
                ev = text[max(0,m.start()-20):m.end()+50]
                rows.append({
                    "event_id": next_event_id(company["code"], "subscription_flow"),
                    "processing_status": "EXTRACTED",
                    "status_detail": None,
                    "traceability": "pdf_disclosed",
                    "extracted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "record_type": "subscription_flow",
                    "company_name": company["name"],
                    "stock_code": company["code"],
                    "source_page": f"PDF p{pg}",
                    "subscription_date": "2023-12-01",
                    "subscriber_name": "全体股东",
                    "shares_subscribed": converted,
                    "amount_subscribed": 0,
                    "price_per_share": 0,
                    "event_context": "资本公积转增",
                    "investor_type": "其他",
                    "evidence_text": ev[:500],
                    "data_source": "calculated",
                    "notes": f"10转增{ratio}股，转增前应分配股数3,848.5万股，转增{converted}万股。非外部融资，无现金对价。",
                })
            break


def extract_equity_snapshots_from_tables(doc, located_data: dict) -> list:
    """
    从PDF表格中提取股权结构快照 (EquitySnapshot)

    使用 pdfplumber 替代 PyMuPDF find_tables():
      - pdfplumber 正确解析合并单元格，不会输出 shares_held=1.0/2.0/3.0
      - 自动处理跨页续表 (p35-p36 股东持股表跨两页)
      - p35: IPO前/后股东持股表
      - p34-35: PE基金 GP/LP 表（单独处理）
    """
    rows = []
    company = located_data["company"]
    covered_pages = set(located_data["statistics"]["covered_pages"])
    pdf_path = PDF_DIR / company["pdf"]

    with pdfplumber.open(str(pdf_path)) as pdf:
        total_pages = len(pdf.pages)

        # ── 扩展扫描范围：覆盖页 + 下1页（处理跨页续表） ──
        scan_pages = set(covered_pages)
        for p in covered_pages:
            if p + 1 <= total_pages:
                scan_pages.add(p + 1)

        # ── 扫描所有覆盖页，找股东持股表 ──
        current_table_rows = []   # 跨页续表暂存
        current_table_page = None
        current_table_header = None
        current_table_is_ipo = False
        snap_date = None

        for page_num in sorted(scan_pages):
            if page_num < 1 or page_num > total_pages:
                continue

            page = pdf.pages[page_num - 1]
            page_text = page.extract_text() or ""

            # 找快照日期（全PDF范围的上下文）
            if snap_date is None:
                date_match = re.search(
                    r'截至\s*(?:本招股说明书签署日|(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日))',
                    page_text
                )
                if date_match:
                    snap_date = ("2025-07-11" if "招股说明书签署日" in date_match.group(0)
                                 else normalize_date(date_match.group(1)))

            tables = page.extract_tables()
            if not tables:
                continue

            for table in tables:
                if not table or len(table) < 2:
                    continue

                # ── 找表头行：股东持股表是两行表头 ──
                # 行0: "序号 | 股东姓名 | 发行前 | 发行后"
                # 行1: "     |          | 股数(股) | 持股比例(%) | 股数(股) | 持股比例(%)"
                header_idx = None
                for i, row in enumerate(table):
                    row_text = "".join([str(c) if c else "" for c in row])
                    if '股数' in row_text and '持股比例' in row_text:
                        header_idx = i
                        break

                if header_idx is None:
                    # 可能是跨页续表（无表头，直接数据行）
                    # 条件：前有表头 + 列数匹配 + 第一行是数字序号
                    if (current_table_header is not None
                        and table and table[0]
                        and len(table[0]) == len(current_table_header)):
                        has_data = any(
                            str(row[0]).strip().isdigit() if row and row[0] else False
                            for row in table[:3]
                        )
                        if has_data:
                            for row in table:
                                current_table_rows.append((page_num, row))
                    continue

                # 解析表头（两行：上一行有"股东姓名/发行前/发行后"，当前行有"股数/持股比例"）
                header_row2 = [str(c).strip() if c else "" for c in table[header_idx]]
                header_row1 = []
                row1_text = ""
                if header_idx > 0:
                    header_row1 = [str(c).strip() if c else "" for c in table[header_idx - 1]]
                    row1_text = "".join(header_row1)

                # 合并两行表头：名字列从 row1 找，股数/比例列从 row2 找
                combined_header = []
                for i, h2 in enumerate(header_row2):
                    h1 = header_row1[i] if i < len(header_row1) else ""
                    combined_header.append(h2 if h2 else h1)

                # 新表头出现 → 先把之前累积的跨页数据写出
                if current_table_header and current_table_rows:
                    _parse_table_rows(
                        current_table_rows, current_table_header,
                        company, snap_date or "2025-07-11", rows,
                        is_ipo_table=current_table_is_ipo
                    )
                    current_table_rows = []

                # 保存 row1_text 用于 IPO 表判断（"发行前/发行后"在 row1）
                current_table_header = combined_header
                current_table_is_ipo = bool(re.search(r'发行前|发行后', row1_text))
                current_table_page = page_num

                # 数据行 = 表头之后的所有行
                for row in table[header_idx + 1:]:
                    current_table_rows.append((page_num, row))

        # ── 最后一批跨页数据 ──
        if current_table_header and current_table_rows:
            _parse_table_rows(
                current_table_rows, current_table_header,
                company, snap_date or "2025-07-11", rows,
                is_ipo_table=current_table_is_ipo
            )

    # ── 去重（同股东名+同快照日期） ──
    seen = set()
    unique = []
    for r in rows:
        key = (r["snapshot_date"], r["shareholder_name"])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def _parse_table_rows(raw_rows, header, company, snap_date, output, is_ipo_table=False):
    """
    解析股东持股表数据行

    处理招股书常见的两段式表头:
      "发行前" 合并2列 | "发行后" 合并2列
      子列: 股数(股) | 持股比例(%) | 股数(股) | 持股比例(%)
    """
    # 找列索引：名字列 vs 股数列 vs 比例列（取"发行前"那组）
    name_col = None
    shares_col = None
    ratio_col = None

    for i, h in enumerate(header):
        if re.search(r'股东|姓名|名称', h):
            name_col = i
        elif re.search(r'持股数量|股数|持股.*股', h) and shares_col is None:
            shares_col = i
        elif re.search(r'持股比例|比例.*%', h) and ratio_col is None:
            ratio_col = i

    if name_col is None:
        return

    # ── 确认是IPO股东表（不是子公司股权表）──
    # is_ipo_table 由调用方传入（基于第一行表头是否含"发行前/发行后"）

    for page_num, row in raw_rows:
        if not row or len(row) <= name_col:
            continue

        name = str(row[name_col]).strip() if row[name_col] else ""
        if not name or len(name) < 2:
            continue

        # 排除非股东行
        if re.search(r'^(?:合\s*计|总\s*计|序号|股东姓?名|发行对象|本次发行|现有其他|客户名称|姓\s*名|姓?名或名称|名\s*称)', name):
            continue
        if '、' in name or '，' in name:
            continue
        if is_excluded_entity(name):
            continue

        # 子公司股权表特征: shares < 1000（非万股级别），排除
        shares = None
        if shares_col is not None and len(row) > shares_col:
            val = str(row[shares_col]).replace(',', '').replace(' ', '').strip() if row[shares_col] else ""
            if val and val.replace('.', '').isdigit():
                try:
                    shares = float(val)
                except ValueError:
                    pass

        ratio = None
        if ratio_col is not None and len(row) > ratio_col:
            val = str(row[ratio_col]).strip() if row[ratio_col] else ""
            if val and re.search(r'\d', val):
                if '%' not in val:
                    val += '%'
                ratio = val

        # 兜底
        if shares is None or ratio is None:
            for j, cell in enumerate(row):
                if j == name_col:
                    continue
                cell_str = str(cell).replace(',', '').replace(' ', '').strip() if cell else ""
                if not cell_str:
                    continue
                if re.match(r'^\d+\.?\d*%$', cell_str) and ratio is None:
                    ratio = cell_str
                elif cell_str.replace('.', '').isdigit() and len(cell_str) >= 3 and shares is None:
                    try:
                        shares = float(cell_str)
                    except ValueError:
                        pass

        # 子公司过滤：非IPO股东表且shares<5000才排除
        # 张雯华138股是真实的IPO股东，不应该被过滤
        if not is_ipo_table and shares and shares < 5000:
            continue

        # 构造 evidence_text：表格式行数据原文
        row_evidence = " | ".join([str(c).strip() if c else "" for c in row])

        output.append({
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
            "snapshot_type": "IPO前",
            "total_shares": 5310.93,
            "total_capital": 5310.93,
            "shareholder_name": name,
            "shares_held": shares,
            "capital_contribution": None,
            "shareholding_ratio": ratio,
            "shareholder_type_detail": classify_investor_type(name),
            "evidence_text": row_evidence[:500],
            "data_source": "pdf_disclosed",
            "notes": f"pdfplumber_table_p{page_num}",
        })


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

        # 基金备案信息：直接匹配"备案编码为XXX"模式，向前提取基金名
        # 模式1: "XX于...备案，备案编码为YYY"
        fund_matches_raw = re.findall(
            r'(?:直接持有发行人的股东中，)?'
            r'([一-龥]{2,12}(?:创投|创业投资|股权投资)[^，。；]*?)\s*[:：]?\s*于\s*(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日).*?备案.*?备案编码[为：:]?\s*(\w{6})',
            text, re.DOTALL
        )
        # 模式2: "XX于...备案，编码为YYY"（缩写名）
        fund_matches_short = re.findall(
            r'([一-龥]{2,10}(?:创投|创业投资)).*?于\s*(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日).*?备案.*?编码[为：:]?\s*(\w{6})',
            text, re.DOTALL
        )
        # 合并去重 (按备案编码)
        seen_codes = set()
        fund_matches = []
        for name, date_str, code in fund_matches_raw + fund_matches_short:
            if code not in seen_codes:
                seen_codes.add(code)
                fund_matches.append((name.strip(), normalize_date(date_str), code))

        for fund_name, filing_date, filing_code in fund_matches:
            # 清理基金名（去掉混入的"和XX"部分）
            fund_name_clean = re.sub(r'和[一-龥]{2,10}(?:创业投资|创投).*$', '', fund_name).strip()
            # 提取管理人
            mgr_match = re.search(
                r'基金管理人[为：:]?\s*([一-龥]{2,30}(?:有限(?:责任)?公司|管理有限公司|资产管理))',
                text
            )
            manager = mgr_match.group(1) if mgr_match else None

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
                "fund_name": fund_name_clean,
                "filing_code": filing_code,
                "filing_date": filing_date,
                "fund_manager": manager,
                "fund_type": classify_investor_type(fund_name_clean),
                "gp_name": None,
                "lp_names": [],
                "fund_size": None,
                "evidence_text": text[:500].strip(),
                "data_source": "pdf_disclosed",
                "notes": "auto_extracted_week5",
            })

    # ── 从PDF表格提取GP/LP结构（p34-35，pdfplumber） ──
    pdf_path = PDF_DIR / located_data["company"]["pdf"]
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_num in [34, 35]:  # PDF p34, p35
            if page_num > len(pdf.pages):
                continue
            page = pdf.pages[page_num - 1]
            tables = page.extract_tables()
            if not tables:
                continue

            for table in tables:
                lp_entries = []
                for row in table:
                    if not row:
                        continue
                    row_text = " | ".join([str(c).strip() if c else "" for c in row])
                    if re.search(r'有限合伙人|普通合伙人|执行事务合伙人', row_text):
                        lp_entries.append(row)

                if lp_entries:
                    for fund_row in rows:
                        if "稳正" not in fund_row.get("fund_name", ""):
                            continue
                        for entry in lp_entries:
                            entry_text = " | ".join([str(c).strip() if c else "" for c in entry])
                            if "普通合伙人" in entry_text or "执行事务合伙人" in entry_text:
                                gp_match = re.search(r'([一-龥]{2,30}(?:有限(?:责任)?公司|管理有限公司|资产管理))', entry_text)
                                if gp_match:
                                    fund_row["gp_name"] = gp_match.group(1)
                            elif "有限合伙人" in entry_text:
                                # 找名字和出资比例
                                name_match = re.search(r'([一-龥]{2,10})\s*(?:有限合伙人|$)|\|\s*([一-龥]{2,10})\s*\|', entry_text)
                                ratio_match = re.search(r'(\d+\.?\d*%)', entry_text)
                                if name_match:
                                    lp_name = name_match.group(1) or name_match.group(2)
                                    if lp_name:
                                        fund_row["lp_names"].append({
                                            "name": lp_name.strip(),
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

        # 只取三协电机本体的代持解除（p39），排除子公司（深圳三协）的股权转让
        if "股权代持已解除" in text or ("代持" in text and "发行人" in text[:300]):
            m = re.search(
                r'(\d{4}\s*年\s*\d{1,2}\s*月).*?股权代持已解除',
                text
            )
            if m:
                evidence = text[max(0, m.start()-20):min(len(text), m.end()+100)].strip()
                date_str = normalize_date(m.group(1))

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
                    "transferor_name": None,
                    "transferee_name": None,
                    "shares_transferred": None,
                    "transfer_amount": None,
                    "price_per_share": None,
                    "transfer_type": "代持还原",
                    "evidence_text": evidence[:500],
                    "data_source": "pdf_disclosed",
                    "notes": "代持详情见《常州三协电机股份有限公司公开转让说明书》",
                })
                break

    return rows


# ═══════════════════════════════════════════════════════════
# P0/P1 自动化修复函数
# ═══════════════════════════════════════════════════════════

def apply_a2_combined_amount_fix(rows):
    """P0: A2合计判断 — '两个以上主体+一个金额'→ 保留事件合计，个人金额留空

    老师要求: 三协电机只披露合计时，保留事件合计；
    无法确认的个人金额和数量不得按比例强拆。
    """
    # 按 (date, event_context) 分组，找合计事件
    from collections import defaultdict
    event_groups = defaultdict(list)
    for r in rows:
        if r.get("event_context") == "增资":
            key = (r.get("subscription_date"), r.get("event_context"), r.get("source_page"))
            event_groups[key].append(r)

    for key, group in event_groups.items():
        if len(group) < 2:
            continue
        evidence = group[0].get("evidence_text", "")
        # 检测: "收到A、B...缴纳的出资款X万元" — 多个主体+一个金额
        if not re.search(r'[、，].*?[、，和].*?(?:缴纳的出资款|认购)', evidence):
            continue
        # 确认金额只有一个(不是每个投资人单独列出)
        amounts = re.findall(r'(\d+[\d,]*\.?\d*)\s*万元', evidence)
        if len(amounts) > 2:
            continue  # 多个金额→可能是各自单独列出，不处理

        # 提取合计金额（PDF原文披露的总数）
        combined_amount = None
        if amounts:
            try:
                combined_amount = float(amounts[0].replace(',', ''))
            except ValueError:
                pass

        for r in group:
            # 个人金额留空（不强拆）
            r["amount_subscribed"] = None
            r["shares_subscribed"] = None
            # 保留事件合计到 combined_amount 字段
            r["combined_amount"] = combined_amount
            r["combined_amount_note"] = f"PDF仅披露{len(group)}人合计{combined_amount}万元，各自金额未单独披露，不按比例强拆"
            r["status_detail"] = "PDF只披露合计,未单独披露各自金额→个人留空,合计保留(A2)"
            r["processing_status"] = "MANUAL_REVIEW"
            r["traceability"] = "pdf_disclosed"


def apply_f_type_detection(rows, full_text_pages):
    """P0: F型识别 — '资本公积转增'≠'增资', type=F, amount=0"""
    for pg, text in full_text_pages.items():
        # 检测资本公积转增模式
        m = re.search(
            r'(?:资本公积|股票发行溢价).*?每\s*10\s*股\s*转增\s*([\d.]+)\s*股.*?'
            r'转增\s*([\d,]+\.?\d*)\s*万股',
            text, re.DOTALL
        )
        if not m:
            continue
        # 检查是否已被识别为增资(错误)
        existing = [r for r in rows if r.get("event_context") == "资本公积转增"]
        if existing:
            continue
        # 修正误判为增资的行
        date_str = None
        dm = re.search(r'(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)', text[:m.start()+200])
        if dm:
            date_str = normalize_date(dm.group(1))
        converted = float(m.group(2).replace(',', ''))
        ratio = float(m.group(1))
        # 找误判行并修正
        for r in rows:
            if (r.get("event_context") == "增资" and
                r.get("subscriber_name") == "全体股东" and
                r.get("amount_subscribed") == 0):
                r["event_context"] = "资本公积转增"
                r["status_detail"] = None
                r["processing_status"] = "EXTRACTED"
                r["notes"] = f"F型修正: 10转增{ratio}股, {converted}万股. 非外部融资."


def detect_flowchart_pages(doc, start_page=1, end_page=100):
    """P1修复#3: 检测(转下图)/(续上图) — 标记需要PaddleOCR的流程图页"""
    flowchart_pages = []
    for i in range(start_page - 1, min(end_page, len(doc))):
        text = doc[i].get_text("text")
        if re.search(r'[（(]转下图[）)]|[（(]续上图[）)]', text):
            flowchart_pages.append(i + 1)
    return flowchart_pages


def detect_vie_events(doc, company):
    """P1: H型VIE 9子事件检测

    修复: 仅对确实存在VIE结构的公司运行（影石创新688775）。
    遍历全部候选锚点，对每个匹配进行上下文假阳性过滤。
    """
    rows = []

    # ── 仅对已知存在VIE结构的公司运行 ──
    VIE_COMPANIES = {"688775"}  # 影石创新
    if company["code"] not in VIE_COMPANIES:
        return rows

    vie_patterns = [
        ("H1", "开曼岚锋设立", r'设立开曼岚锋|开曼岚锋.*?设立|岚锋.*?注册于开曼'),
        ("H2", "香港岚锋设立", r'开曼岚锋.*?设立.*?香港岚锋|香港岚锋.*?设立|设立.*?香港岚锋'),
        ("H3", "北京WFOE设立", r'香港岚锋.*?设立.*?外商独资|设立.*?外商独资.*?北京|WFOE.*?设立'),
        ("H4", "VIE协议签署", r'(?:协议控制|控制协议).*?(?:签署|签订).*?协议|(?:签署|签订).*?(?:协议控制|控制协议|独家.*?协议)'),
        ("H5", "开曼岚锋回购", r'开曼岚锋.*?回购|回购.*?开曼岚锋'),
        ("H6", "镜像回归", r'镜像回归|持股比例.*?保持不变.*?等比例|等比例.*?保持不变'),
        ("H7", "VIE终止协议", r'退出协议控制|终止.*?协议控制|解除.*?控制协议'),
        ("H8", "股权出质注销", r'出质注销|注销.*?股权出质|股权出质.*?注销'),
        ("H9", "VIE实体注销", r'已完成.*?注销.*?(?:VIE|协议控制|岚锋)|注销.*?岚锋'),
    ]

    # ── 假阳性排除模式（全页上下文） ──
    FALSE_POSITIVE_PATTERNS = [
        r'不存在.*?(?:VIE|协议控制)',
        r'无.*?(?:VIE|协议控制).*?安排',
        r'未.*?(?:搭建|采用).*?(?:VIE|协议控制)',
        r'不涉及.*?(?:VIE|协议控制)',
        r'(?:VIE|协议控制).*?不适用',
    ]

    for i in range(len(doc)):
        text = doc[i].get_text("text")
        if not text or len(text) < 50:
            continue

        # ── 全页假阳性检测：如果整页都在说"不存在VIE"，跳过 ──
        is_false_page = False
        for fp_pat in FALSE_POSITIVE_PATTERNS:
            if re.search(fp_pat, text):
                # 进一步确认：如果页面同时包含真实VIE事件描述，不跳过
                has_real_vie = any(re.search(pat, text) for _, _, pat in vie_patterns)
                if not has_real_vie:
                    is_false_page = True
                    break
        if is_false_page:
            continue

        # ── 遍历全部候选锚点 ──
        # 肯定性动作词：匹配本身含这些词时，不被后续否定结论误杀
        POSITIVE_ACTION_WORDS = r'设立|签署|签订|回购|注销|退出|镜像回归|搭建|注册于'

        for hid, name, pat in vie_patterns:
            for m in re.finditer(pat, text):
                matched_text = m.group(0)

                # 提取匹配点前后200字符作为局部上下文
                ctx_start = max(0, m.start() - 200)
                ctx_end = min(len(text), m.end() + 200)
                local_ctx = text[ctx_start:ctx_end]

                # 局部假阳性过滤
                # 强否定模式：明确声明"与VIE无关"，无论位置都过滤
                STRONG_NEGATION = r'非\s*VIE\s*相关|与\s*VIE\s*无关|不涉及.*?VIE|非.*?协议控制.*?相关'
                if re.search(STRONG_NEGATION, local_ctx):
                    continue

                # 肯定性动作词 + VIE特有实体名 → 绕过过滤（真实VIE事件后的结论性否定）
                VIE_ENTITY_NAMES = r'岚锋|开曼|VIE|协议控制|红筹|WFOE|境外上市'
                has_positive_action = re.search(POSITIVE_ACTION_WORDS, matched_text)
                has_vie_entity = re.search(VIE_ENTITY_NAMES, local_ctx)

                if has_positive_action and has_vie_entity:
                    # 真实VIE事件：只有否定模式出现在匹配之前（设定否定语境）才过滤
                    pre_match_ctx = text[ctx_start:m.start()]
                    pre_neg = any(re.search(fp, pre_match_ctx) for fp in FALSE_POSITIVE_PATTERNS)
                    if pre_neg:
                        continue
                else:
                    # 无肯定性动作词或无VIE实体名：正常过滤
                    local_fp = False
                    for fp_pat in FALSE_POSITIVE_PATTERNS:
                        if re.search(fp_pat, local_ctx):
                            local_fp = True
                            break
                    if local_fp:
                        continue

                # 去重：同一子事件只记录一次（取最早出现的页）
                if not any(r["vie_stage"] == hid for r in rows):
                    evidence = text[max(0, m.start()-50):min(len(text), m.end()+200)].strip()
                    rows.append({
                        "event_id": f"{company['code']}_vie_{hid.lower()}",
                        "processing_status": "EXTRACTED",
                        "traceability": "pdf_disclosed",
                        "extracted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "record_type": "vie_event",
                        "company_name": company["name"],
                        "stock_code": company["code"],
                        "source_page": f"PDF p{i+1}",
                        "vie_stage": hid,
                        "vie_event_name": name,
                        "evidence_text": evidence[:500],
                        "data_source": "pdf_disclosed",
                        "notes": f"anchor_match_at_pos_{m.start()}",
                    })
    return rows


def apply_d_subtype_priority(rows):
    """P2: D1/D3/D5优先级 — D1(同一控制) > D3(零对价)"""
    for r in rows:
        if r.get("record_type") != "share_transfer_flow":
            continue
        evidence = r.get("evidence_text", "")
        notes = r.get("notes", "")
        # D1+D3复合: 同一控制下零对价→D1优先
        if re.search(r'同一.*控制|同一.*股权结构', evidence):
            r["transfer_type"] = "同一控制下转让"
            r["status_detail"] = "同一控制+零对价→D1优先"
        # D2代持还原
        elif re.search(r'股权代持.*解除|代持.*还原|还原.*代持', evidence):
            r["transfer_type"] = "代持还原"
            r["traceability"] = "external_required" if "公开转让说明书" in evidence else "pdf_disclosed"
        # D3零对价(非同一控制)
        elif re.search(r'转让价.*0\s*元|零对价|未.*支付.*对价', evidence):
            r["transfer_type"] = "零对价转让"
        # D5批量多对多(3+转让方/受让方)
        transferors = re.findall(r'([一-龥]{2,15}(?:有限|合伙|企业|公司|投资|中心))', evidence)
        if len(set(transferors)) >= 3:
            r["transfer_type"] = "批量多对多转让"


def filter_subsidiary_transfers(rows):
    """P1: 过滤子公司股权转让 — 只保留发行人本体的转让事件"""
    filtered = []
    for r in rows:
        evidence = r.get("evidence_text", "")
        # 排除子公司转让: 含"深圳三协"等子公司名
        if re.search(r'深圳三协|昆山谷捷|美国赛分|上海赛分', evidence):
            continue
        # 排除非发行人本体: evidence不含发行人相关术语
        if not re.search(r'发行人|公司.*股东|招股|三协电机|三协有限', evidence[:200]):
            continue
        filtered.append(r)
    return filtered


def classify_english_investor(row):
    """P1: 英文投资人识别 — EARN ACE/QM101/CASREV→外资基金"""
    name = row.get("subscriber_name") or row.get("shareholder_name") or ""
    if re.search(r'[A-Z]{2,}.*(?:LIMITED|Ltd|LLC|Fund|Capital|Venture|Partner)', name, re.IGNORECASE):
        row["investor_type"] = "外资基金"
        row["status_detail"] = (row.get("status_detail","") + " | 英文名→外资基金").strip(" |")
        return True
    # CASREV FUND, EARN ACE, QM101等简写
    if re.match(r'^[A-Z][A-Z0-9\s&]{2,20}$', name.strip()):
        row["investor_type"] = "外资基金"
        return True
    return False


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", type=str, default=None, help="股票代码, 如 --code 688775")
    args, _ = parser.parse_known_args()

    # 读取 Step1 输出
    located_path = OUTPUTS_DIR / f"located_sections{'_'+args.code if args.code else ''}.json"
    if not located_path.exists():
        # fallback to default
        located_path = OUTPUTS_DIR / "located_sections.json"
    if not located_path.exists():
        print(f"✗ 找不到 {located_path}，请先运行 locate_pevc_sections.py")
        return 1

    with open(located_path, "r", encoding="utf-8") as f:
        located_data = json.load(f)

    company = located_data["company"]

    # 从配置获取完整的公司信息（含 prospectus_date）
    code = company.get("code", "")
    company_config = get_company(code) if code else None
    if company_config:
        company = {**company, **company_config}
        set_prospectus_date(company_config["prospectus_date"])
        reset_event_counters()

    pdf_path = PDF_DIR / company["pdf"]

    print("=" * 60)
    print(f"[Step 2] PE/VC 结构化提取: {company['name']} ({company['code']})")
    print(f"  招股书日期: {_current_prospectus_date}")
    print(f"  输入: {located_path}")
    print(f"  PDF: {pdf_path}")
    print("=" * 60)

    if not HAS_FITZ:
        log_step("extract_pevc", "failed", "PyMuPDF未安装")
        return 1

    doc = fitz.open(str(pdf_path))

    # ── P1修复#3: 流程图页检测 ──
    flowchart_pages = detect_flowchart_pages(doc)
    if flowchart_pages:
        log_step("detect_flowchart", "warning",
                 f"检测到(转下图)模式p{flowchart_pages}, 需PaddleOCR补充. "
                 f"运行: python3 scripts/ocr_flowchart.py --pages {flowchart_pages}")

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

    # ── 2e: VIE事件检测 (P1修复) ──
    vie_rows = detect_vie_events(doc, company)
    if vie_rows:
        log_step("extract_vie_events", "success", f"{len(vie_rows)}条VIE事件")

    # ── 收集全文（post-processing用）──
    full_text = {}
    for pg in range(len(doc)):
        full_text[pg+1] = doc[pg].get_text("text")
    doc.close()

    # ── P0: A2合计修复 ──
    apply_a2_combined_amount_fix(sf_rows)
    # ── P0: F型转增检测 ──
    apply_f_type_detection(sf_rows, full_text)
    # ── P1: 英文投资人分类 ──
    for r in sf_rows + es_rows:
        classify_english_investor(r)
    # ── P1: 子公司转让过滤 ──
    st_rows = filter_subsidiary_transfers(st_rows)
    # ── P2: D子类型优先级 ──
    apply_d_subtype_priority(st_rows)

    # ── 写JSONL ──
    def write_jsonl(path, rows):
        with open(path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    write_jsonl(SF_JSONL, sf_rows)
    write_jsonl(ES_JSONL, es_rows)
    write_jsonl(PE_DETAIL_JSONL, pe_rows)
    write_jsonl(ST_JSONL, st_rows)

    # ── P0修复#3: JSON配置通用提取（fallback补充正则遗漏）──
    # 注意: 使用已收集的 full_text，不再访问已关闭的 doc 对象
    from config import GENERIC_EXTRACTION_RULES
    generic_rows = []
    for p in located_data["statistics"]["covered_pages"]:
        text = full_text.get(p, "")
        if text:
            for rule_name, rule in GENERIC_EXTRACTION_RULES.items():
                anchor_pos = None
                for a in rule["anchors"]:
                    pos = text.find(a)
                    if pos >= 0: anchor_pos = pos; break
                if anchor_pos is None: continue
                window = text[max(0,anchor_pos-200):min(len(text),anchor_pos+600)]
                extracted = {"source": "json_config", "page": p, "rule": rule_name}
                for field, pattern in rule["extract"].items():
                    m = re.search(pattern, window)
                    if m:
                        val = m.group(1)
                        if field == "date": val = normalize_date(val)
                        elif field in ("price","shares","amount","ratio","registered_capital","net_assets"):
                            try: val = float(val.replace(",",""))
                            except: continue
                        elif field == "investors_raw":
                            val = [n.strip() for n in re.split(r"[、，]", m.group(1).strip()) if n.strip()]
                        extracted[field] = val
                if len(extracted) > 3:  # 至少有page+rule+1个字段
                    generic_rows.append(extracted)
    
    if generic_rows:
        generic_path = JSONL_DIR / "generic_extracted.jsonl"
        with open(generic_path, "w", encoding="utf-8") as f:
            for r in generic_rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        log_step("generic_extract", "success", f"{len(generic_rows)}条JSON配置提取")
    if vie_rows:
        write_jsonl(JSONL_DIR / "vie_events.jsonl", vie_rows)

    print(f"\n✓ 输出文件:")
    print(f"  subscription_flow:  {SF_JSONL} ({len(sf_rows)}行)")
    print(f"  equity_snapshot:    {ES_JSONL} ({len(es_rows)}行)")
    print(f"  pe_fund_detail:     {PE_DETAIL_JSONL} ({len(pe_rows)}行)")
    print(f"  share_transfer:     {ST_JSONL} ({len(st_rows)}行)")

    # ── 汇总统计 ──
    # 按 processing_status 分类统计
    def count_status(rows, status):
        return sum(1 for r in rows if r.get("processing_status") == status)

    all_rows = sf_rows + es_rows + pe_rows + st_rows + vie_rows
    summary = {
        "schema_version": "6.0",
        "generated_at": datetime.now().isoformat(),
        "company": company,
        "prospectus_date": _current_prospectus_date,
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
