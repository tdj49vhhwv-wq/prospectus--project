"""
P0: 交叉验证从标记升级为数值验证

逻辑: 对每家公司，按时间排序快照(s0→s1→s2...)
     验证: s0注册资本 + 期间订阅流量 = s1注册资本
     差异>5% → pending_review
"""
import re, os, sys
from pathlib import Path
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


def get_snapshots(cur, code):
    """获取一家公司的所有快照，按时间排序"""
    cur.execute("""
        SELECT snapshot_label, snapshot_date,
               COALESCE(SUM(shares_wan), 0) as total_shares,
               COUNT(*) as shareholders,
               COALESCE(SUM(shareholding_pct), 0) as total_pct
        FROM zbq_equity_snapshot
        WHERE stock_code = %s
          AND snapshot_label IS NOT NULL AND snapshot_label != ''
        GROUP BY snapshot_label, snapshot_date
        HAVING COUNT(*) >= 2  -- 至少2个股东的快照才算
        ORDER BY snapshot_date, snapshot_label
    """, (code,))
    return cur.fetchall()


def get_flow_events(cur, code, snap1_date, snap2_date):
    """获取两个快照之间的订阅流量（用股数）"""
    cur.execute("""
        SELECT '增资' as event_type,
               COALESCE(SUM(subscription_amount_wan), 0) as total_amount,
               COALESCE(SUM(subscription_qty_wan), 0) as total_qty,
               COUNT(*) as events
        FROM zbq_subscription_flow
        WHERE stock_code = %s
          AND event_date >= %s
          AND event_date <= %s
          AND event_type NOT IN ('设立', '股改', '资本公积转增', 'IPO', '吸收合并')
    """, (code, snap1_date or '1900-01-01', snap2_date or '2099-12-31'))
    return cur.fetchall()


def main():
    conn = pg8000.connect(**DB_CONFIG)
    cur = conn.cursor()

    # 清空旧的cross_check
    cur.execute("DELETE FROM zbq_cross_check WHERE check_point LIKE '%数值验证%'")
    conn.commit()

    print("=" * 60)
    print("P0: 交叉验证数值化")
    print("=" * 60)

    cur.execute("SELECT DISTINCT stock_code FROM zbq_companies ORDER BY stock_code")
    companies = [r[0] for r in cur.fetchall()]

    total = 0
    issues = 0

    for code in companies:
        snapshots = get_snapshots(cur, code)
        if len(snapshots) < 2:
            continue

        print(f"\n📊 {code} ({len(snapshots)} 个快照)")

        for i in range(len(snapshots) - 1):
            prev_label, prev_date, prev_shares, prev_n, prev_pct = snapshots[i]
            curr_label, curr_date, curr_shares, curr_n, curr_pct = snapshots[i + 1]

            # 跳过无股数的快照
            if prev_shares == 0 or curr_shares == 0:
                continue

            # 获取期间的流量
            flows = get_flow_events(cur, code, prev_date, curr_date)
            flow_amount = sum(f[1] for f in flows) if flows else 0
            flow_qty = sum(f[2] for f in flows) if flows else 0
            flow_events = sum(f[3] for f in flows) if flows else 0

            # 用股数做验证: prev shares + flow qty = curr shares
            expected = prev_shares + flow_qty
            # 披露值
            disclosed = curr_shares
            diff = disclosed - expected
            diff_pct = (diff / expected * 100) if expected > 0 else 0

            # 判定结果
            abs_pct = abs(diff_pct)
            if abs_pct <= 1:
                result = 'pass'
            elif abs_pct <= 5:
                result = 'near_match'
            else:
                result = 'pending_review'
                issues += 1

            cur.execute("""
                INSERT INTO zbq_cross_check
                    (company_name, stock_code, check_point,
                     prev_snapshot_label, current_snapshot_label,
                     prev_total_capital_wan,
                     flow_event_type, flow_amount_wan, flow_qty_change_wan,
                     expected_next_capital, disclosed_capital,
                     difference_wan, diff_pct, check_result,
                     notes, evidence_pdf_page)
                VALUES (%s,%s,%s, %s,%s, %s, %s,%s,%s, %s,%s, %s,%s,%s, %s,%s)
            """, (
                '', code,
                f'股数验证: {prev_label}→{curr_label}',
                prev_label, curr_label,
                round(prev_shares, 2),
                f'{flow_events}事件', flow_amount, flow_qty,
                round(expected, 2), round(disclosed, 2),
                round(diff, 2), round(diff_pct, 2),
                result,
                f'股数: {prev_shares}+{flow_qty}={expected} vs 披露{disclosed} | 比例和: {prev_pct}%→{curr_pct}%',
                None,
            ))
            total += 1

            icon = '✅' if result == 'pass' else '⚠️' if result == 'near_match' else '🔴'
            print(f"  {icon} {prev_label}→{curr_label}: 股数{prev_shares}+{flow_qty}={expected} vs 披露{disclosed} ({diff_pct:+.1f}%) | 比例和{prev_pct}%→{curr_pct}%")

    conn.commit()

    cur.execute("SELECT COUNT(*), SUM(CASE WHEN check_result='pass' THEN 1 ELSE 0 END), SUM(CASE WHEN check_result='pending_review' THEN 1 ELSE 0 END) FROM zbq_cross_check WHERE check_point LIKE '%数值验证%'")
    t, ok, review = cur.fetchone()
    print(f"\n{'='*60}")
    print(f"交叉验证: {t} 条 (✅{ok} ⚠️{review})")
    print(f"总cross_check: ", end='')
    cur.execute("SELECT COUNT(*) FROM zbq_cross_check")
    print(f"{cur.fetchone()[0]} 条")
    conn.close()


if __name__ == "__main__":
    main()
