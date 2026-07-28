# 数据字典 — zbq 系列表字段说明

> 学习李泽润: 完整的数据字典方便组员检查和后续扩展

## zbq_companies（公司清单）

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| company_id | TEXT PK | 股票代码 | 920100 |
| company_name | TEXT | 公司简称 | 三协电机 |
| stock_code | VARCHAR(10) | 股票代码 | 920100 |
| ipo_board | VARCHAR(20) | 上市板块 | 北交所/科创板/创业板/深主板/沪主板 |
| pdf_prospectus_date | VARCHAR(8) | 招股书签署日 | 20250711 |
| event_count | INTEGER | 融资事件总数 | 6 |
| snapshot_count | INTEGER | 股权快照数 | 10 |
| subscription_count | INTEGER | 认缴记录数 | 15 |
| transfer_count | INTEGER | 转让记录数 | 2 |
| pe_fund_count | INTEGER | PE基金数 | 2 |
| build_status | VARCHAR(20) | 构建状态 | built/pending |

## zbq_equity_snapshot（股权快照）

| 字段 | 类型 | 说明 |
|------|------|------|
| event_id | VARCHAR(50) | 统一事件ID |
| company_name | VARCHAR(200) | 公司名称 |
| stock_code | VARCHAR(10) | 股票代码 |
| snapshot_label | VARCHAR(50) | 快照标签(t0/s1/s2...) |
| snapshot_date | VARCHAR(20) | 快照日期 |
| trigger_event | TEXT | 触发事件描述 |
| trigger_event_order | INTEGER | 事件序号 |
| total_shares_wan | DOUBLE PRECISION | 总股本(万股) |
| registered_capital_wan | DOUBLE PRECISION | 注册资本(万元) |
| shareholder_name | VARCHAR(200) | 股东名称 |
| shares_wan | DOUBLE PRECISION | 持股数(万股) |
| shares_raw | VARCHAR(100) | 原始股数文本 |
| shareholding_pct | DOUBLE PRECISION | 持股比例(%) |
| capital_wan | DOUBLE PRECISION | 出资额(万元) |
| shareholder_type | VARCHAR(50) | PE/VC/政府基金/产业资本/自然人/外资基金/其他 |
| shareholder_category | VARCHAR(50) | 控股股东/创始团队/外部投资 |
| pdf_page | INTEGER | PDF页码 |
| evidence_text | TEXT | 原文逐字摘录 |
| extraction_notes | TEXT | 提取备注 |
| review_status | VARCHAR(20) | pending/extracted/manual_review/verified |
| created_at | TIMESTAMP | 创建时间 |

## zbq_subscription_flow（认缴流量）

| 字段 | 类型 | 说明 |
|------|------|------|
| investor_name | VARCHAR(200) | 投资人名称 |
| investor_type | VARCHAR(50) | 投资人分类 |
| subscription_qty_wan | DOUBLE PRECISION | 认购股数(万股) |
| subscription_amount_wan | DOUBLE PRECISION | 认购金额(万元) |
| subscription_price | DOUBLE PRECISION | 认购价格(元/股) |
| event_type | VARCHAR(50) | 设立/增资/股改/转增/员工激励/VIE融资/IPO |
| registered_capital_before | DOUBLE PRECISION | 增资前注册资本 |
| registered_capital_after | DOUBLE PRECISION | 增资后注册资本 |
| extraction_method | VARCHAR(50) | auto_regex/pdfplumber/supplement_from_final |

## zbq_share_transfer_flow（股权转让）

| 字段 | 类型 | 说明 |
|------|------|------|
| transferor_name | VARCHAR(200) | 转让方 |
| transferee_name | VARCHAR(200) | 受让方 |
| transfer_qty_wan | DOUBLE PRECISION | 转让股数(万股) |
| transfer_amount_wan | DOUBLE PRECISION | 转让金额(万元) |
| transfer_price | DOUBLE PRECISION | 转让价格(元/股) |
| event_type | VARCHAR(50) | 代持还原/同一控制转让/市场价转让/VIE事件 |
| shareholding_before_pct | DOUBLE PRECISION | 转让前持股比例 |
| shareholding_after_pct | DOUBLE PRECISION | 转让后持股比例 |

## zbq_cross_check（交叉验证）

| 字段 | 类型 | 说明 |
|------|------|------|
| check_point | TEXT | 验证点描述 |
| prev_total_capital_wan | DOUBLE PRECISION | 前一注册资本 |
| expected_next_capital | DOUBLE PRECISION | 预期下一注册资本 |
| disclosed_capital | DOUBLE PRECISION | PDF披露注册资本 |
| difference_wan | DOUBLE PRECISION | 差异(万元) |
| diff_pct | DOUBLE PRECISION | 差异百分比 |
| check_result | VARCHAR(30) | pass/mismatch/pending_review |

## 投资人类型枚举

| 代码 | 含义 | 典型关键词 |
|:--:|------|------|
| PE | 私募股权基金 | 创业投资、股权投资、达晨、高瓴、深创投 |
| VC | 风险投资 | 天使投资、种子、孵化 |
| 政府基金 | 政府引导基金 | 国有资本、产业基金、国家集成电路 |
| 产业资本 | 产业投资者 | 产业投资、战略投资 |
| 券商直投 | 券商直接投资 | 证券投资、券商直投 |
| 外资基金 | 境外基金 | EARN ACE、QM101、IDG |
| 自然人 | 个人投资者 | 2-3字中文姓名 |
| 其他 | 其他类型 | 全体股东、员工平台、IPO发行 |
