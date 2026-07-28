# Week 1：公共样本最小闭环报告

**姓名**：赵秉清
**日期**：2026-06-03 至 2026-06-05
**项目**：招股书PEVC融资历史提取

---

## 1. 本周目标

- **目标**：处理8个公共样本，跑通至少1家公司从PDF到JSON的完整闭环。
- **实际完成**：
  - ✅ 8个公共样本全部完成 PDF → Markdown 解析
  - ✅ 8家公司完成章节定位和候选文本截取
  - ✅ 5家公司完成结构化JSON输出（按老师要求Schema）
  - ✅ 建立完整代码管线（爬虫→解析→定位→抽取→校验）
  - ✅ 所有输出保存到各公司独立文件夹

---

## 2. 公共样本处理情况

| sample_id | 公司 | 下载 | 解析 | 章节定位 | 候选文本 | JSON输出 | 人工复核 | 问题 |
|-----------|------|:--:|:--:|:--:|:--:|:--:|:--:|------|
| GEM001 | 黄山谷捷 | ✅ | ✅ | ✅ | ✅ | ✅ (6事件) | unchecked | 无 |
| GEM002 | 云汉芯城 | ✅ | ✅ | ✅ | ✅ | ✅ (8事件) | unchecked | 事件4/6/7/8缺少inferred_round，已修复 |
| STAR001 | 赛分科技 | ✅ | ✅ | ✅ | ✅ | ✅ (3事件) | unchecked | 融资历史章节解析不完整，confidence=low，需回原始PDF补充 |
| STAR002 | 影石创新 | ✅ | ✅ | ✅ | ✅ | ✅ (4事件) | unchecked | 有限公司阶段6次增资未逐轮披露，合并为1个事件 |
| MB001 | 三联锻造 | ✅ | ✅ | ✅ | ✅ | ✅ (5事件) | unchecked | flowchart只显示概览，部分早期增资详情需回PDF确认 |
| MB002 | 友升股份 | ✅ | ✅ | ✅ | ✅ | 仅候选文本 | unchecked | 融资事件较少，暂未纳入5家深度分析 |
| BSE001 | 三协电机 | ✅ | ✅ | ✅ | ✅ | 仅候选文本 | unchecked | 北交所企业，融资历史简单 |
| BSE002 | 星图测控 | ✅ | ✅ | ✅ | ✅ | 仅候选文本 | unchecked | 北交所企业，融资历史简单 |

> 注：友升股份MD文件名为"友声股份"，星图测控MD文件名为"星空测控"，解析阶段OCR识别偏差，建议在文件名映射表中统一。

---

## 3. 招股说明书来源

- **使用的网站**：巨潮资讯网 (cninfo.com.cn) 、上海证券交易所科创板 (kcb.sse.com.cn) 、北京证券交易所 (bse.cn)
- **检索路径**：巨潮资讯网 → 信息披露 → 新股发行 → 招股说明书 → 按公司名称/代码检索
- **文件筛选规则**：
  1. 文件名包含"招股说明书"或"招股意向书"
  2. 排除"问询回复函"、"上市公告书"、"发行公告"
  3. 优先选择"申报稿"（融资历史信息最完整）
  4. PDF页数300-800页之间
- **下载方式**：CSV中预填写prospectus_url，通过`05_pdf_downloader.py`批量下载

---

## 4. 代码说明

### 代码目录结构
```
code/
├── README.md                          # 代码文档
├── run_all.sh                         # 一键运行脚本
├── logger_util.py                     # 日志工具
├── pipeline_main.py                   # 主运行脚本（8步骤）
├── 05_pdf_downloader.py               # PDF下载爬虫
├── 06_pdf_to_markdown.py              # PDF→Markdown解析
├── 01_group_and_locate_chapters.py    # 分组→目录→定位→截取
├── 02_build_timeline_and_events.py    # 时间线+融资事件
├── 04_schema_json_output.py           # 最终Schema JSON输出
└── 03_manual_deep_extract_top5.py     # 手动深度提取（参考）
```

### 下载代码 (`05_pdf_downloader.py`)
- 从CSV企业清单读取`prospectus_url`字段
- 使用urllib下载PDF，支持SSL、超时重试
- 验证PDF文件头`%PDF`
- 计算MD5校验，避免重复下载
- 下载记录保存到`logs/download_record_*.json`

### 解析代码 (`06_pdf_to_markdown.py`)
- 优先使用MinerU (`magic-pdf`) 命令行解析中文PDF
- 备选PyMuPDF (`fitz`) 提取文本
- 保留Markdown标题层级和HTML表格结构
- 输出到`review/`目录

### 定位代码 (`01_group_and_locate_chapters.py` + `pipeline_main.py`)
- 按公司名正则分组MD文件
- 提取前300行的目录条目
- 用关键词列表匹配一级标题，定位融资历史相关章节
- 关键词列表见第7节

### 抽取代码 (`02_build_timeline_and_events.py` + `04_schema_json_output.py`)
- 从候选文本中按段落提取日期+金额+投资方
- 构建股权演变时间线
- 输出严格Schema的JSON

### 校验代码 (`pipeline_main.py` Step 7)
- 检查JSON可解析性
- 验证event必填字段：event_order, event_date, date_type, event_type, disclosed_round, inferred_round, investors[], source_section, source_page, evidence_text, confidence
- 验证investor必填字段：investor_original_name, investor_short_name, investor_type, is_pevc, shareholding_ratio_after_event, exit_status_before_ipo
- 校验报告保存到`logs/verify_report_*.json`

### 如何运行
```bash
# 一键运行
bash code/run_all.sh

# 或分步
python3 code/pipeline_main.py        # 主Pipeline
python3 code/04_schema_json_output.py # Schema JSON输出
```

---

## 5. JSON样例

### 文件路径
```
outputs/
├── 黄山谷捷/黄山谷捷_融资历史_结构化.json    (6事件, 16投资人)
├── 云汉芯城/云汉芯城_融资历史_结构化.json    (8事件, 24投资人)
├── 影石创新/影石创新_融资历史_结构化.json    (4事件, 14投资人)
├── 三联锻造/三联锻造_融资历史_结构化.json    (5事件, 15投资人)
├── 赛分科技/赛分科技_融资历史_结构化.json    (3事件, 5投资人)
└── top5_合并融资历史.json                    (5家合并)
```

### 字段是否完整
- ✅ `company_name`, `stock_code`, `exchange`, `board`, `listing_date`
- ✅ `prospectus_title`, `prospectus_url`, `prospectus_version`, `prospectus_date`
- ✅ 每个event含18个字段（event_order → confidence）
- ✅ 每个investor含8个字段（investor_original_name → exit_status_before_ipo）
- ✅ `processing`含5个状态字段

### 是否有证据文本
- ✅ 每个event都有`evidence_text`（原文摘录，50-500字）
- ✅ 每个event都有`source_section`（章节路径）
- ✅ 每个event都有`source_page`（MD文件行号范围）
- ✅ 每个event都有`confidence`评级（high/medium/low）

### 样例（黄山谷捷 event 4 — A轮增资）
```json
{
  "event_order": 4,
  "event_date": "2021-11-11",
  "date_type": "工商变更日",
  "event_type": "增资",
  "disclosed_round": "未披露",
  "inferred_round": "A轮（首次引入外部投资者）",
  "round_inference_basis": "引入赛格高技术和上汽科技两家外部战略/产业投资者",
  "total_investment_amount": 11530.2857,
  "currency": "CNY",
  "share_price": 22.42,
  "pre_money_valuation": 26904.0,
  "post_money_valuation": 38434.2857,
  "valuation_basis": "增资价格22.42元/注册资本。2020年12月31日评估值26,461.86万元",
  "investors": [
    {
      "investor_original_name": "上海广弘实业有限公司",
      "investor_short_name": "赛格高技术",
      "investor_type": "产业资本",
      "is_pevc": "yes",
      "investment_amount": 10377.0,
      "shareholding_ratio_after_event": "27.00%",
      "exit_status_before_ipo": "未退出"
    }
  ],
  "source_section": "第四节 发行人基本情况 / 二、（二）/ 4、2021年11月，第一次增资",
  "source_page": "黄山谷捷2.md 第722-738行",
  "evidence_text": "2021年9月18日，赛格高技术、上汽科技与黄山供销集团、张俊武、周斌及谷捷有限签署《增资协议》，约定谷捷有限增加注册资本514.2857万元，其中赛格高技术认缴462.8571万元、上汽科技认缴51.4286万元，增资价格为22.42元/注册资本，出资方式为货币。增资后：黄山供销集团54.60%、赛格高技术27.00%、张俊武7.70%、周斌7.70%、上汽科技3.00%。",
  "confidence": "high"
}
```

---

## 6. 失败案例

| 公司 | 环节 | 问题 | 当前处理 |
|------|------|------|----------|
| 赛分科技 | JSON输出 | MinerU解析后融资历史章节内容不完整，3个事件confidence均为low | 已标记confidence=low，建议回原始PDF手动补充 |
| 影石创新 | 候选文本 | 有限公司阶段"六次增资扩股"只在验资报告提及，未按轮次逐一披露详情 | 合并为1个事件(inferred_round="天使轮至C轮")，confidence=medium |
| 三联锻造 | 候选文本 | 早期(2007-2017)增资信息仅出现在mermaid flowchart中，缺少详细文字描述 | confidence=medium，保留flowchart解析的文字作为证据 |
| 友升股份 | JSON输出 | 融资事件仅2条，公司本身融资历史简单 | 暂不纳入5家深度分析，保留候选文本 |
| 三协电机 | 章节定位 | 北交所招股书结构与沪深不同，部分融资信息在"历史沿革"小节而非"发行人基本情况" | 已通过扩大关键词范围解决 |
| 全量 | 文件命名 | MinerU输出的MD文件名存在OCR偏差（友升→友声、星图→星空、赛分科技1→赛分科技1md） | 在group_files()中增加模糊匹配，合并为正确的8家公司 |

---

## 7. 本周形成的规则

### 文件识别规则
1. PDF文件名必须包含"招股说明书"，排除"问询回复函"、"上市公告书"、"发行公告"
2. PDF页数范围：300-800页（太短可能是摘要，太长可能含附件）
3. MD文件按`公司名+数字`模式分组，清理`MinerU_markdown_`前缀和`md`后缀

### 章节定位规则
1. 优先匹配一级标题`# 第四节 发行人基本情况`（沪深招股书统一）
2. 其次匹配`# 第四节 公司基本情况`（部分科创板招股书用词不同）
3. 在第四节下进一步定位"股本和股东变化情况"、"历次增资"、"股权转让"等子章节
4. 北交所招股书结构不同，需额外搜索"历史沿革"章节

### 关键词列表
```
FINANCING_KEYWORDS = [
    "发行人基本情况", "公司基本情况",
    "历史沿革", "股本演变", "历次增资",
    "股权转让", "股东变化", "股东情况",
    "公司设立", "发起人", "注册资本.*增加",
    "融资", "吸收合并", "整体变更",
]
```

### JSON字段规则
1. `event_date`格式：YYYY-MM-DD（日未知填01）
2. `date_type`枚举：工商变更日 / 股东会决议日 / 协议签署日 / 未说明
3. `event_type`枚举：增资 / 股权转让 / 增资及股权转让 / 其他（吸收合并、整体变更等）
4. `disclosed_round`：招股书原文披露的轮次名称（未披露则写"未披露"）
5. `inferred_round`：根据上下文推断的轮次名称
6. `investor_type`枚举：VC / PE / 产业资本 / 自然人 / 员工持股平台 / 政府基金 / 其他 / 无法判断
7. `is_pevc`枚举：yes / no / uncertain
8. `exit_status_before_ipo`枚举：未退出 / 全部退出 / 部分退出 / 无法判断
9. `confidence`枚举：high（招股书原文明确记载）/ medium（有证据但细节不完整）/ low（推测为主）
10. `evidence_text`必须是原文摘录，不能是概括
11. `source_section`必须写明章节路径
12. `source_page`必须写明MD文件+行号

---

## 附录：日志文件

| 文件 | 内容 |
|------|------|
| `logs/pipeline_20260605_114408.log` | Pipeline运行日志（errors=0, warnings=0） |
| `logs/verify_report_20260605_114408.json` | JSON Schema校验报告（5家全部PASS） |
| `logs/toc_summary_20260605_114408.md` | 8家公司目录汇总 |
| `logs/run_report_20260605_114408.md` | 运行报告 |
