"""
导出 zbq 全量数据为 SQL dump — 学习刘宇轩 export_sql.py

生成可复现的 SQL 脚本，方便重建数据库
"""
import os, sys
from datetime import datetime
import pg8000

# DB_CONFIG → from pipeline.db_config import DB_CONFIG
import sys; sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'pipeline'))
try:
    from db_config import DB_CONFIG
except ImportError:
    DB_CONFIG = {
    'host': '<server-host>', 'port': 5433, 'database': 'student',
    'user': '<redacted>', 'password': os.environ.get('DB_PASSWORD', ''),
}

TABLES = [
    'zbq', 'zbq_companies', 'zbq_equity_snapshot',
    'zbq_subscription_flow', 'zbq_share_transfer_flow',
    'zbq_pe_fund_detail', 'zbq_cross_check',
]


def export_table(cur, table, f):
    """导出单张表为 INSERT 语句"""
    # 获取主键列（兼容无id列的表如zbq_companies使用company_id）
    try:
        cur.execute(f"SELECT * FROM {table} ORDER BY 1 LIMIT 5000")
    except:
        cur.execute(f"SELECT * FROM {table} LIMIT 5000")
    rows = cur.fetchall()
    cols = [desc[0] for desc in cur.description]

    f.write(f"\n-- Table: {table} ({len(rows)} rows)\n")
    f.write(f"DELETE FROM {table};\n\n")

    for row in rows:
        values = []
        for val in row:
            if val is None:
                values.append('NULL')
            elif isinstance(val, (int, float)):
                values.append(str(val))
            elif isinstance(val, bool):
                values.append('TRUE' if val else 'FALSE')
            else:
                escaped = str(val).replace("'", "''")
                values.append(f"'{escaped}'")

        f.write(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(values)});\n")

    return len(rows)


def main():
    conn = pg8000.connect(**DB_CONFIG)
    cur = conn.cursor()

    dump_path = f"zbq_dump_{datetime.now():%Y%m%d_%H%M%S}.sql"
    with open(dump_path, 'w', encoding='utf-8') as f:
        f.write(f"-- zbq 全量数据导出\n")
        f.write(f"-- 生成时间: {datetime.now():%Y-%m-%d %H:%M:%S}\n")
        f.write(f"-- 服务器: <server-host>:5433\n\n")

        total = 0
        for table in TABLES:
            try:
                n = export_table(cur, table, f)
                print(f"  {table}: {n} 行")
                total += n
            except Exception as e:
                print(f"  {table}: ERROR - {e}")

    print(f"\n导出完成: {dump_path} ({total} 行)")
    conn.close()


if __name__ == "__main__":
    main()
