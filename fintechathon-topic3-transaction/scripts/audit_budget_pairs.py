"""Paired uncertainty for the already planned low-rating comparator, fixed scores."""
import json
import numpy as np
import pandas as pd
import analyze_transactions as a

if __name__=='__main__':
 p=pd.read_csv(a.OUT/'test_predictions.csv');s=json.loads((a.OUT/'analysis_summary.json').read_text());y=p.label.to_numpy();rng=np.random.default_rng(a.SEED);dif=[]
 for _ in range(2000):
  ix=rng.integers(0,len(y),len(y));yy=y[ix]
  if len(np.unique(yy))==2:dif.append(a.budget(yy,p[s['primary']].to_numpy()[ix])['precision']-a.budget(yy,p.low_rating.to_numpy()[ix])['precision'])
 main=a.budget(y,p[s['primary']]);low=a.budget(y,p.low_rating)
 result={'primary':s['primary'],'low_rating_strategy':'ascending 180-day available single-seller order mean rating; stable preset hashed-seller tie order', 'primary_minus_low_rating_precision':main['precision']-low['precision'],'paired_ci95':a.interval(dif),'scope':'fixed fitted model, planned comparator; no training uncertainty; future platform contraction only'}
 (a.OUT/'low_rating_comparison.json').write_text(json.dumps(result,indent=2));print(result)
