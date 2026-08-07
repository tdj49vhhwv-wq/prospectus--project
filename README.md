# PE/VC 招股说明书融资历史提取

从 IPO 招股说明书中提取 PE/VC 融资历史事件，输出结构化 JSONL，并通过 Gold Standard、Schema 和 Cross-Check 检查数据质量。

**姓名**：赵秉清<br>
**仓库**：tdj49vhhwv-wq/prospectus--project<br>
**当前**：Week 7 修订完成，Week 8 将建立统一 Auto-vs-Gold 评价器

---

## 快速开始

### 1. 安装核心依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r week6/requirements.txt
```

PaddleOCR/PaddlePaddle 仅用于流程图 OCR；若本机安装困难，可先不运行 OCR 相关步骤。

### 2. PDF 管线

```bash
python3 week6/pipeline/run.py                  # 跑全部 8 家
python3 week6/pipeline/run.py --code 920100   # 只跑三协电机
python3 week6/pipeline/run.py --code 688775   # 只跑影石创新
```

**输入**：`week1/data/week1PDF/` 下的 PDF，以及 `week6/validation/located_sections_{code}.json`。<br>
**输出**：`week6/auto_output/{code}/` 下的四类 JSONL 和 `extraction_summary.json`。

> PDF 大文件当前未跟踪在 Git 中。缺少 PDF 时，PDF 管线会跳过相应公司。

### 3. Markdown 候选管线

```bash
cd week6
python3 pipeline/run_md_pipeline.py
cd ..
```

默认读取仓库内 `week1/review/`，生成 `week6/auto_output_md/` 候选文件。若 Markdown 在其他目录，可设置：

```bash
export PROSPECTUS_MD_DIR="/absolute/path/to/review"
```

> 当前 Markdown 管线生成的是宽松正则候选，不是 Final 数据。确定性修复后可复跑得到 645 条候选，其中存在大量误报和字段缺失，不能把候选条数当成准确率，也不要直接用于正式分析。

### 4. LLM 环境变量

```bash
export DEEPSEEK_API_KEY="your-key"
```

API Key 不得写入 Python、Markdown、日志或提交历史。可参考 `.env.example` 查看变量名，但项目不会自动加载 `.env`。

---

## 当前权威目录

```text
README.md                       # 当前运行入口和项目状态
data/gold_standard/             # 当前 Gold Standard（人工标注）
week1/review/                   # Git 内可用的招股书 Markdown 文本源
week6/
  requirements.txt             # 主要依赖
  pipeline/                     # 当前提取代码
    run.py                      # PDF 管线入口
    run_md_pipeline.py          # Markdown 候选管线入口
    llm_extractor.py            # DeepSeek 辅助提取器
    markdown_source.py          # Markdown 文本源
  auto_output/                  # PDF 自动结果
  final/                        # 人工复核结果
  validation/                   # located sections 和 Cross-Check
  report/week6_report.md        # 上市前融资分析报告
week7/
  baseline_report.md            # Week 7 修订基线
  week7_汇报与总结.md            # 向老师汇报稿
  project_gap_audit.md          # 全项目缺口审计
  august_2026_plan.md           # 八月完整计划
week8/
  week8_plan.md                 # Week 8 日级任务书
  baseline_report_20260807.md   # 首版事件级 P/R/F1 基线（2026-08-07）
  week8_baseline_report.md      # Week 8 终版基线报告（8/9 任务提前完成）
  evaluate_events.py            # 事件级评价器
week10/
  blind_test/                   # 2 家事件级 Gold 盲测方案（范围已定）
```

---

## 8 家公司清单

| 代码 | 公司 | 板块 | 招股书日期 |
|------|------|------|-----------|
| 001282 | 三联锻造 | 深主板 | 2023-05-17 |
| 301563 | 云汉芯城 | 创业板 | 2025-09-25 |
| 301581 | 黄山谷捷 | 创业板 | 2024-12-19 |
| 603418 | 友升股份 | 沪主板 | 2025-09-18 |
| 688758 | 赛分科技 | 科创板 | 2025-01-06 |
| 688775 | 影石创新 | 科创板 | 2025-06-06 |
| 920100 | 三协电机 | 北交所 | 2025-07-11 |
| 920116 | 星图测控 | 北交所 | 2024-12-20 |

---

## 当前状态

| 模块 | 状态 | 说明 |
|------|------|------|
| PDF/Markdown 文本源 | 已建立，待统一输入版本 | PDF 未跟踪；Markdown 可覆盖 8 家 |
| 章节定位 | 已建立 | 8 家均有 located sections 或 Markdown 片段 |
| Gold Standard | 待版本化 | `subscription_flow` 原口径 124 条，7 条员工平台记录待迁移确认 |
| PDF 自动提取 | 有历史基线 | 旧 Pipeline 输出 18/124 条，尚无严格 P/R/F1 |
| Markdown 候选提取 | 可运行、不可直接使用 | 当前稳定复跑 645 条候选，误报严重 |
| LLM 辅助提取 | 完成小样本试验 | 尚未完成全量盲测和成本评估 |
| Schema/Cross-Check | 已有材料 | 需与统一 Gold 版本和评价器对齐 |
| Auto-vs-Gold 评价 | 事件级六批修复 | validated P=74.00% / R=82.22% / F1=77.89%，见 `week8/baseline_report_20260807.md` |
| 融资分析报告 | 有初稿 | 需在数据质量达标后更新结论 |
| 盲测范围 | 已定 | 688795 摩尔线程 + 688802 沐曦股份，事件级 Gold；方案见 `week10/blind_test/` |

---

## 指标解释

- **候选数**：规则或模型发现的潜在记录数量；越多不一定越好。
- **规则覆盖数**：规则在已知 Gold 原文上能否命中；不能直接当作独立样本 Recall。
- **Precision**：系统输出中真正正确的比例。
- **Recall**：Gold 中被系统找回的比例。
- **F1**：Precision 与 Recall 的调和平均。

项目后续同时报告事件级和投资人明细级指标。8 月底目标为：事件级 Precision、Recall 均不低于 90%，投资人明细级 F1 不低于 80%，并完成 8 家干净环境复跑。

---

## 已知问题

1. 旧 DeepSeek API Key 曾进入 Git 历史，必须在控制台吊销；仅修改当前文件不能消除历史泄露。
2. Markdown 候选管线目前可能在配置数据库后执行写库；评价阶段应保持数据库变量未设置，并在 Week 8 增加显式 `--write-db` 开关。
3. 云汉芯城 p56-58 为流程图，需要 OCR 或人工证据补充。
4. 三联锻造 t0 设立事件依赖申报文件 4-3。
5. 英文投资人、复合事件、重复披露和表格字段映射仍是主要错误来源。
6. 现有数据库测试依赖远程 PostgreSQL，尚无完整离线测试基线。

完整审计见 `week7/project_gap_audit.md`。

---

## 历史周次

- Week 1：企业清单 + 基础提取（19 家科创板候选）
- Week 2：8 家公共样本 + Pydantic 校验
- Week 3：Gold Standard + 自动化流水线
- Week 4：三协电机深度提取 + PPT 汇报
- Week 5：分类体系 + Prompt 迭代 + 8 家批处理
- Week 6：统一流水线 + 数据库存储 + 融资报告
- Week 7：Gold 对照、Markdown 候选管线、质量纠偏
- Week 8：统一评价器、Gold 版本管理、第一份可信 P/R/F1
