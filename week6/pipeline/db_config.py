"""统一数据库连接配置 — 凭据通过环境变量传入，不硬编码"""
import os

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', ''),
    'port': int(os.environ.get('DB_PORT', '5433')),
    'database': os.environ.get('DB_NAME', 'student'),
    'user': os.environ.get('DB_USER', ''),
    'password': os.environ.get('DB_PASSWORD', ''),
}
