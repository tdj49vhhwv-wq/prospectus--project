# 招股书PEVC融资历史提取 — 代码文件

## 一键运行

```bash
cd "$(dirname "$0")/.."  # 或直接 cd 到项目根目录
bash code/run_all.sh
```

## 代码文件清单（8个文件）

### 爬虫
| 文件 | 功能 | 输入 | 输出 |
|------|------|------|------|
| `05_pdf_downloader.py` | 招股书PDF下载爬虫。从CSV清单读取目标URL，通过巨潮资讯网/交易所下载PDF，支持断点续传、MD5校验 | `company_lists/*.csv` | `data/prospectus_pdfs/*.pdf` |

### 数据解析
| 文件 | 功能 | 输入 | 输出 |
|------|------|------|------|
| `06_pdf_to_markdown.py` | PDF→Markdown解析。优先使用MinerU(magic-pdf)，备选PyMuPDF。保留表格、标题层级 | `data/prospectus_pdfs/*.pdf` | `review/*.md` |
| `01_group_and_locate_chapters.py` | Step1-4：按公司名分组MD → 提取目录/章节标题 → 定位融资历史章节(增资/股权转让/股东情况等) → 截取候选文本 | `review/*.md` | `outputs/*/候选文本.md`, `outputs/*/章节列表.md` |
| `02_build_timeline_and_events.py` | Step5-6：从候选文本中提取股权演变时间线和融资事件（日期/金额/投资方/持股比例） | `outputs/*/候选文本.md` | `outputs/*/融资历史.json`, `outputs/*/融资历史报告.md` |

### 结构化处理
| 文件 | 功能 | 输入 | 输出 |
|------|------|------|------|
| `04_schema_json_output.py` | **最终输出**：严格按照老师要求的JSON Schema（event_order / date_type / event_type / disclosed_round / inferred_round / investors[] / source_section / source_page / evidence_text / confidence）输出5家重点公司结构化数据 | 手动整理+MD文件 | `outputs/*/融资历史_结构化.json`, `outputs/top5_合并融资历史.json` |
| `03_manual_deep_extract_top5.py` | 手动深度提取5家重点公司（已被04替代，保留作为参考） | `review/*.md` | `outputs/*/` |

### 运行脚本
| 文件 | 功能 | 输入 | 输出 |
|------|------|------|------|
| `pipeline_main.py` | **主运行脚本**：串联Step1-8（分组→目录→定位→截取→保存→校验→报告），自动记录日志 | `review/*.md` | `outputs/*/`, `logs/*.log`, `logs/*.md` |
| `logger_util.py` | 日志工具模块：统一日志格式、错误记录(traceback)、步骤标记、统计输出 | — | `logs/*.log` |
| `run_all.sh` | Shell一键启动脚本：依次执行 爬虫 → PDF解析 → Pipeline → Schema JSON | — | 全部输出 |

## 处理流程图

```
company_lists/*.csv
       │
       ▼
[05_pdf_downloader.py]  ──→ data/prospectus_pdfs/*.pdf
       │
       ▼
[06_pdf_to_markdown.py]  ──→ review/*.md  (MinerU/PyMuPDF解析)
       │
       ▼
[pipeline_main.py]  ──→ outputs/*/候选文本.md
                   ──→ outputs/*/章节列表.md
                   ──→ outputs/*/融资历史.json
                   ──→ logs/*.log (运行日志+错误日志+校验报告)
       │
       ▼
[04_schema_json_output.py]  ──→ outputs/*/融资历史_结构化.json  (符合老师要求Schema)
                             ──→ outputs/top5_合并融资历史.json
```

## 日志说明

每次运行自动在 `logs/` 生成：
- `pipeline_YYYYMMDD_HHMMSS.log` — 完整运行日志
- `errors_YYYYMMDD_HHMMSS.log` — 错误记录(含traceback)
- `run_report_YYYYMMDD_HHMMSS.md` — 运行报告(Markdown)
- `toc_summary_YYYYMMDD_HHMMSS.md` — 目录汇总
- `verify_report_YYYYMMDD_HHMMSS.json` — JSON Schema校验报告
- `downloader_YYYYMMDD_HHMMSS.log` — 爬虫下载日志
- `download_record_YYYYMMDD_HHMMSS.json` — 下载记录
- `parse_record_YYYYMMDD_HHMMSS.json` — PDF解析记录

## 分步运行

```bash
# 单独运行爬虫
python3 code/05_pdf_downloader.py

# 单独解析PDF
python3 code/06_pdf_to_markdown.py

# 单独运行章节定位+候选文本
python3 code/01_group_and_locate_chapters.py

# 单独生成时间线+事件
python3 code/02_build_timeline_and_events.py

# 单独生成Schema JSON
python3 code/04_schema_json_output.py

# 运行完整Pipeline
python3 code/pipeline_main.py
```
