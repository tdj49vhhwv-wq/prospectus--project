"""
P0简化版: 交叉验证 — 比例和检查 + 前后一致性
"""
import re, os
from collections import defaultdict
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

def main():
    conn = pg8000.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("DELETE FROM zbq_cross_check WHERE check_point LIKE '%比例%' OR check_point LIKE '%订阅%'")
    conn.commit()

    total = pass_cnt = fail_cnt = 0

    # 1. 比例和检查
    cur.execute("""
        SELECT stock_code, snapshot_label, SUM(shareholding_pct) as total_pct, COUNT(*) as n
        FROM zbq_equity_snapshot
        WHERE shareholding_pct IS NOT NULL AND snapshot_label IS NOT NULL AND snapshot_label != ''
        GROUP BY stock_code, snapshot_label
        ORDER BY stock_code, snapshot_label
    """)

    print("=== 1. 比例和检查 (应在90-110%之间) ===")
    for code, label, pct, n in cur.fetchall():
        total += 1
        if 90 <= pct <= 110:
            result = 'pass'; pass_cnt += 1; icon = '✅'
        elif 85 <= pct <= 115:
            result = 'near_match'; fail_cnt += 1; icon = '⚠️'
        else:
            result = 'pending_review'; fail_cnt += 1; icon = '🔴'

        cur.execute("""
            INSERT INTO zbq_cross_check (company_name, stock_code, check_point,
                prev_snapshot_label, current_snapshot_label,
                flow_qty_change_wan, check_result, notes)
            VALUES ('',%s,%s, %s,%s, %s,%s, %s)
        """, (code, f'比例和检查', label, '', round(pct,1), result,
              f'{n}名股东比例和={pct}% (期望90-110%)'))

        if icon != '✅':
            print(f"  {icon} {code} {label}: {n}股东比例和={pct}%")

    # 2. 订阅流-快照一致性: 每个公司的订阅事件数 vs 快照变化
    print("\n=== 2. 订阅事件-快照一致性 ===")
    cur.execute("""
        SELECT stock_code, COUNT(DISTINCT snapshot_label) as snapshots,
               COUNT(*) as sub_events
        FROM zbq_equity_snapshot WHERE snapshot_label IS NOT NULL AND snapshot_label != ''
        GROUP BY stock_code
    """)
    snap_counts = {r[0]: r[1] for r in cur.fetchall()}

    cur.execute("SELECT stock_code, COUNT(*) FROM zbq_subscription_flow GROUP BY stock_code")
    sub_counts = {r[0]: r[1] for r in cur.fetchall()}

    for code in snap_counts:
        snaps = snap_counts[code]
        subs = sub_counts.get(code, 0)
        ratio = subs / snaps if snaps else 0
        total += 1
        if 1 <= ratio <= 10:
            result = 'pass'; pass_cnt += 1; icon = '✅'
        else:
            result = 'pending_review'; fail_cnt += 1; icon = '⚠️'

        cur.execute("""
            INSERT INTO zbq_cross_check (company_name, stock_code, check_point,
                flow_qty_change_wan, check_result, notes)
            VALUES ('',%s,%s, %s,%s,%s)
        """, (code, f'订阅/快照比', round(ratio,1), result,
              f'{subs}条订阅÷{snaps}个快照={ratio} (1-10正常)'))

        print(f"  {icon} {code}: {subs}订阅÷{snaps}快照={ratio:.1f}")

    # 3. final事件总表覆盖率
    print("\n=== 3. final事件覆盖率 ===")
    cur.execute("SELECT COUNT(*) FROM zbq")
    final_events = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT stock_code) FROM zbq_subscription_flow")
    sub_coverage = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT stock_code) FROM zbq_share_transfer_flow")
    st_coverage = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT stock_code) FROM zbq_equity_snapshot")
    es_coverage = cur.fetchone()[0]

    for metric, val, expected in [
        ('final事件数', final_events, 64),
        ('订阅流公司覆盖', sub_coverage, 8),
        ('转让流公司覆盖', st_coverage, 8),
        ('快照公司覆盖', es_coverage, 8),
    ]:
        total += 1
        ok = val >= expected
        result = 'pass' if ok else 'pending_review'
        if ok: pass_cnt += 1; icon = '✅'
        else: fail_cnt += 1; icon = '🔴'

        cur.execute("""
            INSERT INTO zbq_cross_check (company_name, stock_code, check_point,
                flow_qty_change_wan, check_result, notes)
            VALUES ('','ALL',%s, %s,%s, %s)
        """, (metric, val, result, f'{val}/{expected}'))

        print(f"  {icon} {metric}: {val}/{expected}")

    conn.commit()
    cur.execute("SELECT COUNT(*) FROM zbq_cross_check")
    final = cur.fetchone()[0]
    print(f"\n{'='*50}")
    print(f"交叉验证: {final} 条 (✅{pass_cnt} ⚠️{fail_cnt})")
    conn.close()

if __name__ == "__main__":
    main()
