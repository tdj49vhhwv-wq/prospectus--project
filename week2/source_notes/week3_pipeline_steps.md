# Week 3 自动化流水线：步骤说明与人工介入点

## 流水线总览

```
Step 0 [⚠ 人工] PDF下载
  ↓
Step 1 [⚙ 自动] PDF→MD (PyMuPDF,保留页码)
  ↓
Step 2 [⚙ 自动] 目录和章节识别
  ↓
Step 3 [⚙ 自动] 目标章节定位
  ↓
Step 4 [⚙ 自动] 候选事件包生成
  ↓
Step 5 [◐ 半自动] 结构化抽取
  ↓
Step 6 [⚙ 自动] Pydantic Schema校验
  ↓
Step 7 [⚙ 自动] 数值Cross-Check
  ↓
Step 8 [⚙ 自动] Auto vs Gold对比
  ↓
Step 9 [⚠ 人工] 失败样本复核
```

---

## Step 0: PDF下载 [⚠ 人工]

**做什么**: 从巨潮资讯网(cninfo.com.cn)下载8家招股书PDF
**输出**: `data/week1PDF/{公司名}_招股书.pdf`

**人工改了什么**: 搜索关键词、筛选申报稿/上会稿/注册稿/正式稿、排除12类非目标文件
**为什么规则失败**: 巨潮API需要cookie认证,URL参数因公司而异
**可否自动化**: 可以,需维护cookie + URL查询逻辑。已有`code/02_fetch_prospectus_urls/`做了一半

---

## Step 1: PDF→MD [⚙ 自动]

**脚本**: `scripts/parse_pdf.py`
**方法**: PyMuPDF(fitz)逐页提取文本,每页标注`## 第N页`
**输出**: `review/{公司名}_招股书_{日期}.md`
**保留页码**: ✅ 每页开头有`## 第N页`标记
**已知局限**: MinerU输出无页码标记(友升股份用MinerU,页码从已有JSON提取)

---

## Step 2: 目录和章节识别 [⚙ 自动]

**脚本**: `scripts/locate_sections.py`
**方法**: 关键词匹配`发行人基本情况`/`历史沿革`/`股本演变`等章节标题
**输出**: 控制台输出各公司匹配到的章节和PDF页码
**覆盖**: 8/8家公司均能找到至少1个相关章节

---

## Step 3: 目标章节定位 [⚙ 自动]

**目标章节**: 历史沿革、股本形成及变化、历次增资、历次股权转让、新增股东
**方法**: 按优先级定位:
  1. `第五节 发行人基本情况` → `（三）股本演变`
  2. 降级: 关键词全文搜索(`增资`/`股权转让`/`出资方式`)
  3. 兜底: `VIE搭建`/`VIE拆除`(红筹公司)
**脚本**: `scripts/locate_sections.py`
**失败案例**: 影石创新VIE架构 → 融资在"搭建"和"拆除"段落,不在统一章节 → 使用fulltext_scan策略

---

## Step 4: 候选事件包生成 [⚙ 自动]

**切块方法**: 按`## 第N页`边界切分,每个页面作为一个候选事件包
**不是全页乱截**: 只在含关键词的段落展开上下文窗口(±300字)
**脚本**: `scripts/extract_candidates.py`
**输出**: 候选文本片段(控制台)

---

## Step 5: 结构化抽取 [◐ 半自动]

**这一步有人工介入**

### 5a [⚙ 自动] 规则提取
**脚本**: `scripts/extract_with_rules.py`
**方法**: 6种正则规则(增资/股权转让/设立/整体变更/资本公积转增)
**输出**: `outputs/jsonl/auto_subscription_flow.jsonl` (63条) + `auto_equity_snapshot.jsonl` (434条)

### 5b [LLM辅助+人工确认] Gold标准制作
**实际方法**: Claude(LLM)读取PyMuPDF解析的MD文本, 逐项提取融资事件, 人工确认关键字段:
**LLM做了什么**: 从MD文本中定位增资/转让/股改事件, 提取日期/金额/投资人/evidence_text, 输出结构化JSON
**人工确认了什么**: PDF页码准确性、金额单位、事件类型分类(特别是影石VIE拆分和赛分收购事件)
  1. 找到evidence_text原文 → 抄入`evidence_text`字段
  2. 提取金额/数量/价格 → 标注单位(万元/万股/元/股)
  3. 标注PDF页码 → `source_page`字段
  4. PDF未直接披露的字段 → 标注`data_source: "calculated"`或`"inferred"`
  5. 不确定的记录 → 放入`manual_review_queue.csv`

**人工改了什么**: 
- 影石创新VIE事件: 招股书只说"六次增资扩股"不逐轮披露 → 人工拆为4个独立事件,全部标`data_source: "inferred"`, `confidence: "low"`
- 赛分科技2011-10事件: 原文是"赛分有限收购美国赛分" → 归为M&A,不放入股权转让
- 英文投资人名(CASREV/EARN ACE): 正则抓不到 → 人工补充

**为什么规则失败**:
- "六次增资"是概括性表述,无逐轮日期/金额 → 需要语义理解
- 英文名不匹配中文regex → 需要实体识别
- "收购"vs"转让" → 需要法律语境判断

**可否自动化**: 
- VIE拆分 → 目前不能,招股书本身不披露,需外部数据(证监会问询回复)
- 英文名 → LLM可以处理
- 事件类型分类 → LLM可以处理"其他"类

---

## Step 6: Pydantic Schema校验 [⚙ 自动]

**脚本**: `scripts/validate_schema.py`
**方法**: Pydantic v2校验:
  - 字段类型: str/int/float/Enum
  - 必填项: source_page/日期/名称/evidence_text
  - 枚举值: EventContext(增资/转让/设立/股改/资本公积转增...)
  - 格式: stock_code 6位数字, 日期 YYYY-MM-DD
**结果**: Gold 3P/0W/0F, Auto 2P/0W/0F
**输出**: `logs/schema_validation_log.csv` (741行)

---

## Step 7: 数值Cross-Check [⚙ 自动]

**脚本**: `scripts/validate_schema.py` (同一脚本)
**检查类型**:
  1. 公司记录完整性核对 (8行)
  2. 同一时点总股本核对 (14行)
  3. 认缴流量数值核对: price×shares≈amount (14行)
  4. 持股比例合计≈100% (12行)
**失败处理**: 
  - 标记`status: "待复核"`
  - 自动生成复核任务追加到`manual_review_queue.csv`
  - 不修改数据、不删除行
**输出**: `logs/cross_check_summary.csv` (36行, 9项待复核)

---

## Step 8: Auto vs Gold对比 [⚙ 自动]

**脚本**: `scripts/compare_to_gold.py`
**方法**: 按(日期, 名称)对齐auto和gold记录 → 逐字段diff
**标记类型**: match / mismatch / auto_missing / gold_missing(漏抽) / auto_only(误抽)
**输出**: `reports/auto_vs_gold_comparison.xlsx` (3个sheet: SF对比/ES对比/统计)

**主要发现**:
- subscription_flow: Gold 124条, Auto 63条, 漏抽49%
- 漏抽原因: "其他"事件(43%), 英文名(23%), 非标准描述(19%)
- 误抽: 公司自身/中介机构被当投资人(22条), 税率%被当持股比例

---

## Step 9: 失败样本复核 [⚠ 人工]

**人工队列**: `manual_gold/manual_review_queue.csv` (11条, P0/P1/P2优先级)
**人工做什么**:
  1. 打开`reports/auto_vs_gold_comparison.xlsx`,查看mismatch/gold_only行
  2. 回到PDF原文验证
  3. 判断: Gold缺失(需补充) 还是 Auto误提(规则需改进) 还是 PDF自身数据矛盾
  4. 更新status为`resolved`或`confirmed_issue`

---

## 一键运行

```bash
bash scripts/run_week3.sh
```

自动运行 Step 5a + Step 6 + Step 7 + Step 8. Step 0/5b/9 需人工.
