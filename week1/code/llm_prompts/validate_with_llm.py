#!/usr/bin/env python3
"""
可执行 LLM Prompt: 校验融资事件 JSON 的完整性和正确性

用法:
  python3 validate_with_llm.py <融资历史JSON文件路径>

说明:
  用 LLM 检查 JSON 中的 evidence_text 是否真的是原文片段，
  以及字段之间是否存在逻辑矛盾。
"""

import sys
import json
from pathlib import Path

VALIDATION_PROMPT = """你是一个金融数据质量审核专家。请审查以下融资历史 JSON，检查数据质量和一致性。

## 检查项

1. **evidence_text 可回源性**: 检查每条 evidence_text 是否是原文逐字摘录。
   - 如果出现"招股书显示"、"根据招股书"、"招股书披露"等概括性开头 → 标记为 issue
   - 如果 evidence_text 过短（< 30字）→ 标记为 issue
   - 如果 evidence_text 看起来像人工总结而非原文 → 标记为 issue

2. **字段一致性**:
   - 检查 total_investment_amount 与 investors 中各 investor 的 investment_amount 之和是否匹配（允许四舍五入误差）
   - 检查 share_price × shares_acquired 是否约等于 investment_amount
   - 检查事件日期是否按 event_order 升序排列
   - 检查 valuation_basis 中的估值是否与 pre_money_valuation/post_money_valuation 一致

3. **投资人信息完整性**:
   - 如果 is_pevc = "uncertain" → 标记为 issue（建议核查）
   - 如果 investment_amount 为 null 但其他投资人有金额 → 标记为 issue

4. **轮次推断合理性**:
   - 检查 inferred_round 的推断是否符合 round_inference_basis 中的描述

## 输出格式

输出一个 JSON 对象：
{
  "overall_quality": "good" | "needs_review" | "poor",
  "issues": [
    {
      "event_order": 事件编号,
      "severity": "error" | "warning" | "info",
      "field": "问题字段",
      "description": "问题描述",
      "suggestion": "修复建议"
    }
  ],
  "summary": "总体评价（一句话）"
}

只输出 JSON 对象，不要任何其他文字。

## 待审查 JSON

{json_data}

## 输出
"""


def validate_with_anthropic(json_data: dict, api_key: str, model: str = "claude-sonnet-4-6") -> dict:
    """使用 Anthropic API 校验 JSON"""
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system="你是一个金融数据质量审核专家。只输出JSON，不要markdown代码块。",
        messages=[{
            "role": "user",
            "content": VALIDATION_PROMPT.format(
                json_data=json.dumps(json_data, ensure_ascii=False, indent=2)[:40000]
            )
        }],
    )
    content = response.content[0].text.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content[:-3]
    return json.loads(content)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 validate_with_llm.py <融资历史JSON文件路径>")
        print("      设置 ANTHROPIC_API_KEY 环境变量可直接调用 API")
        print("      否则输出完整 prompt 供手动使用")
        sys.exit(1)

    json_path = Path(sys.argv[1])
    if not json_path.exists():
        print(f"错误: 文件不存在: {json_path}")
        sys.exit(1)

    data = json.loads(json_path.read_text(encoding="utf-8"))

    import os
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if api_key:
        print("使用 Anthropic API 校验...")
        result = validate_with_anthropic(data, api_key)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("# === 将以下 Prompt 复制到 LLM 界面使用 ===")
        print()
        print(VALIDATION_PROMPT.format(
            json_data=json.dumps(data, ensure_ascii=False, indent=2)[:30000]
        ))
        print()
        print("# === Prompt 结束 ===")
