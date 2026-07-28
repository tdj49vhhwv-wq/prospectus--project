# LLM 提取 Prompt (可执行)

> 本文件是老师要求的"可执行 prompt"，不是文档中的示例。
> 可直接用 `code/llm_prompts/extract_financing_events.py` 调用 OpenAI/Anthropic API，
> 也可以将下面的 prompt 复制到 LLM 网页界面手动使用。

## System Prompt

你是一个专业的金融数据提取助手。从招股说明书文本中提取融资历史事件，严格遵守输出格式。

## User Prompt 模板

```
请从以下招股说明书文本中，提取所有融资历史事件。

输出一个 JSON 数组。每个事件对象包含:

{
  "record_type": "financing_event",
  "company_name": "公司全称",
  "stock_code": "6位股票代码",
  "event_order": 1,
  "event_date": "YYYY-MM-DD",
  "date_type": "工商变更日|协议签署日|股东大会日|未说明",
  "event_type": "增资|股权转让|增资及股权转让|整体变更|吸收合并|设立|改制|VIE搭建|VIE拆除|其他",
  "disclosed_round": "原始轮次名或'未披露'",
  "inferred_round": "推断轮次",
  "round_inference_basis": "推断依据",
  "total_investment_amount": 数值(万元)或null,
  "currency": "CNY|USD|HKD",
  "share_price": 每股价格或null,
  "pre_money_valuation": 投前估值(万元)或null,
  "post_money_valuation": 投后估值(万元)或null,
  "valuation_basis": "估值依据说明",
  "investors": [
    {
      "investor_original_name": "完整名称",
      "investor_short_name": "简称",
      "investor_type": "PE|VC|产业资本|政府基金|自然人|员工持股平台|其他",
      "is_pevc": "yes|no|uncertain",
      "investment_amount": 金额(万元)或null,
      "shares_acquired": 股份数或null,
      "shareholding_ratio_after_event": "持股比例",
      "exit_status_before_ipo": "未退出|全部退出|部分退出|无法判断"
    }
  ],
  "source_section": "来源章节",
  "source_page": "来源位置",
  "evidence_text": "原文逐字摘录(必须是原文原句!)",
  "notes": "人工备注",
  "confidence": "high|medium|low"
}

规则:
1. evidence_text 必须是原文逐字摘录，禁止"招股书显示"等概括性语言
2. 金额统一换算为万元
3. total_investment_amount 应约等于 investors 各 investment_amount 之和
4. 只输出 JSON 数组，不要任何其他文字，不要 markdown 代码块包裹

待提取文本:
{text}
```

## 调用方式

```bash
# 使用 OpenAI API
export OPENAI_API_KEY="sk-..."
python3 code/llm_prompts/extract_financing_events.py <候选文本.md>

# 使用 Anthropic API
export ANTHROPIC_API_KEY="sk-ant-..."
python3 code/llm_prompts/extract_financing_events.py <候选文本.md>

# 无 API Key 时输出完整 prompt 到 stdout
python3 code/llm_prompts/extract_financing_events.py <候选文本.md>
```
