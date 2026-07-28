# Week 6 — 运行日志

## 最新运行 (2026-07-24)

### 数据库导入 (import_to_db.py)
- 时间: 2026-07-24 17:27
- 状态: ✅ 成功
- 输出: 64条记录 → zbq表 (PostgreSQL <server-host>:5433)

### 全量导入 (import_all_tables.py)
- 时间: 2026-07-24 17:42
- 状态: ✅ 成功
- 输出:
  - zbq_companies: 8条
  - zbq_equity_snapshot: 313条 (跳过125条无效数据)
  - zbq_subscription_flow: 84条
  - zbq_share_transfer_flow: 25条
  - zbq_pe_fund_detail: 2条
  - zbq_cross_check: 64条

## 运行方式

```bash
cd week6
pip install -r requirements.txt

# 数据库导入
DB_PASSWORD=<redacted> python 01_数据库存储/import_to_db.py

# 全量表导入
DB_PASSWORD=<redacted> python 01_数据库存储/import_all_tables.py

# 自动提取流程
python pipeline/run.py
```
