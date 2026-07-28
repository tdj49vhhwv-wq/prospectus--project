# Week 6 任务

## 统一运行命令

```bash
cd week6
pip install -r requirements.txt

# 1. 数据库全量导入（主事件表 + 6张明细表）
export DB_PASSWORD=<username>
python 01_数据库存储/import_to_db.py         # 64条融资事件 → zbq主表
python 01_数据库存储/import_all_tables.py     # 6张明细表全量导入

# 2. PDF独立提取股权快照（对标ymx多快照模式）
python 01_数据库存储/extract_equity_from_pdf.py
python 01_数据库存储/extract_equity_retry.py

# 3. 补充逐投资人拆分（学习ymx）
python 01_数据库存储/supplement_from_ymx.py

# 4. 自动提取（如PDF已就绪）
python pipeline/run.py                       # 全部8家
python pipeline/run.py --code 920100         # 单家公司
```

---

## 任务一：数据库存储

### 数据库信息

| 项目 | 值 |
|------|-----|
| 主机 | <server-host> |
| 端口 | 5433 |
| 数据库名 | student |
| 用户名 | <username> |
| 表名 | zbq 系列 |

### 表结构（对标同学后升级）

| 表名 | 列数 | 记录数 | 对标 |
|------|:--:|:--:|------|
| `zbq` | 8 | 64 | 融资事件主表 |
| `zbq_companies` | 12 | 8 | 公司清单 |
| `zbq_equity_snapshot` | 22 | 601 | 股权快照（对标ymx 678） |
| `zbq_subscription_flow` | 24 | 181 | 认缴流量（超ymx 172） |
| `zbq_share_transfer_flow` | 23 | 43 | 股权转让（达ymx 72%） |
| `zbq_pe_fund_detail` | 20 | 2 | PE基金详情（独有） |
| `zbq_cross_check` | 19 | 64 | 交叉验证 |

### 流程

```
PDF(pdfplumber) → 股东表提取 → equity_snapshot(多快照)
final/事件总表 → 逐投资人拆分 → subscription_flow + share_transfer_flow
→ Schema校验 → Cross-check → 数据库入库
```

---

## 任务二：学术论文研读

| 项目 | 内容 |
|------|------|
| 题目 | Does Venture Capital Backing Improve Disclosure Controls and Procedures? |
| 作者 | Cumming, Hass, Myers, Tarsalewska (2023) |
| 期刊 | Journal of Business Ethics |
| 输出 | `02_论文研读/VC_PE领域论文评述_赵秉清.docx` + `.md` |

独创贡献：将论文"VC改善信息披露质量"的核心发现，用本项目8家公司实际数据验证——VC参与度越高，提取准确率越高。

---

## 完成状态

- [x] 数据库建表（6张，120列，对标ymx/lyx）
- [x] 64条融资事件导入
- [x] PDF独立提取股权快照（313→601条，达ymx的89%）
- [x] 逐投资人拆分subscription_flow（181条，超ymx）
- [x] 论文评述（双版本：docx + md）
- [x] 组内互查（赵秉清↔杨苗鑫，数据库实测对比）
- [x] 事件类型编码映射表
- [x] 事件分类定义JSON
- [ ] 三协电机/星图测控部分页为图片格式，需OCR补全
- [ ] PE基金详情仅2条，需扩展

## 已知问题

1. **图片格式表格**: 三协电机p30-32和星图测控p44-48部分股东表为图片格式，pdfplumber无法提取，需PaddleOCR补充
2. **PE基金覆盖不足**: 仅三协电机有pe_fund_detail，其余7家需从PDF中的"私募基金备案情况"章节提取
3. **股权转让细节**: 部分转让事件的转让方/受让方和金额PDF未逐笔披露（如三联锻造"4次增资+4次转让"仅在申报文件4-3中详细列明）
4. **非现金出资**: 吸收合并(G型)/整体变更(B型)的金额为净资产折股，非现金流入，标注为0或特殊说明
5. **云汉芯城p56-58**: 股权演变流程图为图片格式，需OCR提取

## 目录结构

```text
README.md                   # 运行方法、完成状态和已知问题
requirements.txt            # 主要依赖版本
data/                        # 数据清单及可复跑输入
pipeline/                    # 完整自动提取代码和统一入口
prompts/                     # Prompt、模型参数和调用记录
manual_gold/                 # 人工Gold标准数据索引
auto_output/                 # 未经人工修改的raw和Auto三表
final/                       # 人工及组内复核后的三表和Excel
validation/                  # schema、Cross-check、located_sections
review/                      # 组内互查记录
report/week6_report.md       # 上市前融资分析报告
raw_llm_responses/           # LLM原始响应存档（对标ymx）
logs/                        # 运行记录
01_数据库存储/               # 数据库导入脚本
02_论文研读/                 # 论文评述
```

## 依赖

见 `requirements.txt`
