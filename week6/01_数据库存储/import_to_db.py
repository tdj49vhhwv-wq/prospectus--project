"""
Week 6 - 任务一：数据处理的数据库存储
将八家公司融资事件总表数据导入外部 PostgreSQL 数据库

数据库信息：
  主机: <server-host>
  端口: 5433
  数据库: student
  用户名: <redacted>

表名: zbq (赵秉清姓名首字母)
"""

import pg8000
import os

# 数据库连接配置
# DB_CONFIG → from pipeline.db_config import DB_CONFIG
import sys; sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'pipeline'))
try:
    from db_config import DB_CONFIG
except ImportError:
    DB_CONFIG = {
    'host': os.environ.get('DB_HOST', '<server-host>'),
    'port': int(os.environ.get('DB_PORT', '5433')),
    'database': os.environ.get('DB_NAME', 'student'),
    'user': os.environ.get('DB_USER', '<redacted>'),
    'password': os.environ.get('DB_PASSWORD', ''),
}

# 使用说明: 通过环境变量传入密码，避免硬编码
#   export DB_PASSWORD=<redacted>
#   python 01_数据库存储/import_to_db.py

TABLE_NAME = 'zbq'


def create_table(cur, conn):
    """创建表格（如不存在）"""
    cur.execute(f"""
        SELECT EXISTS (
            SELECT FROM information_schema.tables WHERE table_name = '{TABLE_NAME}'
        )
    """)
    if cur.fetchone()[0]:
        print(f"表 {TABLE_NAME} 已存在，跳过创建")
        return

    cur.execute(f"""
        CREATE TABLE {TABLE_NAME} (
            id SERIAL PRIMARY KEY,
            event_date VARCHAR(50),
            company VARCHAR(100),
            event_type VARCHAR(50),
            investor TEXT,
            amount_price VARCHAR(200),
            difficulty VARCHAR(50),
            evidence VARCHAR(100)
        )
    """)
    conn.commit()
    print(f"表 {TABLE_NAME} 创建成功!")


def parse_markdown_table(filepath):
    """解析 Markdown 表格，提取融资事件数据"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    data_rows = []
    in_table = False

    for line in lines:
        line = line.strip()
        if line.startswith('| 日期'):
            in_table = True
            continue
        if in_table and line.startswith('|---'):
            continue
        if in_table and line.startswith('|'):
            cols = [c.strip() for c in line.split('|')[1:-1]]
            if len(cols) >= 7:
                data_rows.append(cols[:7])
        elif in_table and not line.startswith('|'):
            break

    return data_rows


def import_data(cur, conn, data_rows):
    """将数据导入表格"""
    # 清空旧数据
    cur.execute(f"DELETE FROM {TABLE_NAME}")
    conn.commit()

    inserted = 0
    for row in data_rows:
        cur.execute(f"""
            INSERT INTO {TABLE_NAME}
                (event_date, company, event_type, investor, amount_price, difficulty, evidence)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, row)
        inserted += 1

    conn.commit()
    print(f"成功插入 {inserted} 条记录")
    return inserted


def verify(cur):
    """验证数据完整性"""
    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
    total = cur.fetchone()[0]
    print(f"\n表中总记录数: {total}")

    cur.execute(f"""
        SELECT company, COUNT(*) FROM {TABLE_NAME}
        GROUP BY company ORDER BY COUNT(*) DESC
    """)
    print("\n各公司事件数:")
    for r in cur.fetchall():
        print(f"  {r[0]}: {r[1]}条")


def main():
    # 数据源文件路径
    data_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'final', '八家公司融资事件总表.md'
    )

    if not os.path.exists(data_file):
        print(f"错误: 找不到数据文件 {data_file}")
        return

    # 解析数据
    data_rows = parse_markdown_table(data_file)
    print(f"解析到 {len(data_rows)} 条记录")

    # 连接数据库
    conn = pg8000.connect(**DB_CONFIG)
    cur = conn.cursor()
    print("数据库连接成功!")

    # 建表 + 导入 + 验证
    create_table(cur, conn)
    import_data(cur, conn, data_rows)
    verify(cur)

    conn.close()
    print("\n完成!")


if __name__ == '__main__':
    main()
