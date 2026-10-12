"""Locked chronological evaluation of real order GMV and public reviews.

GMV is approved-order merchandise value, not bank receipts. The target is future
platform-sales contraction, not closure or credit default. Raw rows stay local.
"""
import argparse, hashlib, json, math
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs'; SEED=20261012
T=['gmv_180','orders_180','gmv_90','orders_90','gmv_growth_log','order_growth_log','monthly_gmv_cv','mean_order_value','days_since_order']
Q=['review_mean','review_low_share','review_std','review_change','review_coverage']
L=['known_late_share','known_delivery_days','undelivered_share']
SETS={'T':T,'TQ':T+Q,'TQL':T+Q+L}
DESIGN={'seed':SEED,'train':['2017-06-30','2017-09-30'],'validation':['2017-12-31'],'test':['2018-03-31'],
 'feature_days':180,'recent_days':90,'horizon_days':90,'target':'future approved-order merchandise GMV <= 50% of past 90-day GMV',
 'eligibility':'at least 10 approved orders in past 180 days, at least 3 in past 90 days; first approved order at least 90 days before cutoff',
 'primary_family':'highest validation AP on T baseline; same family for baseline and TQL enhanced comparison',
 'budget':.1,'bootstrap_repetitions':2000,'scope':'historical chronological platform-contraction proxy, not prospective deployed experiment or credit risk',
 'no_test_selection':True,'reviews':'only single-seller orders; review_answer_timestamp strictly before cutoff; latest available response per order',
 'delivery':'only actual delivery timestamps before cutoff; undelivered includes deliveries after cutoff; current final order_status excluded',
 'raw_price_version_limit':'no point-in-time item-price history or cancellation/refund history; retrospective event-time reconstruction'}

def interval(x):return [float(v) for v in np.percentile(x,[2.5,97.5])]
def budget(y,p):
 k=math.ceil(len(y)*DESIGN['budget']);ix=np.argsort(-np.array(p),kind='stable')[:k];h=int(np.array(y)[ix].sum())
 return dict(reviewed=k,captured=h,precision=h/k,recall=h/int(np.sum(y)),lift=h/k/float(np.mean(y)))
def scores(y,p):return dict(roc_auc=float(roc_auc_score(y,p)),ap=float(average_precision_score(y,p)),brier=float(brier_score_loss(y,p)),**budget(y,p))

def prepare(data):
 orders=pd.read_csv(data/'olist_orders_dataset.csv');items=pd.read_csv(data/'olist_order_items_dataset.csv');reviews=pd.read_csv(data/'olist_order_reviews_dataset.csv');sellers=pd.read_csv(data/'olist_sellers_dataset.csv')
 assert orders.order_id.is_unique and sellers.seller_id.is_unique
 assert not items.duplicated(['order_id','order_item_id']).any()
 audit={'orders_raw':len(orders),'items_raw':len(items),'reviews_raw':len(reviews),'sellers_raw':len(sellers)}
 for c in [c for c in orders if c.endswith('date') or c.endswith('timestamp') or c=='order_approved_at']:orders[c]=pd.to_datetime(orders[c],errors='coerce')
 reviews.review_answer_timestamp=pd.to_datetime(reviews.review_answer_timestamp,errors='coerce')
 assert items.price.notna().all() and (items.price>=0).all()
 audit['orders_missing_approval']=int(orders.order_approved_at.isna().sum())
 invalid_delivery=orders.order_delivered_customer_date<orders.order_approved_at
 audit['delivery_before_approval']=int(invalid_delivery.sum());orders.loc[invalid_delivery,'order_delivered_customer_date']=pd.NaT
 review_timing=reviews.merge(orders[['order_id','order_approved_at']],on='order_id',how='left',validate='many_to_one')
 invalid_answer=review_timing.review_answer_timestamp<review_timing.order_approved_at
 audit['review_before_approval_removed']=int(invalid_answer.sum());reviews=reviews.loc[~invalid_answer.to_numpy()].copy()
 audit['items_unmatched_orders']=int((~items.order_id.isin(orders.order_id)).sum());assert audit['items_unmatched_orders']==0
 tx=items.groupby(['seller_id','order_id'],as_index=False).agg(amount=('price','sum'))
 tx=tx.merge(orders[['order_id','order_approved_at','order_delivered_customer_date','order_estimated_delivery_date']],on='order_id',validate='many_to_one')
 tx=tx[tx.order_approved_at.notna()].copy()
 tx=tx.merge(sellers[['seller_id','seller_state']],on='seller_id',validate='many_to_one')
 assert tx.seller_state.notna().all()
 audit.update(approved_seller_order_pairs=len(tx),approved_order_start=str(tx.order_approved_at.min()),approved_order_end=str(tx.order_approved_at.max()),multi_seller_orders=int((items.groupby('order_id').seller_id.nunique()>1).sum()),review_invalid_score=int((~reviews.review_score.between(1,5)).sum()),review_missing_answer=int(reviews.review_answer_timestamp.isna().sum()))
 singles=items.groupby('order_id').seller_id.nunique();singles=singles[singles==1].index
 reviews=reviews[reviews.order_id.isin(singles)&reviews.review_score.between(1,5)&reviews.review_answer_timestamp.notna()].copy()
 rows=[];counts=[]
 for stage,dates in [(k,DESIGN[k]) for k in ['train','validation','test']]:
  for date in dates:
   cutoff=pd.Timestamp(date)+pd.Timedelta(days=1); future_end=cutoff+pd.Timedelta(days=90)
   assert future_end<=tx.order_approved_at.max(), 'Incomplete future observation horizon'
   eligible_reviews=reviews[reviews.review_answer_timestamp<cutoff].sort_values(['review_answer_timestamp','review_id']).drop_duplicates('order_id',keep='last')
   rv=eligible_reviews[['order_id','review_score']]
   observable=tx[tx.order_approved_at<cutoff]
   active_count=0;kept=0
   for seller,g in tx.groupby('seller_id',sort=True):
    past=g[(g.order_approved_at<cutoff)&(g.order_approved_at>=cutoff-pd.Timedelta(days=180))].copy()
    if not len(past):continue
    active_count+=1
    recent=past[past.order_approved_at>=cutoff-pd.Timedelta(days=90)];prev=past[past.order_approved_at<cutoff-pd.Timedelta(days=90)]
    first=g.loc[g.order_approved_at<cutoff,'order_approved_at'].min()
    if len(past)<10 or len(recent)<3 or first>cutoff-pd.Timedelta(days=90):continue
    kept+=1;g90=float(recent.amount.sum());previous=float(prev.amount.sum())
    age=(cutoff-past.order_approved_at).dt.total_seconds()/86400
    bins=np.minimum((age//30).astype(int),5);monthly=past.amount.groupby(bins).sum().reindex(range(6),fill_value=0).to_numpy()
    r=past.merge(rv,on='order_id',how='left',validate='one_to_one');rr=r[r.order_approved_at>=cutoff-pd.Timedelta(days=90)].review_score.dropna();rp=r[r.order_approved_at<cutoff-pd.Timedelta(days=90)].review_score.dropna();allr=r.review_score.dropna()
    delivered=past.order_delivered_customer_date.notna()&(past.order_delivered_customer_date<cutoff)
    known=past[delivered];late=(known.order_delivered_customer_date>known.order_estimated_delivery_date).mean() if len(known) else np.nan
    days=(known.order_delivered_customer_date-known.order_approved_at).dt.total_seconds()/86400
    future=float(g.loc[(g.order_approved_at>=cutoff)&(g.order_approved_at<future_end),'amount'].sum())
    row=dict(seller_id=hashlib.sha256(('fintechathon:'+seller).encode()).hexdigest()[:16],stage=stage,anchor=date,state=g.seller_state.iloc[0],past_gmv=g90,future_gmv=future,contraction_ratio=future/g90,
     label=int(future<=.5*g90),gmv_180=float(past.amount.sum()),orders_180=len(past),gmv_90=g90,orders_90=len(recent),gmv_growth_log=float(np.log1p(g90)-np.log1p(previous)),order_growth_log=float(np.log1p(len(recent))-np.log1p(len(prev))),monthly_gmv_cv=float(monthly.std()/monthly.mean()),mean_order_value=float(past.amount.mean()),days_since_order=float((cutoff-past.order_approved_at.max()).total_seconds()/86400),review_mean=float(allr.mean()),review_low_share=float((allr<=2).mean()) if len(allr) else np.nan,review_std=float(allr.std(ddof=0)),review_change=float(rr.mean()-rp.mean()) if len(rr) and len(rp) else np.nan,review_coverage=len(allr)/len(past),known_late_share=float(late),known_delivery_days=float(days.mean()),undelivered_share=float(1-delivered.mean()))
    rows.append(row)
   counts.append(dict(stage=stage,anchor=date,active_sellers=active_count,eligible=kept))
 panel=pd.DataFrame(rows);assert not panel.duplicated(['seller_id','anchor']).any()
 panel.to_csv(OUT/'seller_panel.csv',index=False)
 audit['cohort_counts']=counts;audit['panel_rows']=len(panel);audit['split_summary']=panel.groupby(['stage','anchor']).agg(sellers=('seller_id','size'),positive=('label','sum'),positive_rate=('label','mean')).reset_index().to_dict('records')
 audit['unique_sellers']=panel.seller_id.nunique();audit['test_review_missing']=int(panel.loc[panel.stage=='test','review_mean'].isna().sum())
 (OUT/'data_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2));print(json.dumps(audit,indent=2),flush=True)
 return panel

def run(panel):
 train=panel[panel.stage=='train'];valid=panel[panel.stage=='validation'];test=panel[panel.stage=='test'].reset_index(drop=True); fit=panel[panel.stage!='test']
 params={};valid_ap={};models={};pred=test[['seller_id','label','anchor','state','past_gmv','future_gmv','contraction_ratio','orders_180','review_coverage']].copy()
 for family in ['LR','HGB']:
  for set_name,columns in SETS.items():
   choices=[]
   if family=='LR':
    for c in [.1,1.,10.]:choices.append(({'C':c},make_pipeline(SimpleImputer(strategy='median',add_indicator=True),StandardScaler(),LogisticRegression(C=c,max_iter=3000,random_state=SEED))))
   else:
    for leaf in [7,15]:
     for l2 in [1.,5.]:choices.append(({'max_leaf_nodes':leaf,'l2_regularization':l2},make_pipeline(SimpleImputer(strategy='median',add_indicator=True),HistGradientBoostingClassifier(max_iter=150,learning_rate=.05,max_leaf_nodes=leaf,l2_regularization=l2,min_samples_leaf=20,early_stopping=False,random_state=SEED))))
   ranked=[]
   for par,model in choices:
    model.fit(train[columns],train.label);ap=average_precision_score(valid.label,model.predict_proba(valid[columns])[:,1]);ranked.append((float(ap),par,model))
   ranked.sort(key=lambda z:z[0],reverse=True);ap,par,chosen=ranked[0];name=family+'_'+set_name
   valid_ap[name]=ap;params[name]=par;model=clone(chosen);model.fit(fit[columns],fit.label);models[name]=model;pred[name]=model.predict_proba(test[columns])[:,1]
   print(name,'validation AP',ap,par,flush=True)
 family=max(['LR','HGB'],key=lambda f:valid_ap[f+'_T']);baseline=family+'_T';primary=family+'_TQL'
 pred['low_rating']=-test.review_mean.fillna(fit.review_mean.median()).to_numpy();pred.to_csv(OUT/'test_predictions.csv',index=False)
 metrics={name:{'validation_ap':valid_ap[name],**scores(pred.label,pred[name])} for name in models}
 pd.DataFrame(metrics).T.rename_axis('model').to_csv(OUT/'model_metrics.csv')
 y=pred.label.to_numpy();rng=np.random.default_rng(SEED);samples={m:{k:[] for k in ['ap','roc_auc','precision','lift']} for m in models};diff={k:[] for k in ['ap','roc_auc','precision']}
 for _ in range(DESIGN['bootstrap_repetitions']):
  ix=rng.integers(0,len(y),len(y));yy=y[ix]
  if np.unique(yy).size<2:continue
  for m in models:
   v=scores(yy,pred[m].to_numpy()[ix])
   for k in samples[m]:samples[m][k].append(v[k])
  for k in diff:diff[k].append(samples[primary][k][-1]-samples[baseline][k][-1])
 budgets=[]
 for name in ['low_rating',*models]:budgets.append({'strategy':name,**budget(y,pred[name])})
 k=math.ceil(len(y)*.1);budgets.append(dict(strategy='random_expected',reviewed=k,captured=k*float(y.mean()),precision=float(y.mean()),recall=k/len(y),lift=1))
 pd.DataFrame(budgets).to_csv(OUT/'review_budget.csv',index=False)
 sensitivity=[]
 masks={'all_test':np.ones(len(test),dtype=bool),'orders_at_least_20':test.orders_180>=20,'review_coverage_at_least_half':test.review_coverage>=.5,'state_SP':test.state=='SP','state_non_SP':test.state!='SP','unseen_sellers':~test.seller_id.isin(train.seller_id)}
 for group,mask in masks.items():
  if int(mask.sum())<20 or test.loc[mask,'label'].nunique()<2:continue
  for m in [baseline,primary]:sensitivity.append(dict(subset=group,model=m,n=int(mask.sum()),positive=int(test.loc[mask,'label'].sum()),**scores(test.loc[mask,'label'],pred.loc[mask,m])))
 for ratio in [.3,.7]:
  yy=(test.contraction_ratio<=ratio).astype(int)
  for m in [baseline,primary]:sensitivity.append(dict(subset=f'future_ratio_{ratio}',model=m,n=len(yy),positive=int(yy.sum()),**scores(yy,pred[m])))
 pd.DataFrame(sensitivity).to_csv(OUT/'sensitivity_checks.csv',index=False)
 training_constant=float(fit.label.mean());brier_const=brier_score_loss(y,np.full(len(y),training_constant))
 summary={'design':DESIGN,'selected_family':family,'primary':primary,'baseline':baseline,'parameters':params,'validation_ap':valid_ap,'test_n':len(y),'test_positive':int(y.sum()),'test_prevalence':float(y.mean()),'metrics':metrics,'confidence_intervals':{m:{key:interval(vals) for key,vals in d.items()} for m,d in samples.items()},'primary_minus_baseline':{key:interval(vals) for key,vals in diff.items()},'constant_brier':float(brier_const),'fitting_prevalence':training_constant,'uncertainty':'2000 paired seller-level percentile bootstrap; fixed fitted models; single test quarter; excludes training/tuning uncertainty', 'constraints':['GMV is not bank cash flow','Future contraction is not credit default or closure','Platform samples not full merchant sales','Seller size unknown','Public review and fulfillment modules from same provider, not independent external platforms','Snapshot price/refund/cancellation history unavailable','Historical overseas ecommerce, not current Shenzhen restaurant merchants']}
 (OUT/'analysis_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(pd.DataFrame(metrics).T.to_string(),flush=True);print('PRIMARY',primary,'DELTA CI',summary['primary_minus_baseline'],flush=True)
 desc=[]
 for c in T+Q+L:desc.append(dict(feature=c,normal_mean=test.loc[test.label==0,c].mean(),contraction_mean=test.loc[test.label==1,c].mean(),missing=int(test[c].isna().sum())))
 pd.DataFrame(desc).to_csv(OUT/'descriptive_stats.csv',index=False)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--data-dir',type=Path,required=True);args=p.parse_args();OUT.mkdir(exist_ok=True)
 (ROOT/'sources/locked_design.json').write_text(json.dumps(DESIGN,ensure_ascii=False,indent=2))
 with threadpool_limits(limits=2):run(prepare(args.data_dir))
