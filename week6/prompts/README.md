# Week 6 — Prompt 实验记录

## LLM 调用配置

| 参数 | 值 |
|------|-----|
| 模型 | DeepSeek V4 Pro (via Claude Code) |
| 调用方式 | Python pipeline 自动化 |
| Prompt 版本 | prompt_v3_全类型_分模块 |
| 温度 | 默认 |
| 最大输出 | 默认 |

## Prompt 文件索引

| 文件 | 用途 |
|------|------|
| `prompt_v3_全类型_分模块.md` | 8家公司通用提取prompt（见根目录 docs/prompts/） |
| `分类体系_最终验证版_含prompt.md` | 事件类型分类体系+prompt模板 |
| `prompt迭代报告_v1到v2.md` | v1→v2迭代记录 |
| `prompt验证汇总_3家公司.md` | 3家公司验证结果 |
| `model_params_and_evaluation.md` | 模型参数与评估标准 |

## 第八周个人反馈中Prompt实验说明

本周暂未提交独立LLM prompt对比实验。当前pipeline以正则+规则为主（确定性提取70%），LLM用于语义消歧（20%），人工兜底（10%）。

如后续需要提交LLM实验，需包含：
- 模型参数（model_name, temperature, max_tokens）
- 原始响应（raw_response.jsonl）
- 逐条评价（evaluation.csv: TP/FP/FN per event）

## 参考

根目录 `docs/prompts/` 下有完整的历史prompt文档。
