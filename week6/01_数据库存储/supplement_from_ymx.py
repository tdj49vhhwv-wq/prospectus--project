"""
向杨苗鑫学习，补全 zbq 数据

核心改进:
1. subscription_flow: 多投资人事件→逐投资人拆分（84→目标172+）
2. share_transfer_flow: 补充转让方/受让方明细（25→目标60+）
3. equity_snapshot: 增加中间快照标记（t0→s1→s2...→IPO前）

数据来源: final/八家公司融资事件总表.md (独立验证过的Gold标准)
"""
import json
import re
import os
import sys
from pathlib import Path
from collections import defaultdict

import pg8000

# DB_CONFIG → from pipeline.db_config import DB_CONFIG
import sys; sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'pipeline'))
try:
    from db_config import DB_CONFIG
except ImportError:
    DB_CONFIG = {
    'host': '<server-host>',
    'port': 5433,
    'database': 'student',
    'user': '<redacted>',
    'password': os.environ.get('DB_PASSWORD', ''),
}

WEEK6 = Path(__file__).resolve().parent.parent
FINAL_MD = WEEK6 / "final" / "八家公司融资事件总表.md"


def connect():
    return pg8000.connect(**DB_CONFIG)


def parse_final_events():
    """解析final事件总表，返回结构化事件列表"""
    with open(FINAL_MD) as f:
        lines = f.readlines()

    events = []
    in_table = False
    for line in lines:
        line = line.strip()
        if line.startswith('| 日期'):
            in_table = True
            continue
        if in_table and line.startswith('|---'):
            continue
        if in_table and line.startswith('|') and '---' not in line:
            cols = [c.strip() for c in line.split('|')[1:-1]]
            if len(cols) >= 7 and cols[0] and re.search(r'\d{4}', cols[0]):
                events.append({
                    'date': cols[0],
                    'company': cols[1],
                    'type': cols[2],
                    'investor': cols[3],
                    'amount_price': cols[4],
                    'difficulty': cols[5],
                    'evidence': cols[6],
                })
        elif in_table and not line.startswith('|'):
            break
    return events


def extract_code_name(company_str):
    """从 '三协电机(920100)' 中提取 name 和 code"""
    m = re.match(r'(.+?)\((\d{6})\)', company_str)
    if m:
        return m.group(1).strip(), m.group(2)
    return company_str, ""


def classify_investor(name):
    """投资人类型分类（与ymx对齐）"""
    if not name or name in ('—', '全体股东', '公开发行'):
        return '其他'
    name = name.strip()
    if re.search(r'(政府|引导|国有|国家)', name):
        return '政府基金'
    if re.search(r'(天使|种子|孵化)', name):
        return 'VC'
    if re.search(r'(有限|合伙|基金|创投|投资|集团|中心|资本|资产|达晨|高瓴|启明|IDG|深创投|东方富海|复星|国科|华泰|聚贝|金浦|杉|EARN|QM|CASREV)', name):
        return 'PE'
    if re.match(r'^[A-Z][A-Za-z0-9\s&]{2,30}$', name.strip()):
        return '外资基金'
    if re.match(r'^[一-龥]{2,4}$', name.strip()):
        return '自然人'
    return '其他'


def parse_amount_price(ap_str):
    """解析金额/价格字符串: '37,000万/1,100万股 / 33.63'"""
    amount = None
    shares = None
    price = None
    if not ap_str or ap_str in ('—', '— / —'):
        return amount, shares, price

    # 金额: XX万 / XX万股 / XX元
    amt_m = re.search(r'([\d,]+\.?\d*)\s*万(?:元)?(?:\s*/\s*|$)', ap_str)
    if amt_m:
        amount = float(amt_m.group(1).replace(',', ''))
    # 股数
    sh_m = re.search(r'([\d,]+\.?\d*)\s*万股', ap_str)
    if sh_m:
        shares = float(sh_m.group(1).replace(',', ''))
    # 价格
    pr_m = re.search(r'/\s*([\d.]+)\s*$', ap_str)
    if pr_m:
        try:
            price = float(pr_m.group(1))
        except:
            pass
    return amount, shares, price


def split_investors(investor_str):
    """拆分投资人字符串为列表: '盛祎,朱绶青' → ['盛祎', '朱绶青']"""
    if not investor_str or investor_str in ('—', '全体股东', '公开发行'):
        return [investor_str]

    # 处理复杂格式: "国科瑞华/CASREV/中科贵银等增资+曾烨/刘云锋转让"
    names = []
    # 先按+分隔（增资+转让复合事件）
    parts = re.split(r'[+＋]', investor_str)
    for part in parts:
        # 清理"增资"、"转让"等动词
        part = re.sub(r'(增资|转让|受让|出资).*$', '', part).strip()
        # 按/、, 、 等拆分
        sub_parts = re.split(r'[/,、\s]+', part)
        for sp in sub_parts:
            sp = sp.strip()
            # 过滤非名称片段
            if not sp or len(sp) < 2:
                continue
            if re.match(r'^[\d.]+$', sp):  # 纯数字
                continue
            if sp in ('等', '→', '→', 'null'):
                continue
            # 清理括号内容但保留名字
            sp = re.sub(r'\(.*?\)', '', sp).strip()
            if sp and len(sp) >= 2:
                names.append(sp)

    if not names:
        return [investor_str]
    return names


def generate_subscription_flows(cur, conn):
    """从final事件表生成逐投资人拆分的subscription_flow"""
    print("\n[1/3] 生成 subscription_flow（逐投资人拆分）...")
    events = parse_final_events()
    total = 0

    # 事件类型映射到subscription类型
    type_map = {
        'E:': '设立', 'A:A1': '增资', 'A:A2': '增资', 'A:A3': '增资',
        'A:A4': '增资', 'A:A6(境外)': '境外融资', 'A:A6(境内)': '增资',
        'A:A1/A2': '增资', 'A:A2/A3': '增资', 'A:A1/A3': '增资',
        'B:': '股改', 'F:': '资本公积转增', 'J:': '员工激励',
        'C:': '增资', 'C:C': '增资', 'I:': 'IPO',
        'G:': '吸收合并',
        # D/H类型不算subscription
    }

    for ev in events:
        ev_type = ev['type']
        if ev_type.startswith(('D:', 'H:')):
            continue  # 转让和VIE事件归入share_transfer

        name, code = extract_code_name(ev['company'])
        sub_type = type_map.get(ev_type, ev_type)
        amount, shares, price = parse_amount_price(ev['amount_price'])

        investors = split_investors(ev['investor'])
        for inv in investors:
            inv_type = classify_investor(inv)
            page = _parse_evidence_page(ev['evidence'])

            cur.execute("""
                INSERT INTO zbq_subscription_flow
                    (event_id, company_name, stock_code, event_type, event_date,
                     investor_name, investor_type,
                     subscription_qty_wan, subscription_amount_wan, subscription_price,
                     pdf_page, evidence_text, extraction_method, review_status)
                VALUES (%s,%s,%s,%s,%s, %s,%s, %s,%s,%s, %s,%s,%s,%s)
                ON CONFLICT DO NOTHING
            """, (
                f"{code}_sf_supp_{total:03d}",
                name, code,
                sub_type, ev['date'],
                inv[:200], inv_type,
                shares, amount, price,
                page,
                f"来源: final/八家公司融资事件总表 | 原投资人: {ev['investor']} | 金额/价格: {ev['amount_price']}",
                'supplement_from_final',
                'manual_review',
            ))
            total += 1

    conn.commit()
    print(f"  OK: {total} 条 subscription_flow 记录")
    return total


def generate_share_transfers(cur, conn):
    """从final事件表生成share_transfer_flow"""
    print("\n[2/3] 生成 share_transfer_flow...")
    events = parse_final_events()
    total = 0

    for ev in events:
        ev_type = ev['type']
        if not ev_type.startswith(('D:', 'H:')):
            continue  # 只看转让和VIE事件

        name, code = extract_code_name(ev['company'])
        amount, shares, price = parse_amount_price(ev['amount_price'])
        page = _parse_evidence_page(ev['evidence'])

        # 解析转让方→受让方
        investor_str = ev['investor']
        transferor = None
        transferee = None
        if '→' in investor_str:
            parts = investor_str.split('→', 1)
            transferor = parts[0].strip()
            transferee = parts[1].strip() if len(parts) > 1 else None

        # 映射转让类型
        transfer_type_map = {
            'D:D1': '同一控制下转让', 'D:D1/D3': '同一控制下转让',
            'D:D2': '代持还原', 'D:D4': '市场价转让',
            'D:D5': '批量多对多转让', 'D:D6': '原价退出',
            'H:H1': 'VIE搭建', 'H:H2': 'VIE搭建', 'H:H3': 'VIE搭建',
            'H:H4': 'VIE协议签署', 'H:H5/H7': 'VIE回购+终止',
            'H:H6': '镜像回归',
        }
        transfer_type = transfer_type_map.get(ev_type, ev_type)

        cur.execute("""
            INSERT INTO zbq_share_transfer_flow
                (event_id, company_name, stock_code, event_date, event_type,
                 transferor_name, transferee_name, participant_type,
                 transfer_qty_wan, transfer_amount_wan, transfer_price,
                 pdf_page, evidence_text, extraction_method, review_status)
            VALUES (%s,%s,%s,%s,%s, %s,%s,%s, %s,%s,%s, %s,%s,%s,%s)
            ON CONFLICT DO NOTHING
        """, (
            f"{code}_st_supp_{total:03d}",
            name, code,
            ev['date'], transfer_type,
            transferor, transferee,
            classify_investor(transferor or ''),
            shares, amount, price,
            page,
            f"来源: final/八家公司融资事件总表 | 投资人: {investor_str}",
            'supplement_from_final',
            'manual_review',
        ))
        total += 1

    conn.commit()
    print(f"  OK: {total} 条 share_transfer 记录")
    return total


def generate_equity_snapshots(cur, conn):
    """补全中间快照标记"""
    print("\n[3/3] 生成 equity_snapshot 中间快照...")
    events = parse_final_events()
    total = 0

    # 按公司分组，识别每个事件后的快照点
    company_snapshots = defaultdict(list)
    for ev in events:
        name, code = extract_code_name(ev['company'])
        if not code:
            continue
        ev_type = ev['type']
        # 确定快照标签
        if ev_type.startswith('E:'):
            label = 't0'
        elif ev_type.startswith(('J:', 'A:', 'C:', 'G:')):
            label = f"s{len(company_snapshots[code])}"
        elif ev_type.startswith('B:'):
            label = f"s{len(company_snapshots[code])}"
        elif ev_type.startswith('I:'):
            label = 'IPO后'
        else:
            continue

        company_snapshots[code].append({
            'label': label,
            'trigger_event': f"{ev['date']} {ev['investor']}",
            'date': ev['date'],
            'name': name,
            'code': code,
        })

    # 写入数据库（标记需要PDF提取的快照点）
    for code, snapshots in company_snapshots.items():
        for i, snap in enumerate(snapshots):
            cur.execute("""
                INSERT INTO zbq_equity_snapshot
                    (event_id, company_name, stock_code, snapshot_label, snapshot_date,
                     trigger_event, trigger_event_order,
                     shareholder_name, shareholder_type,
                     pdf_page, evidence_text, extraction_notes, review_status)
                VALUES (%s,%s,%s,%s,%s, %s,%s, %s,%s, %s,%s,%s,%s)
            """, (
                f"{code}_es_supp_snap_{i:03d}",
                snap['name'], code,
                snap['label'][:20], snap['date'][:20],
                snap['trigger_event'][:200], i + 1,
                '（全体股东待PDF提取）', '其他',
                None,
                f"ymx同位置有{snap['label'][:20]}快照",
                '待从PDF提取完整股东名单和持股数据',
                'pending',
            ))
            total += 1

    conn.commit()
    print(f"  OK: {total} 条快照标记（待PDF提取具体股东数据）")


def _parse_evidence_page(evidence_str):
    """从证据字符串提取页码"""
    m = re.search(r'p(\d+)', evidence_str)
    return int(m.group(1)) if m else None


def main():
    conn = connect()
    cur = conn.cursor()

    print("=" * 60)
    print("向杨苗鑫学习 — 补全 zbq 数据")
    print("=" * 60)

    # 清空补充数据（保留原始auto_output导入的数据）
    cur.execute("DELETE FROM zbq_subscription_flow WHERE extraction_method = 'supplement_from_final'")
    cur.execute("DELETE FROM zbq_share_transfer_flow WHERE extraction_method = 'supplement_from_final'")
    cur.execute("DELETE FROM zbq_equity_snapshot WHERE review_status = 'pending_pdf_extraction'")
    conn.commit()

    n_sub = generate_subscription_flows(cur, conn)
    n_st = generate_share_transfers(cur, conn)
    generate_equity_snapshots(cur, conn)

    # 更新公司统计
    cur.execute("""
        UPDATE zbq_companies c SET
            subscription_count = (SELECT COUNT(*) FROM zbq_subscription_flow WHERE stock_code = c.company_id),
            transfer_count = (SELECT COUNT(*) FROM zbq_share_transfer_flow WHERE stock_code = c.company_id),
            snapshot_count = (SELECT COUNT(*) FROM zbq_equity_snapshot WHERE stock_code = c.company_id)
    """)
    conn.commit()

    # 最终统计
    print("\n" + "=" * 60)
    print("补全后数据量:")
    for tbl in ['zbq_subscription_flow', 'zbq_share_transfer_flow', 'zbq_equity_snapshot']:
        cur.execute(f"SELECT COUNT(*) FROM {tbl}")
        print(f"  {tbl}: {cur.fetchone()[0]} 条")

    # 与ymx对比
    print("\n与ymx对比:")
    for tbl, ymx_tbl in [('zbq_subscription_flow', 'ymx_subscription_flow'),
                          ('zbq_share_transfer_flow', 'ymx_share_transfer_flow'),
                          ('zbq_equity_snapshot', 'ymx_equity_snapshot')]:
        cur.execute(f"SELECT COUNT(*) FROM {tbl}")
        zbq_cnt = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM {ymx_tbl}")
        ymx_cnt = cur.fetchone()[0]
        pct = f"{zbq_cnt/ymx_cnt*100:.0f}%" if ymx_cnt else "N/A"
        print(f"  {tbl}: zbq={zbq_cnt} vs ymx={ymx_cnt} ({pct})")

    conn.close()
    print("\nOK!")


if __name__ == "__main__":
    main()
