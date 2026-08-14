#!/usr/bin/env python3
"""Post-Blind Revision — Formal Blind Run #2 evaluator.

Identical matching logic to evaluate_blind_run1.py, but reads the Stage 7.2
auto output (blind_run2/week9_blind_run2_pevc_rows.csv). Gold is unchanged:
the frozen week9/blind_run1/blind_gold.csv (161 rows, include_pevc=是).

Matching key = (stock_code, subscription_date[:7], event_context, norm(subscriber_name)).
"""
import csv, re, json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
AUTO=ROOT/'blind_run2'/'week9_blind_run2_pevc_rows.csv'
GOLD=ROOT/'blind_run1'/'blind_gold.csv'

def norm(x):
    s=str(x or '').strip().upper().replace('（','(').replace('）',')')
    s=re.sub(r'\s+','',s)
    return s.strip('，。；、,;:')

def key(r):
    return (str(r.get('stock_code','')).strip(),str(r.get('subscription_date',''))[:7],str(r.get('event_context','')).strip(),norm(r.get('subscriber_name','')))

def main():
    with AUTO.open(encoding='utf-8-sig') as f: auto=list(csv.DictReader(f))
    with GOLD.open(encoding='utf-8-sig') as f: gold=[r for r in csv.DictReader(f) if str(r.get('include_pevc','')).strip() in {'是','1','true','True','yes','YES'}]
    G={key(r):r for r in gold}; A={key(r):r for r in auto}
    tp_keys=set(G)&set(A); fp_keys=set(A)-set(G); fn_keys=set(G)-set(A)
    tp=len(tp_keys); fp=len(fp_keys); fn=len(fn_keys)
    p=tp/(tp+fp) if tp+fp else 0.0
    r=tp/(tp+fn) if tp+fn else 0.0
    f1=2*p*r/(p+r) if p+r else 0.0

    # details CSV
    rows=[]
    for k in sorted(tp_keys): rows.append(('TP',)+k)
    for k in sorted(fp_keys): rows.append(('FP',)+k)
    for k in sorted(fn_keys): rows.append(('FN',)+k)
    det=ROOT/'blind_run2'/'blind_eval_details.csv'
    with det.open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f)
        w.writerow(['status','stock_code','subscription_date','event_context','subscriber_name'])
        w.writerows(rows)

    summary={'gold_pevc':len(G),'auto_pevc':len(A),'tp':tp,'fp':fp,'fn':fn,
             'precision':p,'recall':r,'f1':f1}
    (ROOT/'blind_run2'/'blind_eval_summary.json').write_text(
        json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

    print('='*48)
    print('Formal Blind Run #2 — PE/VC Evaluation (Stage 7.2)')
    print('='*48)
    print(f'Gold PE/VC : {len(G)}')
    print(f'Auto PE/VC : {len(A)}')
    print(f'TP         : {tp}')
    print(f'FP         : {fp}')
    print(f'FN         : {fn}')
    print(f'Precision  : {p:.2%}')
    print(f'Recall     : {r:.2%}')
    print(f'F1         : {f1:.2%}')

if __name__=='__main__': main()
