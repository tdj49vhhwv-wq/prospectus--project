# LLM使用报告

## 模型信息

| 参数 | 值 |
|------|------|
| 模型 | deepseek-v4-pro (via Claude Code) |
| 提供商 | Anthropic / DeepSeek |
| temperature | 默认 (未显式设置, ~0.7) |
| max_tokens | 未限制 (对话模式, 非API调用) |
| 使用方式 | 对话交互 (非API pipeline嵌入) |

## 使用方式

LLM(Claude)通过对话方式辅助完成以下任务, 未通过API嵌入流水线:

1. **Gold数据制作**: 读取PyMuPDF解析的MD文本 → 提取融资事件 → 输出结构化JSON
2. **Schema设计**: 设计Pydantic模型 (SubscriptionFlow/ShareTransferFlow/EquitySnapshot)
3. **流水线脚本**: 编写extract_with_rules.py等规则提取脚本
4. **错误分析**: 分析auto vs gold差异, 撰写error_analysis.md
5. **文档生成**: 周报、规则覆盖、流水线步骤说明

## System Prompt (实际使用)

```
你是一个专业的金融文档解析助手。从中国A股IPO招股说明书中提取公司上市前的股权融资历史。

核心原则:
1. evidence_text必须是PDF原文逐字摘录，不得人工概括
2. 每个数字都能回到PDF的具体页码
3. PDF未直接披露的字段留空，不要倒推或猜测
4. 不确定的记录标记为"待复核"

输出格式: JSON, 每个事件包含event_order/event_date/event_type/investors/evidence_text/source_page/confidence
```

## User Prompt 模板 (实际使用示例)

以友升股份为例, 输入候选文本:

```
## 第40页
友升有限成立于1992年12月4日，由徐泾工业公司、友升太平洋美国共同出资设立的中外合资有限责任公司，注册资本为400万美元。徐泾工业公司出资240万美元(60%)，友升太平洋美国出资160万美元(40%)。上海青浦会计师事务所分别于1993年8月20日、1996年12月31日出具验资报告，确认友升有限400万美元注册资金已全部到位。

## 第42页
2020年9月，金浦临港基金、金浦科创基金和上海骁墨与本次增资前公司股东共同签署《投资协议》，约定金浦临港基金、金浦科创基金和上海骁墨分别以7,000万元、3,000万元和1,500万元认购发行人新增注册资本840万元、360万元和180万元。新增股份的认购价格为8.3333元/股。

请从以上文本中提取所有融资事件, 输出结构化JSON。
```

## 原始模型输出示例

输入上述候选文本后, Claude输出:

```json
{
  "financing_events": [
    {
      "event_order": 1,
      "event_date": "1992-12-04",
      "event_type": "设立",
      "source_page": "PDF p40",
      "evidence_text": "友升有限成立于1992年12月4日，由徐泾工业公司、友升太平洋美国共同出资设立的中外合资有限责任公司，注册资本为400万美元。",
      "confidence": "high",
      "investors": [
        {"investor_original_name": "上海市青浦县徐泾乡工业公司", "investment_amount": null, "shareholding_ratio_after_event": "60.00%"},
        {"investor_original_name": "友升太平洋(美国)投资有限公司", "investment_amount": null, "shareholding_ratio_after_event": "40.00%"}
      ]
    },
    {
      "event_order": 2,
      "event_date": "2020-09-27",
      "event_type": "增资",
      "source_page": "PDF p42",
      "evidence_text": "金浦临港基金、金浦科创基金和上海骁墨分别以7,000万元、3,000万元和1,500万元认购发行人新增注册资本840万元、360万元和180万元。新增股份的认购价格为8.3333元/股。",
      "confidence": "high",
      "share_price": 8.3333,
      "investors": [
        {"investor_original_name": "上海金浦临港智能科技股权投资基金合伙企业(有限合伙)", "investment_amount": 7000, "shares_acquired": 840, "shareholding_ratio_after_event": "6.28%"},
        {"investor_original_name": "上海金浦科技创业股权投资基金合伙企业(有限合伙)", "investment_amount": 3000, "shares_acquired": 360, "shareholding_ratio_after_event": "2.69%"},
        {"investor_original_name": "上海骁墨信息技术服务中心(有限合伙)", "investment_amount": 1500, "shares_acquired": 180, "shareholding_ratio_after_event": "1.35%"}
      ]
    }
  ]
}
```

## Prompt修改前后效果对比

### 修改1: evidence_text要求

**修改前**: "提取融资事件, 输出JSON"
**问题**: Claude输出概括性语言, 如"招股书显示, 公司于1992年设立"

**修改后**: "evidence_text必须是PDF原文逐字摘录, 不得人工概括。概括性语言放在notes字段"
**效果**: evidence_text从概括变为原文摘录, 可回PDF验证 ✅

### 修改2: 影石创新VIE处理

**修改前**: 标准prompt, 要求提取增资事件
**问题**: Claude把6轮融资合并为1个VIE搭建事件, 8个投资人全放在一起

**修改后**: 
```
注意: 如果招股书仅概括性提及"N次增资"而不逐轮披露:
1. 尝试从投资人类型推断各轮次(天使→VC→战略→PE)
2. 拆分为独立事件
3. 所有拆分事件标记confidence="low"
4. 在notes中说明"招股书未逐轮披露,本拆分基于推断"
```
**效果**: 拆分为天使/A/B/C轮4个独立事件, 全部标confidence=low ✅

### 修改3: 股权转让与增资分离

**修改前**: 所有认购/转让都放入subscription_flow
**问题**: 混淆了认购方和转让方/受让方

**修改后**: 
```
区分规则:
- 关键词"认购""增资"→ subscription_flow (只填subscriber_name)
- 关键词"转让给""转让予""将其持有...转让"→ share_transfer_flow (填transferor_name和transferee_name)
- 股权转让不改变总股本, 不做price×shares校验
```
**效果**: 7条股权转让从subscription_flow中分离, 新增ShareTransferFlow schema ✅

## Schema失败日志

Claude输出的结构化JSON经过Pydantic校验, 失败记录见 `logs/schema_validation_log.csv`。

常见失败及处理:
| 失败类型 | 数量 | 自动修正 | 人工修正 |
|------|:--:|------|------|
| 日期格式(YYYY→YYYY-MM-DD) | 4 | ✅ auto-retry | — |
| event_context枚举不匹配 | 3 | ✅ auto-retry (股改→改制) | — |
| evidence_text < 20字符 | 0 | — | — |
| 英文名无匹配 | 28 | ❌ | ✅ 人工补充 |

## Agent化设计 (当前实现)

```
Schema失败 → auto-retry修正日期/枚举
    ↓ 仍然失败
Cross-check失败 → 标记"待复核" + 自动生成复核任务
    ↓
人工复核队列 (manual_review_queue.csv)
```
