"""Aggregate-only workbook for the new transaction and time-outcome study."""
from pathlib import Path
import json,pandas as pd
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs'
if __name__=='__main__':
 files={'模型比较':'model_metrics.csv','复核预算':'review_budget.csv','后时点核对':'later_anchor_check.csv','敏感性检查':'sensitivity_checks.csv','描述分析':'descriptive_stats.csv','时间纠错前历史结果':'initial_metrics_before_timestamp_audit.csv'}
 with pd.ExcelWriter(OUT/'分析结果汇总.xlsx',engine='openpyxl') as w:
  pd.DataFrame({'说明':['真实公开批准订单商品金额，不是银行结算流水','未来90天平台销售额收缩，不是停业或信用违约','主测试2018-03-31，更晚核对2018-04-30；商户与未来窗口有重叠','公开信息相对交易基线增量区间包含0；不能证明稳定改善','更晚核对使用相同固定模型，未重训主测试标签','纠错前结果仅用于过程审计，当前报告使用剔除时间异常后的结果']}).to_excel(w,sheet_name='阅读说明',index=False)
  for sheet,file in files.items():pd.read_csv(OUT/file).to_excel(w,sheet_name=sheet,index=False)
  for sheet,file in [('数据审计','data_audit.json'),('主增量区间','analysis_summary.json'),('低评分对照','low_rating_comparison.json'),('后时点说明','later_anchor_notes.json')]:
   content=json.loads((OUT/file).read_text());pd.DataFrame([{'字段':k,'值':json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v} for k,v in content.items()]).to_excel(w,sheet_name=sheet,index=False)
  for worksheet in w.book.worksheets:
   worksheet.freeze_panes='A2';worksheet.auto_filter.ref=worksheet.dimensions
   for col in worksheet.columns:worksheet.column_dimensions[col[0].column_letter].width=min(70,max(14,max(len(str(c.value or '')) for c in col)+2))
 print('Aggregate workbook generated')
