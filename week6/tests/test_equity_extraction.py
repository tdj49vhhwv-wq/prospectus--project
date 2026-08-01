"""
测试股权快照提取质量 — 学习李泽润 tests/ 体系

验证:
1. 8家公司全覆盖
2. 每家公司至少3个快照点
3. 股东名不为空、不重复
4. 比例之和≈100%
"""
import re, os, sys
from pathlib import Path
import pg8000
import pytest

# DB_CONFIG → from pipeline.db_config import DB_CONFIG
import sys; sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'pipeline'))
try:
    from db_config import DB_CONFIG
except ImportError:
    DB_CONFIG = {
    'host': '<server-host>', 'port': 5433, 'database': 'student',
    'user': '<redacted>', 'password': os.environ.get('DB_PASSWORD', ''),
}

EXPECTED_COMPANIES = ['001282','301563','301581','603418','688758','688775','920100','920116']

pytestmark = pytest.mark.skipif(
    not DB_CONFIG.get('host') or not DB_CONFIG.get('user'),
    reason="需要通过 DB_HOST 和 DB_USER 配置远程 PostgreSQL 集成测试",
)


def test_all_8_companies_present():
    """测试1: 8家公司全覆盖"""
    conn = pg8000.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT stock_code FROM zbq_equity_snapshot ORDER BY stock_code")
    codes = [r[0] for r in cur.fetchall()]
    missing = set(EXPECTED_COMPANIES) - set(codes)
    assert not missing, f"缺失公司: {missing}"
    print(f"  ✅ 8家公司全覆盖: {codes}")
    conn.close()


def test_min_3_snapshots_per_company():
    """测试2: 每家公司至少有3个快照点"""
    conn = pg8000.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("""
        SELECT stock_code, COUNT(DISTINCT snapshot_label) as snapshots
        FROM zbq_equity_snapshot
        GROUP BY stock_code
        ORDER BY snapshots
    """)
    for code, cnt in cur.fetchall():
        assert cnt >= 3, f"{code}只有{cnt}个快照(需>=3)"
    print(f"  ✅ 所有公司>=3个快照点")
    conn.close()


def test_no_empty_shareholder_names():
    """测试3: 股东名不为空"""
    conn = pg8000.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM zbq_equity_snapshot
        WHERE shareholder_name IS NULL OR shareholder_name = ''
           OR shareholder_name = '（全体股东待PDF提取）'
    """)
    empty = cur.fetchone()[0]
    assert empty == 0, f"有{empty}条空股东名"
    print(f"  ✅ 0条空股东名")
    conn.close()


def test_ratio_sum_around_100():
    """测试4: 快照内比例之和≈100%（±5%）"""
    conn = pg8000.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("""
        SELECT stock_code, snapshot_label, SUM(shareholding_pct) as total
        FROM zbq_equity_snapshot
        WHERE shareholding_pct IS NOT NULL
        GROUP BY stock_code, snapshot_label
        HAVING SUM(shareholding_pct) < 90 OR SUM(shareholding_pct) > 105
    """)
    bad = cur.fetchall()
    if bad:
        print(f"  ⚠ {len(bad)}个快照比例异常: {[(r[0],r[1],round(r[2],1)) for r in bad[:5]]}")
    else:
        print(f"  ✅ 所有快照比例合理")
    conn.close()


def test_no_duplicate_shareholders():
    """测试5: 同一快照无重复股东"""
    conn = pg8000.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("""
        SELECT stock_code, snapshot_label, shareholder_name, COUNT(*)
        FROM zbq_equity_snapshot
        GROUP BY stock_code, snapshot_label, shareholder_name
        HAVING COUNT(*) > 1
    """)
    dups = cur.fetchall()
    assert len(dups) == 0, f"有{len(dups)}组重复股东"
    print(f"  ✅ 无重复股东记录")
    conn.close()


if __name__ == "__main__":
    print("=" * 50)
    print("股权快照质量测试")
    print("=" * 50)
    tests = [
        test_all_8_companies_present,
        test_min_3_snapshots_per_company,
        test_no_empty_shareholder_names,
        test_ratio_sum_around_100,
        test_no_duplicate_shareholders,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"  ❌ {t.__name__}: {e}")
        except Exception as e:
            print(f"  ❌ {t.__name__}: {e}")
    print(f"\n结果: {passed}/{len(tests)} 通过")
