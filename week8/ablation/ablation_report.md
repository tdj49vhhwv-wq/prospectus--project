# 三种提取策略消融报告（Week 9 提前执行）

**2026-08-07**：按 Week 9 任务 5/6 落地消融框架并完成三臂实测。LLM 臂由用户提供
`DEEPSEEK_API_KEY` 后实际调用 DeepSeek（`deepseek-chat`），原始响应与调用日志已归档。

## 一、设计

| 臂 | 输入 | 说明 | 状态 |
|---|------|------|------|
| 仅正则 | `week6/auto_output_md/validated/` | 现有 PATTERNS + 分层/去重/过滤 | 已完成 |
| 仅 LLM | candidate 层缺日期/待识别低置信度候选 | `llm_extractor.py`，保存原始响应与费用日志 | 已完成（31 次调用） |
| 正则 + LLM | 正则结果 + LLM 补充 | 合并后重跑两层评价 | 已完成 |

运行：

```bash
python3 week8/ablation/run_ablation.py --arm regex
export DEEPSEEK_API_KEY=...
python3 week8/ablation/run_ablation.py --arm llm
python3 week8/ablation/run_ablation.py --arm "regex+llm"
```

LLM 臂只处理 candidate 层低置信度候选（缺日期或 `（待识别）`），逐条保存原始响应到
`raw_llm_responses/`，调用记录写入 `llm_cost_log.csv`，默认不发起任何 LLM 调用。

## 二、仅正则臂结果（validated，`--relax-gold-day-to-month`）

事件级：TP=39 / FP=12 / FN=6，P=76.47%，R=86.67%，F1=81.25%。

投资人明细级：Gold 108 / Auto 294 / 匹配 30，R=27.78%，P=10.20%；
金额准确率 10.53%，股数 0.00%，价格 7.69%；Auto 缺失率：金额 69.73%，股数 85.37%，价格 94.56%。

指标文件：`metrics_regex.json`。

## 二.5、仅 LLM 臂实测结果

- 调用次数：31 次（8 家开发集 × 低置信度候选，限 5 条/家）；
- 归一化输出：81 条记录，其中带日期 17 条；
- 质量观察：LLM 能正确拆出逐投资人金额（如 001282 2014-05 孙国奉 1,995 万元、
  张松满 1,005 万元），但多数低置信度证据片段不含日期，输出仍缺日期；
- 原始响应：`raw_llm_responses/`；调用日志：`llm_cost_log.csv`（当前只记调用次数，
  DeepSeek 响应中的 usage 未解析，精确 token/费用待补）。

指标文件：`metrics_llm.json`、`llm_output.jsonl`。

## 二.6、正则 + LLM 实测结果

将 17 条带日期 LLM 记录合并进 validated 层后重跑两层评价：

- 朴素合并：事件级 TP=39 / FP=13 / FN=6，P=75.00%，R=86.67%，F1=80.41%；
  LLM 把 603418 2020-09-30 工商变更日重复事件当成新增资，增加 1 条 FP；
- 增加“同月同类去重”后：事件级 TP=39 / FP=11 / FN=6，P=78.00%，R=86.67%，F1=82.11%，
  与仅正则一致；投资人明细级不变（R=27.78% / P=10.20%）。

结论：当前低置信度候选上，LLM 补充没有带来事件级增益；真正的增益点在于
“带日期的原文片段”与实体规范化，而不是把工商变更日重复行并入 validated。

指标文件：`metrics_regex_plus_llm.json`。

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
金额缺失率从旧口径 36.05%（大量为错误填充）调整到 69.73%，股数缺失率从 89.12% 降到 85.37%；
第九批加入价格回填后，价格缺失率从 100% 降到 94.56%。

## 四、待办

- 解析 DeepSeek usage 字段，补齐 token 数与费用；
- 把 LLM 输入改为“含日期的事件段落”，让仅 LLM 臂能直接产出日期；
- 投资人实体规范化与去重（明细级 F1 仍约 14.9%，需要先解决匹配侧）。
