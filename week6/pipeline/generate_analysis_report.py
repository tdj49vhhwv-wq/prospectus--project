"""
P2: 数据分析可视化 — 生成HTML报告

4类图表: 投资人分布 / 融资时间线 / 估值增长 / 融资模式总结
"""
import json, os
from datetime import datetime
from collections import Counter, defaultdict
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

def fetch_data():
    conn = pg8000.connect(**DB_CONFIG)
    cur = conn.cursor()

    # 1. 投资人类型分布
    cur.execute("""
        SELECT investor_type, COUNT(*) as cnt
        FROM zbq_subscription_flow
        WHERE investor_type IS NOT NULL
        GROUP BY investor_type ORDER BY cnt DESC
    """)
    investor_dist = [(r[0], r[1]) for r in cur.fetchall()]

    # 2. 融资时间线
    cur.execute("""
        SELECT stock_code, company_name, event_date, event_type, investor_name,
               subscription_amount_wan, subscription_price
        FROM zbq_subscription_flow
        WHERE event_date IS NOT NULL AND event_date != ''
        ORDER BY stock_code, event_date
    """)
    timeline_raw = cur.fetchall()

    # 3. 估值增长
    cur.execute("""
        SELECT stock_code, event_date, subscription_price, investor_name
        FROM zbq_subscription_flow
        WHERE subscription_price IS NOT NULL AND subscription_price > 0
        ORDER BY stock_code, event_date
    """)
    valuation_raw = cur.fetchall()

    # 4. 各公司事件统计
    cur.execute("""
        SELECT s.stock_code, COUNT(*) as events, COUNT(DISTINCT s.event_type) as types,
               COUNT(DISTINCT CASE WHEN investor_type='PE' THEN s.investor_name END) as pe_count,
               COUNT(DISTINCT CASE WHEN investor_type='政府基金' THEN s.investor_name END) as gov_count
        FROM zbq_subscription_flow s
        GROUP BY s.stock_code ORDER BY events DESC
    """)
    company_stats = cur.fetchall()

    conn.close()

    # 组织时间线数据
    timeline = defaultdict(list)
    for code, name, date, etype, investor, amt, price in timeline_raw:
        timeline[code].append({
            'name': name, 'date': str(date)[:10], 'type': etype,
            'investor': str(investor)[:30] if investor else '',
            'amount': float(amt) if amt else 0,
            'price': float(price) if price else 0,
        })

    # 组织估值数据
    valuation = defaultdict(list)
    for code, date, price, investor in valuation_raw:
        if price:
            valuation[code].append({
                'date': str(date)[:10], 'price': float(price),
                'investor': str(investor)[:20] if investor else '',
            })

    return investor_dist, dict(timeline), dict(valuation), company_stats


def gen_html(investor_dist, timeline, valuation, company_stats):
    """生成HTML报告"""
    # 投资人分布数据
    inv_labels = json.dumps([x[0] for x in investor_dist])
    inv_values = json.dumps([x[1] for x in investor_dist])

    # 估值曲线数据
    val_data = {}
    for code, points in valuation.items():
        if len(points) >= 2:
            val_data[code] = {
                'dates': json.dumps([p['date'] for p in sorted(points, key=lambda x: x['date'])]),
                'prices': json.dumps([p['price'] for p in sorted(points, key=lambda x: x['date'])]),
                'labels': json.dumps([p['investor'] for p in sorted(points, key=lambda x: x['date'])]),
            }

    # 公司统计
    stats_rows = ""
    for code, ev, types, pe, gov in company_stats:
        stats_rows += f"<tr><td>{code}</td><td>{ev}</td><td>{types}</td><td>{pe}</td><td>{gov}</td></tr>"

    # 融资模式总结
    mode_data = [
        ("标准PE/VC路径", "赛分科技/友升股份/黄山谷捷/星图测控", "设立→早期增资→中后期PE抱团→员工激励→股改→IPO", 4),
        ("VIE回归路径", "影石创新", "境外VIE搭建→开曼融资→回购→镜像回归→境内增资→IPO", 1),
        ("产业孵化路径", "云汉芯城/星图测控", "母公司合资设立→引入产业投资者→员工激励→IPO", 2),
        ("北交所精简路径", "三协电机/星图测控", "设立→1-2次定增→股改→北交所IPO", 2),
    ]
    mode_rows = ""
    for mname, companies, flow, cnt in mode_data:
        mode_rows += f"<tr><td><b>{mname}</b></td><td>{companies}</td><td>{flow}</td><td>{cnt}家</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang='zh-CN'>
<head><meta charset='UTF-8'><title>PE/VC 融资分析报告</title>
<script src='https://cdn.jsdelivr.net/npm/chart.js@4'></script>
<style>
body{{font-family:-apple-system,sans-serif;max-width:1100px;margin:0 auto;padding:20px;background:#f5f5f5}}
.card{{background:white;border-radius:12px;padding:24px;margin:20px 0;box-shadow:0 2px 8px rgba(0,0,0,.1)}}
h1{{color:#1a1a2e}}h2{{color:#16213e;border-bottom:2px solid #3498db;padding-bottom:8px}}
.charts{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
table{{width:100%;border-collapse:collapse;margin:10px 0}}
th,td{{padding:10px;text-align:left;border-bottom:1px solid #eee}}
th{{background:#3498db;color:white}}
.badge{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px;color:white}}
.badge-pe{{background:#e74c3c}}.badge-vc{{background:#2ecc71}}.badge-gov{{background:#f39c12}}.badge-corp{{background:#9b59b6}}.badge-fo{{background:#1abc9c}}
@media(max-width:768px){{.charts{{grid-template-columns:1fr}}}}
</style></head>
<body>
<h1>📊 8家公司 PE/VC 融资分析报告</h1>
<p>赵秉清 | 数据来源: 8家公司招股说明书 | 生成: {datetime.now():%Y-%m-%d %H:%M}</p>

<div class='card'>
<h2>一、投资人类型分布</h2>
<div class='charts'>
<div><canvas id='investorPie'></canvas></div>
<div><canvas id='investorBar'></canvas></div>
</div>
</div>

<div class='card'>
<h2>二、公司融资统计</h2>
<table>
<tr><th>公司</th><th>事件数</th><th>事件类型</th><th>PE基金数</th><th>政府基金数</th></tr>
{stats_rows}
</table>
</div>

<div class='card'>
<h2>三、估值增长曲线（价格变化）</h2>
<div class='charts'>
{"".join(f"<div><canvas id='val_{code}'></canvas><p style='text-align:center'>{code}</p></div>" for code in val_data)}
</div>
</div>

<div class='card'>
<h2>四、融资模式总结</h2>
<table>
<tr><th>模式</th><th>代表公司</th><th>路径</th><th>覆盖面</th></tr>
{mode_rows}
</table>
</div>

<div class='card'>
<h2>五、关键发现</h2>
<ul>
<li><b>PE集中进入</b>: 中后期增资轮通常有5-10家机构同时进入（赛分科技10家、友升股份10家），形成"抱团投资"</li>
<li><b>估值跃升</b>: 首轮到IPO，估值增幅10-100倍。赛分科技从6.15元→127.24元，4年增长20倍</li>
<li><b>员工激励前置</b>: 全部8家公司在股改前1-2年完成员工持股平台增资，价格低于外部融资</li>
<li><b>政府基金渗透</b>: 云汉芯城(国科瑞华)、星图测控(中科星图)、友升股份(金浦临港)有明显政府引导基金参与</li>
<li><b>外资差异化</b>: 仅影石创新有境外VIE架构和外资基金，其余7家为纯内资结构</li>
</ul>
</div>

<script>
// 投资人分布
new Chart(document.getElementById('investorPie'),{{
  type:'doughnut',
  data:{{
    labels:{inv_labels},
    datasets:[{{data:{inv_values},backgroundColor:['#e74c3c','#2ecc71','#f39c12','#9b59b6','#1abc9c','#34495e','#95a5a6','#e67e22']}}]
  }},
  options:{{plugins:{{title:{{display:true,text:'投资人类型分布'}}}}}}
}});
new Chart(document.getElementById('investorBar'),{{
  type:'bar',
  data:{{
    labels:{inv_labels},
    datasets:[{{label:'记录数',data:{inv_values},backgroundColor:'#3498db'}}]
  }},
  options:{{plugins:{{title:{{display:true,text:'各类型记录数'}}}}}}
}});
// 估值曲线
"""
    for code, v in val_data.items():
        html += f"""
new Chart(document.getElementById('val_{code}'),{{
  type:'line',
  data:{{
    labels:{v['dates']},
    datasets:[{{label:'价格(元/股)',data:{v['prices']},borderColor:'#e74c3c',tension:0.3}}]
  }},
  options:{{plugins:{{title:{{display:true,text:'{code}'}}}}}}
}});
"""
    html += "</script></body></html>"
    return html


def main():
    print("提取数据...")
    inv, timeline, valuation, stats = fetch_data()
    print(f"  投资人类型: {len(inv)} 类")
    print(f"  公司时间线: {len(timeline)} 家")
    print(f"  估值数据: {len(valuation)} 家")

    html = gen_html(inv, timeline, valuation, stats)
    path = 'report/analysis_charts.html'
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"\n✅ 报告生成: {path}")
    print("   浏览器打开即可查看")


if __name__ == "__main__":
    main()
