"""Fixed-model later anchor check. No new tuning or test-driven model selection."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
import analyze_transactions as a

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--data-dir',type=Path,required=True);args=p.parse_args()
 root=a.ROOT;mainout=a.OUT;summary=json.loads((mainout/'analysis_summary.json').read_text());original=pd.read_csv(mainout/'seller_panel.csv');oldpred=pd.read_csv(mainout/'test_predictions.csv')
 import tempfile
 a.OUT=Path(tempfile.mkdtemp(prefix='fintech-later-'));a.OUT.mkdir(exist_ok=True);a.DESIGN={**a.DESIGN,'train':[],'validation':[],'test':['2018-04-30']}
 with threadpool_limits(limits=2):
  later=a.prepare(args.data_dir);fit=original[original.stage!='test'];first=original[original.stage=='test'].reset_index(drop=True);result=[];sc={}
  for name in [summary['baseline'],summary['primary']]:
   family,set_name=name.split('_');par=summary['parameters'][name];columns=a.SETS[set_name]
   if family=='LR':model=make_pipeline(SimpleImputer(strategy='median',add_indicator=True),StandardScaler(),LogisticRegression(**par,max_iter=3000,random_state=a.SEED))
   else:model=make_pipeline(SimpleImputer(strategy='median',add_indicator=True),HistGradientBoostingClassifier(**par,max_iter=150,learning_rate=.05,min_samples_leaf=20,early_stopping=False,random_state=a.SEED))
   model.fit(fit[columns],fit.label)
   np.testing.assert_allclose(model.predict_proba(first[columns])[:,1],oldpred[name],rtol=1e-10,atol=1e-10)
   score=model.predict_proba(later[columns])[:,1];sc[name]=score
   result.append(dict(model=name,anchor='2018-04-30',n=len(later),positive=int(later.label.sum()),**a.scores(later.label,score)))
  rng=np.random.default_rng(a.SEED);d=[];y=later.label.to_numpy()
  for _ in range(2000):
   ix=rng.integers(0,len(y),len(y));yy=y[ix]
   if np.unique(yy).size==2:d.append(a.average_precision_score(yy,sc[summary['primary']][ix])-a.average_precision_score(yy,sc[summary['baseline']][ix]))
 pd.DataFrame(result).to_csv(mainout/'later_anchor_check.csv',index=False)
 note={'same_fixed_models_verified':True,'primary_minus_baseline_ap_ci95':a.interval(d),'later_cohort':json.loads((a.OUT/'data_audit.json').read_text())['cohort_counts'],'limitations':'Overlapping sellers and future windows; later-anchor check is not independent replication or model selection. No refitting with primary-test labels.'}
 (mainout/'later_anchor_notes.json').write_text(json.dumps(note,indent=2));print(pd.DataFrame(result).to_string(index=False));print(note)
