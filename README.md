# PEVC 招股说明书融资历史提取项目

## 项目简介

从A股IPO招股说明书中自动提取企业融资历史（增资/股权转让/PEVC投资），输出结构化JSON数据。

## 仓库结构

```
├── README.md
├── company_lists/          # 企业清单 (Week1-3)
├── source_notes/           # 数据源说明
├── code/                   # 代码 (01-07按处理流程)
├── outputs/                # 输出 (候选文本+JSON)
├── logs/                   # 运行日志
├── review/                 # 同行复核
├── weekly_reports/         # 周报
└── presentation/           # 最终展示
```

## 处理流程

```
PDF下载 → Markdown解析 → 章节定位 → 候选文本截取 → 融资事件抽取 → JSON输出 → 校验
 (03)        (04)           (05)           (06)            (06)         (06)      (07)
```

## Week 1 成果

- 8个公共样本完成 PDF→JSON 完整闭环
- 5家公司完成 Schema 级结构化JSON输出（26事件，74投资人）
- 校验通过率 100%

## 运行方式

```bash
cd code/03_download_pdfs && python3 downloader.py     # PDF下载
cd code/04_parse_pdf_to_markdown && python3 parse_pdf.py  # PDF解析
cd code/05_locate_relevant_sections && python3 locate_sections.py  # 章节定位
cd code/06_extract_pevc_info && python3 extract_events.py  # 事件抽取
cd code/06_extract_pevc_info && python3 schema_output.py   # JSON输出
cd code/07_validate_outputs && python3 validate.py    # 校验
```
