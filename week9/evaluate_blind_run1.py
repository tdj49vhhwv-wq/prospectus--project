#!/usr/bin/env python3
import csv, re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
AUTO=ROOT/'blind_run1'/'week9_blind_run1_pevc_rows.csv'
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
    tp=len(set(G)&set(A)); fp=len(set(A)-set(G)); fn=len(set(G)-set(A))
    p=tp/(tp+fp) if tp+fp else 0.0
    r=tp/(tp+fn) if tp+fn else 0.0
    f1=2*p*r/(p+r) if p+r else 0.0
    print('='*48)
    print('Formal Blind Run #1 — PE/VC Evaluation')
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
