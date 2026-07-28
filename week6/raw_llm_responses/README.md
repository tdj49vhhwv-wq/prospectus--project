# raw_llm_responses/ — LLM原始响应存档

> 老师要求：使用LLM时需提交调用代码、Prompt、模型参数和raw response（不要提交密钥）。

## 当前策略

本周pipeline以代码正则+规则为主（确定性提取70%），LLM用于语义消歧（20%），人工兜底（10%）。未进行大规模LLM批量调用，因此本目录暂无逐公司的raw_response.jsonl。

## LLM使用场景

| 场景 | 调用方式 | Prompt | 状态 |
|------|----------|--------|:--:|
| 投资人类型分类 | classify_investor_type() | 规则关键词 | ✅ 已替代LLM |
| VIE事件检测 | detect_vie_events() | 正则锚点+上下文过滤 | ✅ 已替代LLM |
| 英文投资人识别 | classify_english_investor() | 正则模式 | ✅ 已替代LLM |
| 事件类型判定 | event_type_mapping.md | 编码映射表 | ✅ 已替代LLM |

## 如需启用LLM模式

参考 `prompts/` 目录下的prompt模板和模型参数说明。调用时需保留：

1. **模型参数**: model_name, temperature, max_tokens, top_p
2. **输入**: 原文段落（evidence_text）
3. **输出**: raw_response.jsonl（逐条完整响应）
4. **评价**: evaluation.csv（TP/FP/FN per event）

## 对标ymx

ymx的raw_llm_responses/目录按公司代码（001282/301563/...）存放了逐公司的LLM响应文件。如后续启用LLM模式，应参照此结构。
