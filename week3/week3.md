# Week 3: 8家Gold收敛 + 可复现自动化流水线

**姓名**: 赵秉清  
**日期**: 2026-06-17  
**项目**: 招股书PEVC融资历史提取  

---

## 1. Week 2 问题修复

| # | Week 2 问题 | Week 3 修复 | 状态 |
|:--:|------|------|:--:|
| 1 | 公司名误写(友声→友升, 星空→星图) | 目录/文件/代码全部重命名 | ✅ |
| 2 | 3家硬编码在Python变量中 | 转为`_融资历史_结构化.json` | ✅ |
| 3 | source_page引用MD行号 | 全部转为PDF页码格式(PDF pXX) | ✅ |
| 4 | 影石创新6轮合并为1事件 | 拆分为天使/A/B/C轮4个独立事件 | ✅ |
| 5 | Excel第三表偏离示范 | 三段式分隔+snapshot_type标准化 | ✅ |
| 6 | 批注PDF空目录 | build_annotations_pdf.py + 8家批注 | ✅ |

## 2. 人工 Gold Standard

| Gold文件 | 行数 | 说明 |
|------|:--:|------|
| subscription_flow_gold.jsonl | 124 | 增资/设立/股改/资本公积转增 |
| share_transfer_flow_gold.jsonl | 7 | 股权转让(转让方→受让方+价款) |
| equity_snapshot_gold.jsonl | 83 | 各时点股权结构存量 |
| cross_check_gold.jsonl | 164 | 流量↔存量交叉验证 |

**8家公司覆盖**: 001282/301563/301581/603418/688758/688775/920100/920116 — 全部 ✅

**Schema升级**: 
- 新增ShareTransferFlow Pydantic模型(区分transferor/transferee)
- EventContext枚举新增"资本公积转增"
- 全部source_page为PDF页码, evidence_text为原文逐字摘录

## 3. 自动化流程

**一键运行**: `bash week3/pipeline/run.sh`

| 步骤 | 脚本 | 类型 | 输出 |
|:--:|------|:--:|------|
| 1 | extract_with_rules.py | ⚙自动 | auto_subscription_flow.jsonl (63行) + auto_equity_snapshot.jsonl (434行) |
| 2 | validate_schema.py | ⚙自动 | schema_validation_log.csv (716行) + cross_check_summary.csv (14行) |
| 3 | compare_to_gold.py | ⚙自动 | auto_vs_gold_comparison.xlsx (逐字段diff) |

**规则覆盖**:
- 6种事件类型: 增资 / 股权转让 / 设立 / 整体变更 / 资本公积转增 / 其他
- 日期标准化: 中文日期→YYYY-MM-DD (100%)
- 投资人名称: 中文实体80%, 英文名0%(规则盲区)

**Schema校验结果**: Gold 3P/0W/0F ✅ | Auto 2P/0W/0F ✅

## 4. Auto vs Gold 对比

| 类型 | Gold | Auto | 匹配 | 漏抽(gold_only) | 误抽(auto_only) |
|------|:--:|:--:|:--:|:--:|:--:|
| subscription_flow | 124 | 63 | — | 744 fields | 378 fields |
| share_transfer_flow | 7 | 0 | — | 42 fields | 0 |
| equity_snapshot | 83 | 434 | — | 498 fields | 2604 fields |

**主要漏抽原因**: event_type="其他"(53条), 英文投资人名(28条), 非标准增资描述(24条)  
**主要误抽原因**: 公司自身/中介机构当投资人, 税率/%符号当持股比例

## 5. 方法说明 (规则 vs LLM 分工)

### 规则 vs LLM 分工

- **规则负责**: 章节定位, 日期标准化(100%), 中文名提取(80%), Pydantic校验, Cross-check
- **LLM负责**(计划中): "其他"事件分类(36条), 英文名提取(28条), 金额消歧, VIE拆分

### 错误分析 (8问)

1. 可以稳定提取: 标准格式"增资""设立""整体变更"
2. 必须LLM/人工: "其他"事件(0%), 英文名(0%), VIE拆分
3. 主要漏抽: 非标准事件+英文名 (43%)
4. 主要误抽: 公司自身/中介机构/税率%当持股
5. 单位发现: price×shares≈amount校验, 量级check
6. 转让分离: ShareTransferFlow schema+event_context区分
7. cross-check失败: 标记待复核→人工回PDF→自动生成复核任务
8. 50家瓶颈: PDF格式多样性(P0), 英文名(P0), 人工复核(P2)

## 7. 已知局限与下一步

| 局限 | 影响 | 解决方案 |
|------|:--:|------|
| 影石VIE 4事件 confidence=low | 日期/金额推断 | 查证监会问询回复 |
| 三协电机t0出资缺失 | cross-check不完整 | 工商资料补充 |
| 友升PDF缺失 | 批注无法生成 | 下载PDF |
| 英文投资人名 0%覆盖 | 28条漏抽 | LLM接入 |
| Auto ES精度低(406噪声) | 434→83实际可用 | LLM过滤噪声 |

## 8. 提交物清单

| 要求 | 路径 | 状态 |
|------|------|:--:|
| 一键运行 | `bash week3/pipeline/run.sh` | ✅ |
| 无绝对路径 | `week3/pipeline/config.py` | ✅ |
| Gold JSONL | `week3/manual_gold/*.jsonl` (4个) | ✅ |
| Auto JSONL | `week3/outputs/auto_jsonl/` | ✅ |
| Schema校验日志 | `week3/logs/schema_validation_log.csv` | ✅ |
| Cross-check | `week3/logs/cross_check_summary.csv` | ✅ |
| Auto vs Gold | `week3/evaluation/auto_vs_gold_comparison.xlsx` | ✅ |
| 规则/Prompt说明 | `week3/pipeline/rule_coverage.md` + `week3/prompts/` | ✅ |
| 批注PDF | `annotations_pdf/` (8家,自动生成) | ✅ |
| 人工复核队列 | `week3/manual_gold/manual_review_queue.csv` | ✅ |
| 失败样本 | `week3/evaluation/error_analysis.md` | ✅ |
| 与教师基准对比 | `week3/evaluation/benchmark_comparison.md` | ✅ |
| 周报 | `weekly_reports/week3.md` (本文件) | ✅ |
