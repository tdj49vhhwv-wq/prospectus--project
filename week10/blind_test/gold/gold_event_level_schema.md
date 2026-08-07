# 事件级 Gold 字段规范（融资历史事件流）

**适用**：688795 摩尔线程、688802 沐曦股份盲测 Gold v1.0
**口径**：一条记录 = 一个融资/股权事件；不展开投资人明细

## 1. 字段定义

| 字段 | 必填 | 格式 / 枚举 | 说明 |
|------|:--:|------|------|
| `blind_gold_id` | 是 | `BT-{stock_code}-{seq:03d}` | 盲测 Gold 唯一 ID |
| `stock_code` | 是 | `688795` / `688802` | 公司代码 |
| `company_name` | 是 | 文本 | 与 manifest 一致 |
| `event_date` | 是 | `YYYY-MM-DD` 或 `YYYY-MM` 或 `YYYY` | 事件日期，粒度由 `date_type` 说明 |
| `date_type` | 是 | `day` / `month` / `year` / `inferred` | 原文粒度；推算日期必须填 `inferred` 并在 notes 说明 |
| `event_type_code` | 是 | E / A:A1-A:A6 / B / C / D:D1-D:D6 / F / G / H:H1-H9 / I / J | 复用 `week6/pipeline/event_category_definitions.json` |
| `event_context` | 是 | 文本 | 中文事件类型（增资、整体变更、股权转让等） |
| `round_label` | 是 | 文本或 `未披露` | 优先原文口径（如“第一次增资”“A轮”）；原文未披露填 `未披露`，不得引用市场传闻 |
| `total_amount_wan` | 否 | 数值或空 | 事件总额，单位万元；未披露则空 |
| `amount_disclosed` | 是 | `true` / `false` | 金额是否由招股书披露 |
| `amount_currency` | 否 | `人民币` / `美元` / `港元` | 原披露币种；不做汇率换算 |
| `valuation_wan` | 否 | 数值或空 | 该轮估值，单位万元；未披露则空 |
| `valuation_basis` | 是 | `投前` / `投后` / `未披露` | 估值口径必须写明 |
| `valuation_currency` | 否 | `人民币` / `美元` / `港元` | 估值币种 |
| `source_file` | 是 | 文件名 | `week1/review/` 下对应 Markdown |
| `source_page` | 是 | `第N页` 或 `行区间` | 能回原文定位 |
| `evidence_text` | 是 | 原文逐字摘录 ≤ 500 字 | 不得概括、不得改写 |
| `annotator` | 是 | 姓名/标识 | 标注人 |
| `annotation_status` | 是 | `draft` / `reviewed` / `frozen` | 状态机 |
| `notes` | 否 | 文本 | 歧义、复合拆分、重复披露说明 |

## 2. 标注规则

1. **事件粒度**：同一公司同一天同一类型，只记一条事件记录，不展开投资人明细；金额填事件总额。
2. **复合事件**：招股书将“增资 + 股权转让”作为一次披露时，Gold 记一条 `C`；若原文分段披露且金额、对象可独立核对，则拆为两条并各自附证据。
3. **日期取值**：优先工商变更/核准日期；只有协议日时取协议日并在 notes 说明；股东会决议日、验资日不混用。
4. **金额**：只填招股书明确披露的金额；`总金额未披露但单投资人金额披露` 时，`amount_disclosed=false`，notes 记录可获得的投资人金额明细。资本公积转增为非外部融资，金额可留空。
5. **估值**：必须区分投前/投后；未披露填 `未披露`，不允许用金额推算估值。
6. **员工平台**：员工持股平台增资记为 `J`，`event_context=员工激励`。
7. **去重**：同一事件在多个章节重复披露时只记一条，notes 列明重复位置。
8. **独立性**：标注期间不得查看 Auto 候选或规则输出；已有 week1 抽取结果不得作为依据。

## 3. 示例

```csv
blind_gold_id,stock_code,company_name,event_date,date_type,event_type_code,event_context,round_label,total_amount_wan,amount_disclosed,amount_currency,valuation_wan,valuation_basis,valuation_currency,source_file,source_page,evidence_text,annotator,annotation_status,notes
BT-688795-001,688795,摩尔线程,2022-12,month,A:A4,增资,A轮,未披露,false,人民币,未披露,未披露,人民币,688795_摩尔线程_招股书_正式稿_20251128.md,第N页,"原文逐字摘录",待填,draft,
```

标注模板见 `gold_event_level_template.csv`。
