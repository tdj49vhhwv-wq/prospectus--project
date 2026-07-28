#!/usr/bin/env python3
"""
回归测试: VIE 误报修复验证

老师要求: 修复 VIE 等误报，遍历全部候选锚点，并将当前错误固定为回归测试。

测试用例:
  1. 非VIE公司（三协电机等7家）不应产生任何VIE事件
  2. 影石创新（688775）应正确检测H1-H9子事件
  3. 含"不存在VIE"/"无协议控制"的页面不应触发误报
  4. 局部上下文含否定语义时不应触发
  5. 同一页多个锚点应全部遍历
"""
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


class MockPage:
    """模拟 PyMuPDF 页面对象"""
    def __init__(self, text):
        self._text = text
    def get_text(self, fmt="text"):
        return self._text


class MockDoc:
    """模拟 PyMuPDF document 对象，支持 len(doc) 和 doc[i]"""
    def __init__(self, pages_text: list):
        self._pages = [MockPage(t) for t in pages_text]
    def __len__(self):
        return len(self._pages)
    def __getitem__(self, i):
        return self._pages[i]
    def __iter__(self):
        return iter(self._pages)


def make_mock_doc(pages_text: list):
    """构造模拟 PyMuPDF document 对象"""
    return MockDoc(pages_text)


def test_non_vie_company_returns_empty():
    """测试1: 非VIE公司不应产生任何VIE事件"""
    from extract_pevc import detect_vie_events

    # 模拟三协电机 — 页面中包含"协议控制"字样但在否定语境中
    pages = [
        "第五节 发行人基本情况。本公司不存在协议控制架构，未搭建VIE结构，不涉及境外红筹架构。公司历史股东包括盛祎、朱绶青等自然人股东。",
        "本次股票定向发行价格为5.41元/股，发行普通股318.50万股，募集资金总额1,723.09万元。发行对象为15名自然人。",
        "截至本招股说明书签署日，公司总股本为5,310.93万股。控股股东盛祎持股62.97%，实际控制人未发生变更。",
    ]
    doc = make_mock_doc(pages)
    company = {"name": "三协电机", "code": "920100"}

    result = detect_vie_events(doc, company)
    assert result == [], f"非VIE公司不应有VIE事件，但得到 {len(result)} 条"
    print("  PASS: 非VIE公司(920100)返回空列表")


def test_non_vie_company_with_keywords():
    """测试2: 非VIE公司即使页面含VIE关键词也不应触发"""
    from extract_pevc import detect_vie_events

    pages = [
        "关于协议控制：本公司不涉及VIE架构，无协议控制安排。公司不存在境外上市主体，未搭建红筹架构，不存在开曼公司。",
        "股权出质注销：本公司历史股东张三已完成股权出质注销手续。该股权出质系个人融资担保，与协议控制无关。不存在协议控制。",
        "开曼岚锋设立：此段为引用影石创新案例说明行业情况，非本公司实际情况。本公司不存在协议控制架构，无VIE相关安排。",
    ]
    doc = make_mock_doc(pages)

    # 测试所有非VIE公司
    for code, name in [("001282", "三联锻造"), ("301563", "云汉芯城"),
                       ("603418", "友升股份"), ("688758", "赛分科技"),
                       ("920116", "星图测控"), ("301581", "黄山谷捷")]:
        company = {"name": name, "code": code}
        result = detect_vie_events(doc, company)
        assert result == [], f"{name}({code})不应有VIE事件，但得到 {len(result)} 条"
    print("  PASS: 所有非VIE公司(6家)含关键词时返回空列表")


def test_vie_company_detects_events():
    """测试3: 影石创新应正确检测H1-H9子事件"""
    from extract_pevc import detect_vie_events

    # 每页文本 > 50 字符，模拟真实招股书页面
    pages = [
        "（一）境外架构搭建。2015年3月，公司创始人刘靖康设立开曼岚锋，注册于开曼群岛，作为境外融资及拟上市主体，注册资本5万美元。",
        "（二）中间层设立。2015年6月，开曼岚锋设立香港岚锋作为中间控股公司，用于持有境内外商独资企业的全部股权。",
        "（三）WFOE设立。2015年9月，香港岚锋设立外商独资企业北京岚锋科技有限公司，注册资本100万美元，从事技术研发。",
        "（四）协议控制。2015年12月，北京WFOE与境内运营实体签署协议控制相关协议，包括独家服务协议、股权质押协议、独家购买权协议。",
        "（五）境外回购。2018年5月，开曼岚锋回购境外投资人所持全部股份，境外财务投资人退出，回购对价合计2,000万美元。",
        "（六）镜像回归。镜像回归完成后，各股东持股比例保持不变，境内外等比例对应，不存在利益输送或损害公司利益的情形。",
        "（七）VIE解除。2019年3月，各方签署终止协议，退出协议控制架构，全部控制协议终止，VIE结构正式解除。",
        "（八）出质注销。2019年4月，相关股东完成股权出质注销登记手续，股权质押全部解除，不存在权利限制。",
        "（九）实体注销。截至本招股说明书签署日，已完成VIE实体注销，岚锋科技已注销完毕，不存在协议控制架构。",
    ]
    doc = make_mock_doc(pages)
    company = {"name": "影石创新", "code": "688775"}

    result = detect_vie_events(doc, company)
    stages_found = {r["vie_stage"] for r in result}
    expected_stages = {"H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9"}

    assert stages_found == expected_stages, \
        f"影石创新应检测到全部9个子事件，实际: {stages_found}，缺失: {expected_stages - stages_found}"
    print(f"  PASS: 影石创新检测到全部{len(result)}个VIE子事件")


def test_false_positive_negation_context():
    """测试4: 否定语境不应触发误报"""
    from extract_pevc import detect_vie_events

    # 影石创新的页面，但包含否定语境的段落
    pages = [
        "关于公司架构的说明：本公司不存在协议控制架构。未搭建VIE结构。不涉及协议控制安排。公司采用直接持股方式。",
        "关于出质注销的说明：此处讨论的是普通股权质押解除，非VIE相关。不存在协议控制。该出质系个人贷款担保。",
        # 真实VIE描述页（>50字符）
        "（一）境外架构搭建。2015年3月，公司创始人设立开曼岚锋，注册于开曼群岛，作为境外上市主体，注册资本5万美元。",
    ]
    doc = make_mock_doc(pages)
    company = {"name": "影石创新", "code": "688775"}

    result = detect_vie_events(doc, company)
    # 第0、1页是否定语境，不应触发；第2页是真实事件
    for r in result:
        assert r["source_page"] != "PDF p1", "否定语境页(p1)不应触发VIE事件"
        assert r["source_page"] != "PDF p2", "否定语境页(p2)不应触发VIE事件"
    # 应该只有H1从第3页检测到
    assert any(r["vie_stage"] == "H1" for r in result), "真实VIE事件(H1)应被检测到"
    print(f"  PASS: 否定语境正确过滤，真实事件正确保留 ({len(result)}条)")


def test_all_anchor_points_traversed():
    """测试5: 同一页多个锚点应全部遍历"""
    from extract_pevc import detect_vie_events

    # 一页中包含多个VIE事件（>50字符）
    pages = [
        "2015年3月设立开曼岚锋，注册于开曼群岛。同年6月开曼岚锋设立香港岚锋作为中间控股。"
        "9月香港岚锋设立外商独资企业北京岚锋科技有限公司。"
        "12月签署协议控制相关独家服务协议、股权质押协议等一揽子控制安排。",
    ]
    doc = make_mock_doc(pages)
    company = {"name": "影石创新", "code": "688775"}

    result = detect_vie_events(doc, company)
    stages = {r["vie_stage"] for r in result}
    assert "H1" in stages, "应检测到H1(开曼岚锋设立)"
    assert "H2" in stages, "应检测到H2(香港岚锋设立)"
    assert "H3" in stages, "应检测到H3(WFOE设立)"
    assert "H4" in stages, "应检测到H4(VIE协议签署)"
    print(f"  PASS: 单页多锚点全部遍历，检测到 {len(result)} 个事件")


if __name__ == "__main__":
    print("=" * 60)
    print("VIE 误报回归测试")
    print("=" * 60)

    tests = [
        test_non_vie_company_returns_empty,
        test_non_vie_company_with_keywords,
        test_vie_company_detects_events,
        test_false_positive_negation_context,
        test_all_anchor_points_traversed,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR: {t.__name__}: {type(e).__name__}: {e}")
            failed += 1

    print(f"\n结果: {passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
