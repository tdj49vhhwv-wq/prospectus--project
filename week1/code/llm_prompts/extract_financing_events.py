#!/usr/bin/env python3
"""
可执行 LLM Prompt: 从招股书融资历史文本中提取结构化融资事件

用法:
  python3 extract_financing_events.py <候选文本文件路径>

输出: 符合 Schema v2.0 的 JSON（stdout）

说明:
  本文件是老师要求的"可执行 prompt"，不是文档中的示例。
  可以直接替换 API_KEY 后运行，也可以作为 prompt 模板供其他系统调用。
"""

import sys
import json
from pathlib import Path

# ============================================================
# 可执行 Prompt: 融资事件提取
# ============================================================
EXTRACTION_PROMPT = """你是一个专业的金融数据提取助手。请从以下招股说明书文本中，提取所有融资历史事件。

## 输出格式要求（严格遵守）

输出一个 JSON 数组，每个元素是一个融资事件对象：

{
  "event_order": 整数，按时间顺序编号，
  "event_date": "YYYY-MM-DD 或 YYYY-MM 格式",
  "date_type": "工商变更日" | "协议签署日" | "未说明",
  "event_type": "增资" | "股权转让" | "整体变更" | "吸收合并" | "设立" | "改制" | "VIE搭建" | "VIE拆除" | "其他",
  "disclosed_round": "原始披露的轮次名称，如A轮/B轮，若未披露则填'未披露'",
  "inferred_round": "人工推断的轮次（天使轮/A轮/B轮/C轮/D轮/Pre-IPO/员工股权激励/公司设立/改制），需给出推断依据",
  "round_inference_basis": "推断依据说明",
  "total_investment_amount": 数值（万元人民币），无则填 null,
  "currency": "CNY" | "USD" | "HKD",
  "share_price": 每股价格（元），无则填 null,
  "pre_money_valuation": 投前估值（万元），无则填 null,
  "post_money_valuation": 投后估值（万元），无则填 null,
  "valuation_basis": "估值计算依据说明",
  "investors": [
    {
      "investor_original_name": "投资者完整名称",
      "investor_short_name": "简称",
      "investor_type": "PE" | "VC" | "产业资本" | "政府基金" | "自然人" | "员工持股平台" | "其他",
      "is_pevc": "yes" | "no" | "uncertain",
      "investment_amount": 投资金额（万元），无则填 null,
      "shares_acquired": 获得股份数，无则填 null,
      "shareholding_ratio_after_event": "持股比例（如 25.00%）",
      "exit_status_before_ipo": "未退出" | "全部退出" | "部分退出" | "无法判断"
    }
  ],
  "source_section": "来源章节（如：第四节 发行人基本情况 / 二、（三）报告期内股本变化）",
  "source_page": "来源位置（文件中的行号或页码范围）",
  "evidence_text": "原文逐字摘录（必须是原文中的原句，不要概括！不要改写！）",
  "notes": "人工备注/概括（如：此为报告期内第一次引入外部PE）",
  "confidence": "high" | "medium" | "low"
}

## 重要规则

1. **evidence_text 必须是原文逐字摘录**，禁止使用"招股书显示"、"根据招股书"等概括性语言。
   直接从文本中复制粘贴原文段落作为 evidence_text。

2. **金额统一换算为万元**。如果原文是"5,000万元"则填 5000；如果是"1.5亿元"则填 15000。

3. **投资人信息尽量完整**。如果原文只提到了投资人名称，至少填写 investor_original_name 和 investor_short_name。

4. **置信度判断**：
   - high: 所有关键字段（金额、投资人、日期）均来自原文
   - medium: 部分字段需要推断
   - low: 大部分字段无法从原文获取

5. **只输出 JSON 数组，不要任何其他文字**。不要用 markdown 代码块包裹。

## 待提取文本

{text}

## 输出

现在请输出 JSON 数组：
"""

# ============================================================
# 调用示例（使用 OpenAI/Anthropic API）
# ============================================================

def extract_with_openai(text: str, api_key: str, model: str = "gpt-4o") -> list:
    """
    使用 OpenAI API 提取融资事件
    pip install openai
    """
    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你是一个专业的金融数据提取助手。只输出JSON，不要markdown代码块。"},
            {"role": "user", "content": EXTRACTION_PROMPT.format(text=text[:50000])}
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )
    return json.loads(response.choices[0].message.content)


def extract_with_anthropic(text: str, api_key: str, model: str = "claude-sonnet-4-6") -> list:
    """
    使用 Anthropic API 提取融资事件
    pip install anthropic
    """
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system="你是一个专业的金融数据提取助手。只输出JSON，不要markdown代码块。",
        messages=[{
            "role": "user",
            "content": EXTRACTION_PROMPT.format(text=text[:50000])
        }],
    )
    # 提取 JSON 内容
    content = response.content[0].text
    # 去除可能的 markdown 代码块包裹
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content[:-3]
    return json.loads(content)


# ============================================================
# 命令行入口
# ============================================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 extract_financing_events.py <候选文本文件路径>")
        print("      将候选文本文件的内容注入 prompt 并输出完整 prompt（可用于复制到 LLM 界面）")
        print()
        print("      设置 OPENAI_API_KEY 或 ANTHROPIC_API_KEY 环境变量可直接调用 API")
        sys.exit(1)

    text_path = Path(sys.argv[1])
    if not text_path.exists():
        print(f"错误: 文件不存在: {text_path}")
        sys.exit(1)

    text = text_path.read_text(encoding="utf-8")

    # 检查是否有 API key
    import os
    openai_key = os.environ.get("OPENAI_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

    if openai_key:
        print("使用 OpenAI API 提取...")
        result = extract_with_openai(text, openai_key)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif anthropic_key:
        print("使用 Anthropic API 提取...")
        result = extract_with_anthropic(text, anthropic_key)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # 没有 API key，输出完整 prompt 供手动使用
        print("# === 将以下 Prompt 复制到 LLM 界面使用 ===")
        print()
        print(EXTRACTION_PROMPT.format(text=text[:30000]))
        print()
        print("# === Prompt 结束 ===")
