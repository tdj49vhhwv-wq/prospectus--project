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

OUTPUTS_DIR = PROJECT_ROOT / "outputs"
JSONL_DIR = OUTPUTS_DIR / "week2_jsonl"
JSONL_DIR.mkdir(parents=True, exist_ok=True)

# 8 家
TARGET = {
    "三联锻造": {"code": "001282", "full": "芜湖三联锻造股份有限公司", "src": "manual"},
    "友升股份": {"code": "603418", "full": "上海友升铝业股份有限公司", "src": "review"},
    "黄山谷捷": {"code": "301581", "full": "黄山谷捷股份有限公司", "src": "manual"},
    "云汉芯城": {"code": "301563", "full": "云汉芯城（上海）互联网科技股份有限公司", "src": "manual"},
    "赛分科技": {"code": "688758", "full": "苏州赛分科技股份有限公司", "src": "manual"},
    "影石创新": {"code": "688775", "full": "影石创新科技股份有限公司", "src": "manual"},
    "三协电机": {"code": "920100", "full": "常州三协电机股份有限公司", "src": "review"},
    "星图测控": {"code": "920116", "full": "中科星图测控技术股份有限公司", "src": "review"},
}

DIR_MAP = {"友升股份": "友声股份", "星图测控": "星空测控", "三协电机": "三协电机"}


def load_structured(name):
    """加载手动提取的结构化 JSON"""
    path = OUTPUTS_DIR / name / f"{name}_融资历史_结构化.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("financing_events", [])


# ═══════════════════════════════════════════════════════
# 手动从 review 笔记中提取的三家公司数据
# ═══════════════════════════════════════════════════════

YOUSheng_DATA = [
    # t0: 有限公司设立 (1992-12-04), 注册资本400万美元
    {"event_date": "1992-12-04", "event_type": "设立",
     "source_page": "友声股份2.md 第695-730行",
     "evidence_text": "友升有限成立于1992年12月4日，由徐泾工业公司、友升太平洋美国共同出资设立的中外合资有限责任公司，注册资本为400万美元。徐泾工业公司出资240万美元(60%)，友升太平洋美国出资160万美元(40%)。上海青浦会计师事务所分别于1993年8月20日、1996年12月31日出具验资报告，确认友升有限400万美元注册资金已全部到位。",
     "notes": "有限公司设立。徐泾工业公司以土地使用权出资99.12万美元+货币出资140.88万美元；友升太平洋美国以货币出资160万美元",
     "investors": [
         {"investor_original_name": "上海市青浦县徐泾乡工业公司", "investor_short_name": "徐泾工业公司", "investment_amount": None, "shareholding_ratio_after_event": "60.00%"},
         {"investor_original_name": "友升太平洋(美国)投资有限公司", "investor_short_name": "友升太平洋美国", "investment_amount": None, "shareholding_ratio_after_event": "40.00%"},
     ]},
    # 股改: 有限公司→股份公司 (2020-09-09), 净资产40482.37万折股12000万股
    {"event_date": "2020-09-09", "event_type": "整体变更",
     "source_page": "友声股份2.md 第731-768行",
     "evidence_text": "公司由上海友升铝业有限公司整体变更设立。根据会计师出具的《审计报告》，友升有限截至2020年5月31日的净资产为40,482.37万元。以友升有限截至2020年5月31日的净资产40,482.37万元按3.3735:1的比例折合股本12,000.00万元（每股面值1.00元），净资产超过股本部分全部计入资本公积。2020年9月9日，公司在上海市市场监督管理局登记注册。泽升贸易8,976.00万股(74.80%)，达晨创联基金1,800.00万股(15.00%)，共青城泽升1,020.00万股(8.50%)，罗世兵204.00万股(1.70%)。",
     "notes": "股改。追溯调整后净资产40,437.44万元，评估值48,620.33万元。泽升贸易为控股股东(罗世兵100%持有)",
     "investors": [
         {"investor_original_name": "上海泽升贸易有限公司", "investor_short_name": "泽升贸易", "investment_amount": None, "shares_acquired": 8976.0, "shareholding_ratio_after_event": "74.80%"},
         {"investor_original_name": "深圳市达晨创联私募股权投资基金合伙企业(有限合伙)", "investor_short_name": "达晨创联基金", "investment_amount": None, "shares_acquired": 1800.0, "shareholding_ratio_after_event": "15.00%"},
         {"investor_original_name": "共青城泽升投资管理合伙企业(有限合伙)", "investor_short_name": "共青城泽升", "investment_amount": None, "shares_acquired": 1020.0, "shareholding_ratio_after_event": "8.50%"},
         {"investor_original_name": "罗世兵", "investor_short_name": "罗世兵", "investment_amount": None, "shares_acquired": 204.0, "shareholding_ratio_after_event": "1.70%"},
     ]},
    # 2020-09 增资, +1380万→13380万
    {"event_date": "2020-09-27", "event_type": "增资",
     "source_page": "友声股份2.md 第769-802行",
     "evidence_text": "2020年9月，金浦临港基金、金浦科创基金和上海骁墨与本次增资前公司股东泽升贸易、罗世兵、共青城泽升、达晨创联基金共同签署《投资协议》，约定金浦临港基金、金浦科创基金和上海骁墨分别以7,000万元、3,000万元和1,500万元认购发行人新增注册资本840万元、360万元和180万元。新增股份的认购价格为8.3333元/股。2020年9月30日完成工商变更。增资后：泽升贸易67.09%、达晨创联基金13.45%、共青城泽升7.62%、金浦临港基金6.28%、金浦科创基金2.69%、罗世兵1.52%、上海骁墨1.35%。",
     "notes": "A轮：金浦系(金浦临港+金浦科创)合计10,000万，上海骁墨1,500万。认购价8.33元/股。投后估值约11.15亿",
     "total_investment_amount": 11500.0, "share_price": 8.3333,
     "investors": [
         {"investor_original_name": "上海金浦临港智能科技股权投资基金合伙企业(有限合伙)", "investor_short_name": "金浦临港基金", "investment_amount": 7000.0, "shares_acquired": 840.0, "shareholding_ratio_after_event": "6.28%"},
         {"investor_original_name": "上海金浦科技创业股权投资基金合伙企业(有限合伙)", "investor_short_name": "金浦科创基金", "investment_amount": 3000.0, "shares_acquired": 360.0, "shareholding_ratio_after_event": "2.69%"},
         {"investor_original_name": "上海骁墨信息技术服务中心(有限合伙)", "investor_short_name": "上海骁墨", "investment_amount": 1500.0, "shares_acquired": 180.0, "shareholding_ratio_after_event": "1.35%"},
     ]},
    # 2022-12 增资, +1100.1333万→14480.1333万
    {"event_date": "2022-12-19", "event_type": "增资",
     "source_page": "友声股份2.md 第804-870行",
     "evidence_text": "2022年12月4日，友升股份召开第一届董事会第十六次会议，同意增加注册资本至14,480.1333万元，新增股份的认购价格为33.6323元/股。杉晖创业认购297.3333万股(10,000万元)，上海联炻认购297.3333万股(10,000万元)，安吉璞颉认购148.6667万股(5,000万元)，财投晨源认购89.2万股(3,000万元)，深圳达晨创程认购86.5984万股(2,912.5万元)，杉创智至认购59.4667万股(2,000万元)，杭州达晨创程认购51.959万股(1,747.5万元)，达晨财汇认购29.7333万股(1,000万元)，达晨财智认购29.7333万股(1,000万元)，财智创赢认购10.1093万股(340万元)。合计1,100.1333万股，37,000万元。2022年12月19日完成工商变更。",
     "notes": "B轮：达晨系+杉晖/联炻等10家机构，总融资3.7亿。认购价33.63元/股。投后估值约48.7亿",
     "total_investment_amount": 37000.0, "share_price": 33.6323,
     "investors": [
         {"investor_original_name": "深圳市杉晖创业投资合伙企业(有限合伙)", "investor_short_name": "杉晖创业", "investment_amount": 10000.0, "shares_acquired": 297.3333, "shareholding_ratio_after_event": "2.05%"},
         {"investor_original_name": "上海联炻企业管理中心(有限合伙)", "investor_short_name": "上海联炻", "investment_amount": 10000.0, "shares_acquired": 297.3333, "shareholding_ratio_after_event": "2.05%"},
         {"investor_original_name": "安吉璞颉企业管理合伙企业(有限合伙)", "investor_short_name": "安吉璞颉", "investment_amount": 5000.0, "shares_acquired": 148.6667, "shareholding_ratio_after_event": "1.03%"},
         {"investor_original_name": "江西赣江新区财投晨源股权投资中心(有限合伙)", "investor_short_name": "财投晨源", "investment_amount": 3000.0, "shares_acquired": 89.2, "shareholding_ratio_after_event": "0.62%"},
         {"investor_original_name": "深圳市达晨创程私募股权投资基金企业(有限合伙)", "investor_short_name": "深圳达晨创程", "investment_amount": 2912.5, "shares_acquired": 86.5984, "shareholding_ratio_after_event": "0.60%"},
         {"investor_original_name": "上海杉创智至创业投资合伙企业(有限合伙)", "investor_short_name": "杉创智至", "investment_amount": 2000.0, "shares_acquired": 59.4667, "shareholding_ratio_after_event": "0.41%"},
         {"investor_original_name": "杭州达晨创程股权投资基金合伙企业(有限合伙)", "investor_short_name": "杭州达晨创程", "investment_amount": 1747.5, "shares_acquired": 51.959, "shareholding_ratio_after_event": "0.36%"},
         {"investor_original_name": "海南三亚达晨财汇私募股权投资基金合伙企业(有限合伙)", "investor_short_name": "达晨财汇", "investment_amount": 1000.0, "shares_acquired": 29.7333, "shareholding_ratio_after_event": "0.21%"},
         {"investor_original_name": "深圳市达晨财智创业投资管理有限公司", "investor_short_name": "达晨财智", "investment_amount": 1000.0, "shares_acquired": 29.7333, "shareholding_ratio_after_event": "0.21%"},
         {"investor_original_name": "深圳市财智创赢私募股权投资企业(有限合伙)", "investor_short_name": "财智创赢", "investment_amount": 340.0, "shares_acquired": 10.1093, "shareholding_ratio_after_event": "0.07%"},
     ]},
]

SANXIE_DATA = [
    # 有限公司设立 (2002-11-07)
    {"event_date": "2002-11-07", "event_type": "设立",
     "source_page": "三协电机_招股书_正式稿_20250711.md 第30页",
     "evidence_text": "公司全称: 常州三协电机股份有限公司。证券代码: 920100。注册资本: 5,310.93万元。法定代表人: 盛祎。成立日期: 2002年11月7日。2002年11月至今，盛祎担任三协电机总经理，股份公司成立后担任董事长。",
     "notes": "三协电机有限公司设立。盛祎、朱绶青为共同实际控制人(夫妻，合计控制82.46%)。三协有限→三协股份→三协电机。具体设立时出资结构在发行人历史沿革部分",
     "investors": [
         {"investor_original_name": "盛祎", "investor_short_name": "盛祎", "investment_amount": None, "shareholding_ratio_after_event": "62.97%"},
         {"investor_original_name": "朱绶青", "investor_short_name": "朱绶青", "investment_amount": None, "shareholding_ratio_after_event": "19.49%"},
     ]},
    # 2022年新三板挂牌 + 第一次定增 (2022-08)
    {"event_date": "2022-08-09", "event_type": "增资",
     "source_page": "三协电机_招股书_正式稿_20250711.md 第31-32页",
     "evidence_text": "2022年6月24日，公司召开第二届董事会第四次会议审议通过了《关于<常州三协电机股份有限公司股票定向发行说明书>的议案》。本次股票发行价格为4.48元/股，共发行普通股530.00万股，募集资金总额为2,374.40万元，募集资金用途为补充流动资金。2022年8月15日，苏亚金诚出具《验资报告》（苏亚锡验[2022]7号），经审验，截至2022年8月9日，公司已收到稳正景明、长泽创投缴纳的出资款2,374.40万元。",
     "notes": "新三板挂牌后第一次定增。稳正景明+长泽创投认购530万股，4.48元/股，共2,374.40万元。稳正景明目前持股486.70万股(9.16%)",
     "total_investment_amount": 2374.40, "share_price": 4.48,
     "investors": [
         {"investor_original_name": "深圳市稳正景明创业投资企业(有限合伙)", "investor_short_name": "稳正景明", "investment_amount": None, "shares_acquired": None, "shareholding_ratio_after_event": "9.16%"},
         {"investor_original_name": "深圳市稳正长泽创业投资企业(有限合伙)", "investor_short_name": "长泽创投", "investment_amount": None, "shares_acquired": None, "shareholding_ratio_after_event": None},
     ]},
    # 2023年第二次定增 (2023-09)
    {"event_date": "2023-09-06", "event_type": "增资",
     "source_page": "三协电机_招股书_正式稿_20250711.md 第32页",
     "evidence_text": "2023年5月26日，公司召开第二届董事会第十三次会议审议通过了《关于<常州三协电机股份有限公司股票定向发行说明书>的议案》。本次股票拟发行价格为5.41元/股，拟发行普通股321.50万股，拟募集资金总额为1,739.32万元。2023年9月8日，苏亚金诚出具《验资报告》（苏亚验[2023]10号），经审验，截至2023年9月6日，公司已收到盛祎、盛松、薛小丽、倪进宽、余方成、吴春扣、陆宇君、戈翔俊、陈都亮、圣利、董雪强、文涛、付荷庆、陈韵和盛月瑶15名认购人缴纳的出资款1,723.09万元。",
     "notes": "第二次定增。15名认购人(盛祎及员工/关联方)认购321.50万股，5.41元/股，共1,723.09万元。2023年12月权益分派:10转增3.8股+派现3.90元",
     "total_investment_amount": 1723.09, "share_price": 5.41,
     "investors": [
         {"investor_original_name": "盛祎等15名自然人", "investor_short_name": "盛祎等15人", "investment_amount": 1723.09, "shares_acquired": 321.50, "shareholding_ratio_after_event": None},
     ]},
]

XINGTU_DATA = [
    # 有限公司设立 (2016-12-14)
    {"event_date": "2016-12-14", "event_type": "设立",
     "source_page": "星图测控_招股书_正式稿_20241220.md 第48页",
     "evidence_text": "2016年12月，四方股份、罗永红、王金林共同出资设立星图测控有限，其中，四方股份出资1,200万元（对应持有星图测控有限60%股权）；罗永红出资400万元（对应持有星图测控有限20%股权）；王金林出资400万元（对应持有星图测控有限20%股权）。罗永红、王金林于测控有限设立时所持有的全部股权分别系为牛威和吴功友代持。",
     "notes": "有限公司设立。注册资本未明确，四方股份(中科星图前身关联方)60%，罗永红(代牛威)20%，王金林(代吴功友)20%。代持于2017年10月解除",
     "investors": [
         {"investor_original_name": "四方股份", "investor_short_name": "四方股份", "investment_amount": 1200.0, "shareholding_ratio_after_event": "60.00%"},
         {"investor_original_name": "牛威(罗永红代持)", "investor_short_name": "牛威", "investment_amount": 400.0, "shareholding_ratio_after_event": "20.00%"},
         {"investor_original_name": "吴功友(王金林代持)", "investor_short_name": "吴功友", "investment_amount": 400.0, "shareholding_ratio_after_event": "20.00%"},
     ]},
    # 代持解除 (2017-10)
    {"event_date": "2017-10-25", "event_type": "股权转让",
     "source_page": "星图测控_招股书_正式稿_20241220.md 第48页",
     "evidence_text": "2017年10月9日，星图测控有限的股东会作出决议，同意：罗永红将其持有的星图测控有限20%股权转让予牛威；王金林将其持有的星图测控有限20%股权转让予吴功友。罗永红与牛威、王金林与吴功友于2017年10月9日分别签署了《股权转让协议》。本次股权转让系还原股权代持，故牛威、吴功友未向罗永红和王金林实际支付股权转让对价。星图测控有限于2017年10月25日就上述股权转让办理了工商变更登记手续。",
     "notes": "代持还原：罗永红→牛威，王金林→吴功友。零对价转让",
     "total_investment_amount": 0,
     "investors": [
         {"investor_original_name": "牛威", "investor_short_name": "牛威", "investment_amount": 0, "shareholding_ratio_after_event": "20.00%"},
         {"investor_original_name": "吴功友", "investor_short_name": "吴功友", "investment_amount": 0, "shareholding_ratio_after_event": "20.00%"},
     ]},
    # IPO前股权结构 (2024-06-30时点)
    {"event_date": "2024-06-30", "event_type": "其他",
     "source_page": "星图测控_招股书_正式稿_20241220.md 第47页",
     "evidence_text": "截至本招股说明书签署日，公司总股本为82,500,000股。发行前股本结构：中科星图38,250,000股(46.36%)，策星九天23,450,781股(28.43%)，幸福一期9,174,219股(11.12%)，策星揽月4,125,000股(5.00%)，幸福二期3,000,000股(3.64%)，策星银河2,790,000股(3.38%)，策星逐日1,710,000股(2.07%)。合计82,500,000股(100.00%)。",
     "notes": "IPO前股权结构(2024年中报时点)。中科星图为控股股东(46.36%)，实际控制人为中国科学院空天院。策星系为员工持股平台(38.88%合计)",
     "investors": [
         {"investor_original_name": "中科星图股份有限公司", "investor_short_name": "中科星图", "investment_amount": None, "shares_acquired": 3825.0, "shareholding_ratio_after_event": "46.36%"},
         {"investor_original_name": "策星九天", "investor_short_name": "策星九天", "investment_amount": None, "shares_acquired": 2345.0781, "shareholding_ratio_after_event": "28.43%"},
         {"investor_original_name": "幸福一期", "investor_short_name": "幸福一期", "investment_amount": None, "shares_acquired": 917.4219, "shareholding_ratio_after_event": "11.12%"},
         {"investor_original_name": "策星揽月", "investor_short_name": "策星揽月", "investment_amount": None, "shares_acquired": 412.5, "shareholding_ratio_after_event": "5.00%"},
         {"investor_original_name": "幸福二期", "investor_short_name": "幸福二期", "investment_amount": None, "shares_acquired": 300.0, "shareholding_ratio_after_event": "3.64%"},
         {"investor_original_name": "策星银河", "investor_short_name": "策星银河", "investment_amount": None, "shares_acquired": 279.0, "shareholding_ratio_after_event": "3.38%"},
         {"investor_original_name": "策星逐日", "investor_short_name": "策星逐日", "investment_amount": None, "shares_acquired": 171.0, "shareholding_ratio_after_event": "2.07%"},
     ]},
]


def load_review_events(name):
    """加载 review 笔记中的事件（使用手动提取的结构化数据）"""
    if name == "友升股份":
        return YOUSheng_DATA
    elif name == "三协电机":
        return SANXIE_DATA
    elif name == "星图测控":
        return XINGTU_DATA
    return []


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
    print("=" * 60)

    stats = {}

    for name, info in TARGET.items():
        print(f"\n处理: {name} ({info['code']}) [{info['src']}]")

        if info["src"] == "manual":
            events = load_structured(name)
        else:
            events = load_review_events(name)

        if not events:
            print(f"  ⚠ 无事件数据")
            continue

        # 拆出两类记录
        sub_flows = build_subscription_flows(events, info)
        eq_snaps = build_equity_snapshots(events, info)

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
