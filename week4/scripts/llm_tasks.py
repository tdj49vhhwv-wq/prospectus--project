#!/usr/bin/env python3
"""
Week 4 LLM 三任务实现

任务1: 拆分"15名认购人"名单（中文姓名分词+数量验证）
任务2: 判断"拟募集vs实际收到"差异（语义差异检测）
任务3: 理解"10转增3.8股"的股本变化语义（数学推理+事件分类）

方法: 规则层（确定性高）+ LLM prompt层（语义理解需要）双路径
输入: week4/outputs/三协电机_PEVC_原文.md
输出: week4/outputs/llm_tasks_output.json
"""
import json
import re
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import *


# ============================================================
# 任务1: 拆分"15名认购人"名单
# ============================================================

# 已知中文姓名特征: 2-3字，常见姓氏
COMMON_SURNAMES = set('王李张刘陈杨黄赵周吴徐孙马胡朱郭何罗高林郑梁谢唐许冯宋韩邓彭曹曾田萧潘袁蔡蒋余于杜叶程魏苏吕丁任卢姚沈钟姜崔谭陆范汪廖石金韦贾夏付方白邹孟熊秦邱江尹薛闫段雷侯龙史陶黎贺顾毛郝龚邵万钱严覃武戴莫孔向汤温芦')

class ChineseNameSplitter:
    """中文姓名拆分器：用规则 + LLM prompt 两阶段"""

    def __init__(self):
        self.surnames = COMMON_SURNAMES

    def split_by_rules(self, text: str) -> list:
        """
        规则层: 按分隔符拆分 + 姓名验证

        覆盖: "盛祎、盛松、薛小丽、...、陈韵和盛月瑶"
        """
        # Step 1: 提取名字列表段
        # 先定位2023年段落（含"拟发行价格"或"15名认购人"），再从中提取名字
        section_2023 = re.search(
            r'2、2023\s*年股票发行[\s\S]+?本次股票发行新增股份于2023',
            text
        )
        search_text = section_2023.group(0) if section_2023 else text

        # 匹配"已收到...N名认购人"(2023年定增)
        # 用 [\s\S] 跨行匹配，但限制在2023段落内
        m = re.search(
            r'已收到\s*([\s\S]+?)\s*(\d+)\s*名\s*认购人',
            search_text
        )
        if not m:
            # 兜底: 匹配"已收到...缴纳的出资款"(2022年定增)
            m = re.search(
                r'已收到\s*(.+?)\s*缴纳的出资款',
                text
            )
            expected_count = None

        if not m:
            return []

        name_str = m.group(1).strip()
        groups = m.groups()
        expected_count = int(groups[1]) if len(groups) >= 2 else None

        # Step 2: 按分隔符拆分
        # "盛祎、盛松、薛小丽、...陈韵和盛月瑶"
        # 处理"和"：如果"和"前面有"、"或"，它是连接词不是人名一部分
        parts = re.split(r'[、，]', name_str)
        names = []
        for p in parts:
            p = p.strip()
            # 处理 "陈韵和盛月瑶" → "陈韵" + "盛月瑶"
            if '和' in p and len(p) > 4:  # 两个2字名+连接词 > 4字
                sub_parts = p.split('和')
                for sp in sub_parts:
                    sp = sp.strip()
                    if self._is_valid_name(sp):
                        names.append(sp)
            elif self._is_valid_name(p):
                names.append(p)

        # 验证数量
        if expected_count and len(names) != expected_count:
            # 拆分不完整，尝试更激进的切割
            # "陈韵和盛月瑶" → 2人
            for i, name in enumerate(names):
                if '和' in name and len(name) > 3:
                    parts = name.split('和')
                    valid_parts = [p for p in parts if self._is_valid_name(p)]
                    if valid_parts:
                        names[i:i+1] = valid_parts

        return names

    def _is_valid_name(self, s: str) -> bool:
        """验证是否为合法中文姓名"""
        if not (2 <= len(s) <= 4):
            return False
        if not all('一' <= c <= '鿿' for c in s):
            return False
        # 姓在常见姓列表中
        if s[0] not in self.surnames:
            # 复姓 or 罕见姓也可以
            pass
        return True

    def split_with_llm_prompt(self, text: str) -> dict:
        """
        LLM层: 生成 prompt，供 LLM 辅助拆分

        用于规则层无法完全覆盖的边缘情况
        """
        prompt = f"""请将以下招股书原文中的认购人名单拆分为独立的姓名列表。

原文: "{text}"

要求:
1. 每个姓名应为2-3个中文字符
2. "和"在此语境中是连接词，不是人名的一部分
3. 拆分后验证：总数应等于原文中"等N名"的N
4. 输出严格JSON格式: {{"names": ["姓名1", "姓名2", ...], "count": N, "verified": true/false}}

只输出JSON，不要解释。"""

        return {
            "task": "拆分15名认购人名单",
            "method": "llm_prompt",
            "prompt": prompt,
            "expected_output_schema": {
                "names": ["list of strings"],
                "count": "int",
                "verified": "bool"
            }
        }


# ============================================================
# 任务2: 判断"拟募集 vs 实际收到"差异
# ============================================================

class FundraisingDiscrepancyDetector:
    """募资差异检测器"""

    def extract_amounts(self, text: str) -> dict:
        """从原文中提取拟募集和实际收到的金额（专找2023年定增段）"""
        result = {
            "planned_amount": None,
            "actual_amount": None,
            "price_per_share": None,
            "shares_issued": None,
            "expected_amount": None,  # price × shares
            "difference": None,
            "difference_pct": None,
            "verdict": None,
        }

        # 定位到2023年股票发行段落（含"拟募集"关键词的那个）
        m_section = re.search(
            r'2023\s*年股票发行.*?'
            r'拟发行价格[为：:]?\s*(\d+\.?\d*)\s*元/股.*?'
            r'拟发行普通股\s*(\d+[\d,]*\.?\d*)\s*万股.*?'
            r'拟募集资金总额[为：:]?\s*(\d+[\d,]*\.?\d*)\s*万元.*?'
            r'已收到.+?15\s*名.*?出资款\s*(\d+[\d,]*\.?\d*)\s*万元',
            text, re.DOTALL
        )
        if m_section:
            result["price_per_share"] = float(m_section.group(1))
            result["shares_issued"] = float(m_section.group(2).replace(',', ''))
            result["planned_amount"] = float(m_section.group(3).replace(',', ''))
            result["actual_amount"] = float(m_section.group(4).replace(',', ''))
        else:
            # fallback: try separate matches
            m = re.search(r'拟募集资金总额[为：:]?\s*(\d+[\d,]*\.?\d*)\s*万元', text)
            if m:
                result["planned_amount"] = float(m.group(1).replace(',', ''))

            m = re.search(r'15\s*名\s*认购人.+?出资款\s*(\d+[\d,]*\.?\d*)\s*万元', text)
            if m:
                result["actual_amount"] = float(m.group(1).replace(',', ''))

            m = re.search(r'拟发行价格[为：:]?\s*(\d+\.?\d*)\s*元/股', text)
            if m:
                result["price_per_share"] = float(m.group(1))

            m = re.search(r'拟发行普通股\s*(\d+[\d,]*\.?\d*)\s*万股', text)
            if m:
                result["shares_issued"] = float(m.group(1).replace(',', ''))

        # 计算预期金额
        if result["price_per_share"] and result["shares_issued"]:
            result["expected_amount"] = round(
                result["price_per_share"] * result["shares_issued"], 2
            )

        # 差异分析
        if result["expected_amount"] and result["actual_amount"]:
            result["difference"] = round(
                result["expected_amount"] - result["actual_amount"], 2
            )
            if result["expected_amount"] > 0:
                result["difference_pct"] = round(
                    abs(result["difference"]) / result["expected_amount"] * 100, 2
                )

        return result

    def classify_discrepancy(self, amounts: dict) -> dict:
        """
        分类差异性质:
        - "正常": 拟募集≠实际收到是招股书常见现象（预计 vs 验资）
        - "可疑": 差异过大或来源矛盾
        - "待复核": 需要人工确认
        """
        diff = amounts.get("difference", 0)
        pct = amounts.get("difference_pct", 0)

        if diff is None or pct is None:
            return {"verdict": "待复核", "reason": "无法计算差异"}

        if pct < 1.0:
            return {
                "verdict": "正常",
                "reason": f"差异{pct}% < 1%，拟募集为预计值，实际收到以验资报告为准。"
                          f"拟募集{amounts['planned_amount']}万 → 实际{amounts['actual_amount']}万，差额{diff}万。"
                          f"建议: 以实际收到金额为准，拟募集金额放入notes。"
            }
        elif pct < 3.0:
            return {
                "verdict": "可疑",
                "reason": f"差异{pct}%在1-3%之间，需人工复核是否因部分认购人少缴或四舍五入。"
            }
        else:
            return {
                "verdict": "待复核",
                "reason": f"差异{pct}% > 3%，可能数据提取错误，需回PDF核对原文。"
            }

    def generate_llm_prompt(self, text: str, amounts: dict) -> dict:
        """生成 LLM prompt 用于语义层面的差异判断"""
        prompt = f"""分析以下招股书中的募资金额差异:

原文:
"{text[:500]}"

数据:
- 发行价格: {amounts['price_per_share']}元/股
- 发行数量: {amounts['shares_issued']}万股
- 价格×数量 = {amounts['expected_amount']}万元（预期募集）
- 拟募集资金: {amounts['planned_amount']}万元
- 实际收到: {amounts['actual_amount']}万元
- 差额: {amounts['difference']}万元 ({amounts['difference_pct']}%)

请判断:
1. 这个差异是正常的（拟募集是预计、验资是实际）还是异常的？
2. 应该以哪个数字为准填入结构化数据？
3. 是否需要标记"待复核"？

输出JSON: {{"verdict": "正常|可疑|待复核", "primary_value": "planned|actual", "reason": "一句话解释"}}"""

        return {
            "task": "判断募资差异",
            "method": "llm_prompt",
            "prompt": prompt,
            "amounts": amounts,
        }


# ============================================================
# 任务3: 理解"10转增3.8股"的股本变化语义
# ============================================================

class EquityConversionParser:
    """资本公积转增股本解析器"""

    def parse(self, text: str) -> dict:
        """从原文解析转增事件"""
        result = {
            "event_type": "资本公积转增",
            "ratio": None,        # 转增比例 (如 3.8/10 = 0.38)
            "ratio_text": None,   # 原文表述 (如 "10转增3.80")
            "pre_shares": None,   # 转增前总股本（万股）
            "converted_shares": None,  # 转增股数（万股）
            "post_shares": None,  # 转增后总股本（万股）
            "verified": False,
        }

        # 提取转增比例
        m = re.search(r'每\s*10\s*股\s*转增\s*(\d+\.?\d*)\s*股', text)
        if m:
            ratio_val = float(m.group(1))
            result["ratio"] = ratio_val / 10
            result["ratio_text"] = f"10转增{m.group(1)}"

        # 提取转增前应分配股数
        m = re.search(r'应分配股数\s*(\d+[\d,]*)\s*股', text)
        if m:
            result["pre_shares"] = float(m.group(1).replace(',', '')) / 10000  # 转万股

        # 提取转增数量
        m = re.search(r'转增\s*(\d+[\d,]*\.?\d*)\s*万股', text)
        if m:
            result["converted_shares"] = float(m.group(1).replace(',', ''))

        # 验证: pre_shares × ratio ≈ converted_shares
        if result["pre_shares"] and result["ratio"] and result["converted_shares"]:
            expected = result["pre_shares"] * result["ratio"]
            diff_pct = abs(expected - result["converted_shares"]) / result["converted_shares"] * 100
            if diff_pct < 0.5:
                result["verified"] = True
                result["post_shares"] = result["pre_shares"] + result["converted_shares"]

        return result

    def generate_llm_prompt(self, text: str, parsed: dict) -> dict:
        """生成LLM prompt验证转增事件的语义理解"""
        prompt = f"""分析以下招股书中的权益分派事件:

原文:
"{text[:400]}"

已知解析结果:
- 转增比例: {parsed['ratio_text']} (ratio={parsed['ratio']})
- 转增前应分配股数: {parsed['pre_shares']}万股
- 转增股数: {parsed['converted_shares']}万股
- 验证: 转增前 × 比例 = {parsed['pre_shares']} × {parsed['ratio']} = {parsed['pre_shares'] * parsed['ratio'] if parsed['pre_shares'] and parsed['ratio'] else '?'}万股 (PDF值: {parsed['converted_shares']}万股)

请判断:
1. 此事件应归类为"资本公积转增"吗？还是有其他属性？
2. 这不是外部融资事件——转增不增加公司现金，只是股本内部调整。如何与真正的增资事件区分？
3. 生成一个 subscription_flow 行，event_context="资本公积转增"，shares_subscribed=转增总股数，amount_subscribed=0（非现金认购）

输出JSON: {{"event_type": "资本公积转增", "is_external_financing": false, "subscription_flow": {{...}}}}"""

        return {
            "task": "理解资本公积转增语义",
            "method": "llm_prompt",
            "prompt": prompt,
            "parsed": parsed,
        }


# ============================================================
# 主函数: 运行三个任务
# ============================================================

def main():
    # 读取原文
    md_path = OUTPUTS_DIR / "三协电机_PEVC_原文.md"
    if not md_path.exists():
        print(f"✗ 找不到原文: {md_path}")
        print("  请先运行: python3 scripts/extract_pevc_raw.py")
        return 1

    text = md_path.read_text(encoding='utf-8')

    print("=" * 60)
    print("LLM 三任务: 三协电机 PE/VC 语义理解")
    print("=" * 60)

    output = {
        "generated_at": datetime.now().isoformat(),
        "company": TARGET,
    }

    # ── 任务1: 拆分15人名单 ──
    print("\n[任务1] 拆分15名认购人名单")
    splitter = ChineseNameSplitter()
    names = splitter.split_by_rules(text)

    task1 = {
        "method": "rules",
        "result": names,
        "count": len(names),
        "verified": len(names) == 15,
    }
    if len(names) != 15:
        task1["llm_prompt"] = splitter.split_with_llm_prompt(text)

    output["task1_split_names"] = task1
    print(f"  规则拆分: {len(names)}人 {names}")
    print(f"  验证: {'✅ 15人' if len(names) == 15 else '⚠ 需LLM辅助'}")

    # ── 任务2: 募资差异检测 ──
    print("\n[任务2] 判断拟募集vs实际收到差异")
    detector = FundraisingDiscrepancyDetector()
    amounts = detector.extract_amounts(text)
    classification = detector.classify_discrepancy(amounts)

    task2 = {
        "amounts": amounts,
        "classification": classification,
    }
    if classification["verdict"] != "正常":
        task2["llm_prompt"] = detector.generate_llm_prompt(text, amounts)

    output["task2_discrepancy"] = task2
    print(f"  拟募集: {amounts['planned_amount']}万")
    print(f"  预期(价格×数量): {amounts['expected_amount']}万")
    print(f"  实际收到: {amounts['actual_amount']}万")
    print(f"  差额: {amounts['difference']}万 ({amounts['difference_pct']}%)")
    print(f"  判定: {classification['verdict']} — {classification['reason']}")

    # ── 任务3: 转增解析 ──
    print("\n[任务3] 理解10转增3.8股")
    parser = EquityConversionParser()
    parsed = parser.parse(text)

    task3 = {"parsed": parsed}
    if not parsed["verified"]:
        task3["llm_prompt"] = parser.generate_llm_prompt(text, parsed)

    output["task3_equity_conversion"] = task3
    print(f"  转增比例: {parsed['ratio_text']} (ratio={parsed['ratio']})")
    print(f"  转增前股本: {parsed['pre_shares']}万股")
    print(f"  转增股数: {parsed['converted_shares']}万股")
    print(f"  转增后股本: {parsed['post_shares']}万股")
    print(f"  验证: {'✅ 计算一致' if parsed['verified'] else '⚠ 需LLM辅助'}")

    # ── 生成 subscription_flow 补充行 ──
    supplement_sf = []
    if parsed["verified"]:
        supplement_sf.append({
            "record_type": "subscription_flow",
            "company_name": TARGET["full_name"],
            "stock_code": TARGET["code"],
            "source_page": "PDF p32",
            "subscription_date": "2023-12-01",
            "subscriber_name": "全体股东",
            "shares_subscribed": parsed["converted_shares"],
            "amount_subscribed": 0,
            "price_per_share": 0,
            "event_context": "资本公积转增",
            "investor_type": "其他",
            "evidence_text": text[text.find("每10股转增"):text.find("每10股转增")+200].strip(),
            "data_source": "calculated",
            "notes": f"10转增{parsed['ratio']*10:.2f}股。转增前总股本{parsed['pre_shares']}万股，转增{parsed['converted_shares']}万股，转增后{parsed['post_shares']}万股。非外部融资，无现金对价。",
        })

    # 统计
    n_rules = 0
    if task1.get("verified"):
        n_rules += 1
    if task2.get("classification", {}).get("verdict") == "正常":
        n_rules += 1
    if task3.get("parsed", {}).get("verified"):
        n_rules += 1
    n_llm = 3 - n_rules

    print(f"\n{'='*60}")
    print(f"总结: 规则可覆盖 {n_rules}/3 任务, {n_llm} 需LLM辅助")

    # ── 保存输出 ──
    output["supplement_subscription_flows"] = supplement_sf
    output["summary"] = {
        "tasks_total": 3,
        "rules_solved": n_rules,
        "llm_required": n_llm,
    }

    output_path = OUTPUTS_DIR / "llm_tasks_output.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✓ 输出: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
