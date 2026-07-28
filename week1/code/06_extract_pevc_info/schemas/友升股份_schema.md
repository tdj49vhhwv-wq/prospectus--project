# 友声股份 — 字段Schema定义

> 生成时间: 2026-06-05 16:57:22

**公司名称**: 友声股份  

**股票代码**: N/A  

**交易所**: N/A  

**上市板块**: N/A  

**上市日期**: N/A  


**数据格式**: 结构化格式 (含完整字段定义)

---

## 一、公司基本信息字段

| 字段名 | 类型 | 必填 | 说明 | 实际值 |
|--------|------|------|------|--------|
| company_name | string | 是 | 公司全称 | ✓ |
| stock_code | string | 是 | 股票代码 | ✗ 缺失 |
| exchange | string | 是 | 交易所 | ✗ 缺失 |
| board | string | 是 | 上市板块 | ✗ 缺失 |
| listing_date | string | 是 | 上市日期 (YYYY-MM-DD) | ✗ 缺失 |
| prospectus_title | string | 是 | 招股书标题 | ✗ 缺失 |
| prospectus_url | string | 是 | 招股书URL | ✗ 缺失 |
| prospectus_version | string | 是 | 招股书版本 | ✗ 缺失 |
| prospectus_date | string | 是 | 招股书日期 (YYYY-MM-DD) | ✗ 缺失 |

## 二、融资事件字段

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| event_order | integer | 是 | 事件顺序号 |
| event_date | string | 是 | 事件日期 |
| date_type | string | 是 | 日期类型 |
| event_type | string | 是 | 事件类型 |
| disclosed_round | string | 是 | 披露轮次 |
| inferred_round | string | 是 | 推断轮次 |
| round_inference_basis | string | 是 | 轮次推断依据 |
| total_investment_amount | number|null | 否 | 总投资金额(万元) |
| currency | string | 是 | 币种 |
| share_price | number|null | 否 | 每股价格(元) |
| pre_money_valuation | number|null | 否 | 投前估值(万元) |
| post_money_valuation | number|null | 否 | 投后估值(万元) |
| valuation_basis | string|null | 否 | 估值依据 |
| source_section | string | 是 | 来源章节 |
| source_page | string | 是 | 来源页码 |
| evidence_text | string | 是 | 证据文本 |
| confidence | string | 是 | 置信度 |

## 三、投资者字段

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| investor_original_name | string | 是 | 投资者原始名称 |
| investor_short_name | string | 是 | 投资者简称 |
| investor_type | string | 是 | 投资者类型 |
| is_pevc | string | 是 | 是否PE/VC |
| investment_amount | number|null | 否 | 投资金额(万元) |
| shares_acquired | number|null | 否 | 获得股份数 |
| shareholding_ratio_after_event | string|null | 否 | 事件后持股比例 |
| exit_status_before_ipo | string | 是 | IPO前退出状态 |

## 四、处理状态字段

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| download_status | string | 否 |  |
| parse_status | string | 否 |  |
| locate_status | string | 否 |  |
| extract_status | string | 否 |  |
| review_status | string | 否 |  |

## 五、融资事件概览

**事件总数**: 1

- **事件#None** | None | None | 推断轮次: None | 金额: None | 置信度: None