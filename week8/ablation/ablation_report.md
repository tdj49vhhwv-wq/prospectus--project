# 三种提取策略消融报告（Week 9 提前执行）

**2026-08-07**：按 Week 9 任务 5/6 落地消融框架，并完成“仅正则”臂；LLM 相关臂
需要 `DEEPSEEK_API_KEY`，本机未配置，已保留可复跑脚本与状态记录。

## 一、设计

| 臂 | 输入 | 说明 | 状态 |
|---|------|------|------|
| 仅正则 | `week6/auto_output_md/validated/` | 现有 PATTERNS + 分层/去重/过滤 | 已完成 |
| 仅 LLM | candidate 层缺日期/待识别低置信度候选 | `llm_extractor.py`，保存原始响应与费用日志 | 待 key |
| 正则 + LLM | 正则结果 + LLM 补充 | 合并后重跑两层评价 | 待 key |

运行：

```bash
python3 week8/ablation/run_ablation.py --arm regex
export DEEPSEEK_API_KEY=...
python3 week8/ablation/run_ablation.py --arm llm
python3 week8/ablation/run_ablation.py --arm "regex+llm"
```

LLM 臂只处理 candidate 层低置信度候选（缺日期或 `（待识别）`），逐条保存原始响应到
`raw_llm_responses/`，费用写入 `llm_cost_log.csv`，默认不发起任何 LLM 调用。

## 二、仅正则臂结果（validated，`--relax-gold-day-to-month`）

事件级：TP=39 / FP=12 / FN=6，P=76.47%，R=86.67%，F1=81.25%。

投资人明细级：Gold 108 / Auto 294 / 匹配 30，R=27.78%，P=10.20%；
金额准确率 10.53%，股数 0.00%，价格 0.00%；Auto 缺失率：金额 69.73%，股数 85.37%，价格 100%。

指标文件：`metrics_regex.json`。

## 三、字段映射修复（Week 9 任务 4）

`PATTERN_FIELD_ROLES` 为 36 条正则逐组声明 `amount` / `shares` / `price` 角色，
不再按“匹配到的第 N 个数字”猜测字段。同时处理单位换算：

- 定向发行：`发行价格` → price，`发行普通股 X 万股` → shares，`募集资金总额` → amount；
- 认购 XX 万股（X 万元）→ shares + amount；
- 增发股份 / 折股以“股”为单位 → 自动换算为万股（÷10000）；
- 出资、认缴、转让对价 → amount；
- 注册资本由 X 增至 Y、增资至 X 万元、股本总额增至 X 万股等“事件后总规模”不再冒充
  amount/shares（置空，避免字段级错误命中）。

事件级指标不受影响（P/R/F1 不变）；投资人明细级字段完整率口径更诚实：
金额缺失率从旧口径 36.05%（大量为错误填充）调整到 69.73%，股数缺失率从 89.12% 降到 85.37%。

## 四、待办

- 提供 `DEEPSEEK_API_KEY` 后重跑 LLM 两臂，补充原始响应、费用与合并指标；
- 投资人实体规范化与去重（明细级 F1 仍约 14.9%，需要先解决匹配侧）。
