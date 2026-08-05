# Week 8 阶段成果：严格评价闭环与第一轮修复

**赵秉清｜2026.08.05**

## 一、已经形成的闭环

本周已建立从现有8家公司Markdown候选到Gold评价报告的确定性流程：

```text
Markdown文本 → 规则候选 → 字段标准化 → 事件级一对一匹配
                                    → 投资人级一对一匹配
                                    → P/R/F1、FP/FN和字段完整率
```

运行命令：

```bash
python3 week8/gold/build_gold_v1_1.py
python3 week8/gold/audit_gold_sources.py
python3 week8/run_week8_evaluation.py --output-dir week8/results/baseline_after_date_fix
```

该流程默认不连接数据库、不调用LLM；同一输入的输出已经通过逐字节一致性测试。

## 二、严格基线与修复结果

| 阶段 | 层级 | TP | FP | FN | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|---:|---:|
| 修复前 | 事件 | 5 | 91 | 33 | 5.21% | 13.16% | 7.46% |
| 修复后 | 事件 | 6 | 70 | 32 | 7.89% | 15.79% | 10.53% |
| 修复前 | 投资人 | 0 | 645 | 124 | 0 | 0 | 0 |
| 修复后 | 投资人 | 2 | 120 | 122 | 1.64% | 1.61% | 1.63% |
| Gold裁决后 | 事件 | 5 | 71 | 28 | 6.58% | 15.15% | 9.17% |
| Gold裁决后 | 投资人 | 2 | 120 | 97 | 1.64% | 2.02% | 1.81% |

本轮没有追求漂亮数字，而是修复两类有明确证据的问题：

1. 禁止从整段上下文任意抓取“公司召开”“关于”等伪投资人，只从语义捕获组提取；
2. 当投资人语句本身没有日期时，只继承该语句之前500字内最近的明确日期，不读取未来日期。

修复后原始候选由645条降为122条，日期标准化率由66.82%升至91.80%；事件级F1由7.46%升至10.53%。投资人级首次出现2个严格TP，即三协电机的稳正景明与长泽创投。

## 三、Gold质量审计

Gold v1.1 保留既有124条人工记录并增加稳定ID和复核状态，但进一步来源审计发现：

| 可追溯状态 | 数量 | 含义 |
|---|---:|---|
| exact_evidence | 3 | Gold证据可在当前Markdown逐字找到 |
| name_year_near | 81 | 投资人和年份邻近出现，但Gold证据是概括文字，需重新对齐原文 |
| name_only | 15 | 名称存在，但相应年份未在附近找到 |
| name_absent | 25 | 当前Markdown中找不到投资人名称，必须裁决或补充数据源 |

经人工裁决，25条 `name_absent` 记录不删除，单独进入 `gold_disputes_v1.1.jsonl`，并暂时排除出主评价集。当前主评价分母为99条；裁决后的完整结果保存在 `results/baseline_after_gold_adjudication/`。其余99条仍有逐字证据对齐工作，因此现有P/R/F1仍是暂定基线，不能作为最终论文准确率。

## 四、当前质量结论

- 评价程序：已经具备一对一约束、分母为零处理、证据追溯和重复运行一致性，可以继续使用；
- 抽取结果：仍未达到研究数据质量，不能进入回归分析或数据库Final层；
- Gold：记录结构完整，但来源证据大多不是当前文本的逐字摘录，需要优先修复；
- 下一轮修复：限制“设立”只识别发行人自身、按历史沿革段落解析同轮多投资人，并对Gold的25条阻塞争议逐条裁决。

## 五、交付物

- `gold/subscription_flow_gold_v1.1.jsonl`：冻结Gold；
- `gold/gold_source_audit.csv`：124条来源审计；
- `gold/gold_disputes_v1.1.jsonl`：25条暂时排除的争议记录；
- `gold/subscription_flow_gold_v1.1_evaluable.jsonl`：99条当前主评价集快照；
- `evaluation/`：标准化、事件评价和投资人评价程序；
- `results/baseline_before_fix/`：修复前完整结果；
- `results/baseline_after_date_fix/`：当前修复后结果；
- `results/baseline_after_gold_adjudication/`：按99条主评价集重跑的结果；
- `results/before_after_metrics.csv`：三阶段指标对比；
- `tests/`：Gold、标准化、匹配器、提取修复和端到端测试。
