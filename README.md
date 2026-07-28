# PE/VC 招股说明书融资历史提取

从 IPO 招股说明书中提取 PE/VC 融资历史事件，输出结构化 JSONL，支持 Schema 校验和 Cross-Check。

**姓名**：赵秉清
**仓库**：tdj49vhhwv-wq/prospectus--project
**当前**：Week 6（统一流水线 + 融资分析报告）

---

## 一键运行

```bash
pip install -r requirements.txt
python pipeline/run.py                  # 跑全部8家
python pipeline/run.py --code 920100    # 只跑三协电机
python pipeline/run.py --code 688775    # 只跑影石创新（含VIE检测）
```

**输入**: `week1/data/week1PDF/` 下的 8 个 PDF + `validation/located_sections_{code}.json`
**输出**: `auto_output/{code}/` 下的四类 JSONL + extraction_summary.json
**人工介入**: `final/` 目录（Auto结果不可修改，人工修订在Final中完成）

---

## 目录结构

```
README.md                      # 本文件：运行方法、完成状态和已知问题
requirements.txt               # 主要依赖版本
data/                          # PDF/Markdown清单及可复跑输入
  pdf_manifest.csv             #   8家公司PDF清单
  pdf_file_list.txt            #   PDF文件名列表
pipeline/                      # 完整自动提取代码和统一入口
  run.py                       #   统一运行入口（8家公司）
  extract_pevc.py              #   核心提取逻辑（正则+表格+VIE）
  config.py                    #   路径/关键词/规则配置
  extract_json_config.py       #   JSON配置驱动提取器
  models.py                    #   Pydantic v2 Schema定义
  test_vie_regression.py       #   VIE误报回归测试
prompts/                       # Prompt、模型参数和调用记录
  prompt_v3_全类型_分模块.md    #   v3最终版（10类型×4模块，T=0.0）
  prompt迭代报告_v1到v2.md     #   v1(38%)→v2(100%) 全过程
  分类体系_最终验证版_含prompt.md # 10类型×35+案例×7种prompt
  prompt验证汇总_3家公司.md    #   三协+影石+云汉 6类型验证
manual_gold/                   # 人工Gold，不要求代码生成
  subscription_flow_gold.jsonl #   认缴流量Gold（131条）
  equity_snapshot_gold.jsonl   #   股权结构Gold
  share_transfer_flow_gold.jsonl # 股权转让Gold
  融资事件总表.jsonl           #   64事件汇总
auto_output/                   # 未经人工修改的raw和Auto三表
  {code}/                      #   每家公司独立目录
    subscription_flow.jsonl
    equity_snapshot.jsonl
    pe_fund_detail.jsonl
    share_transfer_flow.jsonl
    extraction_summary.json
final/                         # 人工及组内复核后的三表和Excel
  八家公司融资事件总表.md      #   最终版64事件
  *_cross_check.xlsx           #   8家公司Cross-Check Excel
validation/                    # schema、Cross-check、Auto-vs-Gold和复核队列
  models.py                    #   Pydantic Schema
  located_sections_*.json      #   章节定位结果
  *_cross_check.xlsx           #   Cross-Check结果
review/                        # 组内差异、处理结论和PR/Issue链接
  （第一组：赵秉清×杨苗鑫 互查记录）
report/
  week6_report.md              #   上市前融资分析报告
logs/                          # 运行记录、输出数量和文件哈希
  run_*.json                   #   每次运行的完整日志
```

---

## 8家公司清单

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

## 完成状态

| 模块 | 状态 | 说明 |
|------|------|------|
| PDF文本提取 | 完成 | PyMuPDF + pdfplumber 双引擎 |
| 章节定位 | 完成 | 8家公司 located_sections 全覆盖 |
| 认缴流量(SF) | 完成 | 正则+表格+全文补充 |
| 股权快照(ES) | 完成 | pdfplumber表格解析 |
| PE基金详情(PF) | 完成 | 备案编码+GP/LP结构 |
| 股权转让(ST) | 完成 | 代持还原+D子类型分类 |
| VIE事件(H) | 完成 | 仅影石创新，9子事件+回归测试 |
| Schema校验 | 完成 | Pydantic v2 |
| Cross-Check | 完成 | 8家公司Excel |
| A2合计修复 | 完成 | 保留合计，不强拆个人 |
| F型转增识别 | 完成 | 资本公积转增≠增资 |
| 融资分析报告 | 完成 | report/week6_report.md |

---

## 已知问题

1. 云汉芯城 p56-58 为 Mermaid 流程图，需 PaddleOCR 补充（已提供 OCR 结果）
2. 三联锻造 t0 设立事件需参考申报文件 4-3（外部依赖）
3. 影石创新 VIE 全流程 confidence=medium（部分事件跨多页）
4. 英文投资人名覆盖率低（需 LLM 辅助）
5. 友升股份 PDF 部分页面扫描质量差

---

## 代码可复现说明

1. 统一运行命令: `python pipeline/run.py`
2. 使用相对路径，不写死本人电脑目录
3. 自动流程从 PDF 生成 Auto 三表，不从 Gold/Final 开始
4. LLM 调用代码和 Prompt 在 `prompts/` 目录，模型参数 T=0.0
5. 外部服务不可用时，可读取 `validation/located_sections_*.json` 重新生成
6. Final 中的人工修订保留修改前后值、原因和 PDF 证据

---

## 历史周次

- Week 1: 企业清单 + 基础提取（19家科创板）
- Week 2: 8家公共样本 + Pydantic校验
- Week 3: Gold Standard + 自动化流水线
- Week 4: 三协电机深度提取 + PPT汇报
- Week 5: 分类体系 + Prompt迭代 + 8家批处理
- Week 6: 统一流水线 + 目录规范化 + 融资报告
