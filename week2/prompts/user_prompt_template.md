# User Prompt Template: 招股书融资历史提取

## 输入

招股书PDF解析后的Markdown文本片段（包含页码标记 `## 第N页`）

## 提取要求

请从以下文本中提取公司上市前的所有股权融资事件，输出两类记录：

### 1. subscription_flow (认缴流量)

每行 = 一个认购方在一次增资中的认购记录

必填字段:
- record_type: "subscription_flow"
- company_name: 公司全称
- stock_code: 6位股票代码
- source_page: PDF页码 (如 "PDF p43-45")
- subscription_date: 增资日期 (YYYY-MM-DD 或 YYYY-MM)
- subscriber_name: 认购方全称
- evidence_text: PDF原文逐字摘录（至少20字）

选填字段（PDF未披露则留空）:
- shares_subscribed: 认购数量（万股）
- amount_subscribed: 认购金额（万元）
- price_per_share: 认购价格（元/股）
- event_context: 事件类型枚举
  - 增资 / 股权转让 / 整体变更 / 设立 / 改制 / VIE搭建 / VIE拆除 / 吸收合并 / 其他
- post_event_total_shares: 增资后总股本（万股）
- post_event_total_capital: 增资后总出资额/注册资本（万元）
- subscription_ratio: 认购占比 (如 "6.28%")

### 2. equity_snapshot (股权存量)

每行 = 一个股东在一个时点的持仓

必填字段:
- record_type: "equity_snapshot"
- company_name: 公司全称
- stock_code: 6位股票代码
- source_page: PDF页码
- snapshot_date: 时点 (YYYY-MM-DD 或 YYYY-MM)
- snapshot_type: 股权结构口径 (如 "有限公司设立时" / "A轮增资后" / "股改后" / "IPO前")
- shareholder_name: 股东全称
- evidence_text: PDF原文逐字摘录

选填字段:
- total_shares: 总股本（万股）
- total_capital: 总出资额/注册资本（万元）
- shares_held: 持股数（万股）
- capital_contribution: 出资额（万元）
- shareholding_ratio: 持股比例 (如 "25.00%")
- snapshot_order: 快照序号 (t0=0)
- shareholder_type_detail: 股东类型 (控股股东/实际控制人/员工持股平台/外部PE/外部VC/产业资本/政府基金/自然人/原始创始人)
- is_original_founder: yes/no/unknown

## 重要规则

1. PDF只披露出资额 → 只填出资额, 持股数空着
2. PDF只披露持股数 → 只填持股数, 出资额空着
3. 不要为了填满表格去倒推
4. evidence_text必须是原文, "招股书显示"/"根据招股书"等概括性开头视为不合格
5. notes字段放人工概括和推断

## 输出格式

每行一个JSON对象（JSONL格式），不要数组包裹。
