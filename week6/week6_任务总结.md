# Week 6 任务总结

**赵秉清 | 2026-07-24**

---

## 任务一：数据库存储

### 完成内容

1. **PostgreSQL 数据库连接**：在服务器 `<server-host>:5433` 的 `student` 数据库中建立 `zbq` 系列表。

2. **表结构对齐**：对比同组同学（lyx、ymx、lzr）的数据库结构，发现千问生成的原始表仅有 5 张表、基本全是文本字段，缺少数值类型、证据原文、审查状态、投资人分类等关键列。完成后重构为 6 张完整表：

| 表名 | 列数 | 记录数 | 对标 |
|------|:--:|:--:|------|
| `zbq_companies` | 12 | 8 | 公司清单（对齐lzr） |
| `zbq_equity_snapshot` | 22 | 313 | 股权快照（对齐ymx 20列） |
| `zbq_subscription_flow` | 24 | 84 | 认缴流量（对齐ymx 22列） |
| `zbq_share_transfer_flow` | 23 | 25 | 股权转让（对齐ymx 21列） |
| `zbq_pe_fund_detail` | 20 | 2 | PE基金详情（独有） |
| `zbq_cross_check` | 19 | 64 | 交叉验证（对齐ymx） |

3. **数据导入**：从 `auto_output/` JSONL 文件和 `final/八家公司融资事件总表.md` 导入全量数据，64 条融资事件覆盖 8 家公司。

4. **工具安装**：安装 DBeaver GUI 客户端，实现数据库可视化查看。

> 详见：`01_数据库存储/import_to_db.py`、`01_数据库存储/import_all_tables.py`

---

## 任务二：学术论文研读

### 论文信息

- **题目**: Does Venture Capital Backing Improve Disclosure Controls and Procedures? Evidence from Management's Post-IPO Disclosures
- **作者**: Douglas Cumming, Lars Helge Hass, Linda A. Myers, Monika Tarsalewska
- **期刊**: Journal of Business Ethics, 2023, Vol.187(3), pp.539-563

### 完成内容

1. **论文评述**：从研究问题、研究方法、数据来源、主要结论、创新之处、不足之处六个维度完成详细评述。

2. **与项目关联分析**：将论文核心发现（VC 支持改善信息披露质量）与本项目 8 家公司的实际提取数据对照，验证了 VC 参与度越高、招股书融资历史披露越规范、自动提取准确率越高的规律。

3. **批判性思考**：从中国情境适用性（IPO 审核制 vs 注册制）、数据源差异（招股书 vs 年报）、VC 异质性分类（七类投资人体系 vs 论文的 VC 同质化）等角度进行了独立分析。

4. **双版本输出**：
   - `VC_PE领域论文评述_赵秉清.docx`（千问生成详版）
   - `VC_PE领域论文评述_赵秉清.md`（整合版 + 项目独有批判分析，GitHub 可在线预览）

> 详见：`02_论文研读/`

---

## 附加：项目目录整理

GitHub 仓库根目录原有 17 个文件/文件夹杂乱散落，本次整理为清晰的分类结构：

```
prospectus-pevc-project/
├── README.md
├── data/gold_standard/    ← 金标准数据
├── docs/
│   ├── prompts/           ← prompt工程文档
│   └── review/            ← 评审记录
├── week1/ ~ week6/        ← 按周组织
```

---

## 不足与待改进

1. **PE 基金详情数据不足**：多数公司缺失 `pe_fund_detail.jsonl`，需跑完整 pipeline 重新提取
2. **部分股权快照数据质量差**：千问自动导出时将财务指标（总资产/净利润）误识别为股东名
3. **数据库密码管理**：已改为环境变量方式，但需确认服务器侧也做了安全配置
4. **论文研读可进一步扩充**：建议后续增加第二篇论文（关注 PE/Pre-IPO 方向），形成对比研读
