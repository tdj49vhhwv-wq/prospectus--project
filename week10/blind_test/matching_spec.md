# 盲测匹配口径（预注册）

本文件在 Gold 标注与规则运行前定稿；盲测报告必须按本口径计算，不得事后调整。

## 1. 分析单位

事件级。Gold 事件与 Auto 事件各自聚合为：

```text
事件 key = (stock_code, event_date, event_type_top_level)
```

本次不做投资人明细级匹配。

## 2. Auto → 事件类型映射

`run_md_pipeline.py` 输出 `event_context` 中文类型，映射如下：

| Auto event_context | 事件类型顶层码 |
|------|------|
| 增资 | A |
| 设立 | E |
| 整体变更 | B |
| 增资及股权转让 / 增资+转让 | C |
| 股权转让 | D |
| 资本公积转增 | F |
| 吸收合并 | G |
| 员工持股平台出资 / 员工激励 | J |
| 境外融资 / VIE | H 或 A（按 `event_category_definitions.json`） |

Gold 的 `A:A1`—`A:A6`、`D:D1`—`D:D6` 子类在事件级匹配时只比较顶层码（A/D）；子类差异记录为字段级偏差，不影响 TP。

## 3. 日期匹配

按 Gold 的粒度比较：

| Gold date_type | 匹配条件 |
|------|------|
| `day` | Auto 日期与 Gold 日期同日 |
| `month` | Auto 日期与 Gold 同年同月 |
| `year` | Auto 日期与 Gold 同年 |
| `inferred` | 按 Gold 实际填写的粒度比较（如 `2022-12` 按同年同月） |

## 4. 匹配算法

一对一贪心匹配，确定性执行：

1. 按 `(event_date, blind_gold_id)` 升序排序 Gold；
2. 按 `(subscription_date, event_id)` 升序排序 Auto；
3. 逐条 Gold 取第一个满足“日期粒度匹配 + 顶层类型相同 + 尚未被占用”的 Auto，记为 TP 并占用；
4. 剩余 Gold → FN；剩余 Auto → FP；
5. 禁止一条 Auto 匹配多条 Gold；同一事件的重复 Auto 输出，第二条计入 FP。

## 5. 指标定义

```text
Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
F1        = 2 * Precision * Recall / (Precision + Recall)
```

- 全样本、分公司、分事件类型三层都报告；
- 分母为零时填 `N/A`，不填 100%；
- 分公司结果不允许用全样本掩盖单家掉点。

## 6. 字段级一致率（次要报告，不影响 P/R/F1）

对 TP 事件比较：

| 字段 | 一致判定 |
|------|------|
| `total_amount_wan` | 同币种下数值一致，或偏差 ≤ 0.5% |
| `valuation_wan` | 同币种且 `valuation_basis` 一致，数值一致或偏差 ≤ 0.5% |
| `round_label` | 字符串一致；`未披露` 与空值视为不一致 |
| `event_date` | 按第 3 节粒度一致 |

逐字段报告一致率与缺失率；`amount_disclosed=false` 的 Gold 不参与金额一致率。

## 7. 过拟合判定（预注册）

盲测结果与盲测运行当日已冻结的 Week 8/9 dev 基线比较：

1. 事件级 F1、Precision、Recall 中任一项相对 dev 基线下降 ≥ 10 个百分点，或盲测任一指标 < 80% → 标记“盲测明显下降 / 过拟合嫌疑”；
2. 两家公司分别报告；若一家 P/R ≥ 90% 而另一家任一指标 ≤ 70%，判定“单家崩坏”，不得以两家均值通过；
3. 判定结果写入 Week 10 盲测报告，作为是否进入下一阶段的证据。
