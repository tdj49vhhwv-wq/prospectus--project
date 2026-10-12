# 赛题三最新提交稿：真实订单与未来经营收缩

**推荐阅读本目录新数据版，原`fintechathon-topic3`餐饮营业状态研究仅保留为历史稿。**

- [285-赛题3.pdf](report/285-赛题3.pdf)：封面1页、正文8页（含摘要）、参考文献1页。
- [Word可编辑稿](report/报告可编辑稿.docx)、[中文正文](report/报告正文.md)、[五张图表](report/figures/)。
- [三个不足的改善说明](report/改善说明与边界.md)、[实际排版检查](report/排版检查结果.json)。
- `outputs/分析结果汇总.xlsx`及CSV/JSON：全部六模型、配对区间、复核预算、后时点核对与敏感性结果。
- `analysis-package.zip`：完整成果与复现代码；`交付文件清单.json`提供逐文件SHA256。

## 数据与许可

取自数据提供方官方仓库：https://github.com/olist/work-at-olist-data ，固定提交d9e49802f3e92d09ee94ab9ccc5e457f207a8959。官方README称关系表直接抽样自交易系统；仓库MIT许可证及版权原文保存在sources/LICENSE。四个输入文件哈希和地址在sources/data_manifest.json。原始消费者记录、评论、逐商户特征和预测仅本地保存，不上传GitHub或成果ZIP。

原始99,441笔订单、112,650条商品明细、99,224条评价、3,095名卖家。金额是批准订单的商品价格之和，**不是银行收款、结算净现金流或完整经营额**。公开评价和履约与交易同源，并非已经验证了独立外部平台对真实银行流水的增益。小微企业规模未知。

## 研究与结果

主标签：未来90天平台商品销售额≤过去90天的50%，代表未来平台经营收缩代理，**不是停业或信用违约**。使用训练2017-06-30、09-30，验证2017-12-31，主测试2018-03-31，更晚核对2018-04-30。全部特征按观察日前批准、回答和配送事件重建；排除61笔配送时序异常的时间和20条评价时序异常，保留初轮结果供审计。

主测试581家、229家未来收缩。验证T基线AP选择LR家族，固定算法检验TQL增量：基线AP=0.5476，增强AP=0.5580，增量0.0103，配对95%区间[-0.0070,0.0272]。约10%预算复核59家，交易基线与增强均命中42家，低评分27家；相对低评分命中率差25.42个百分点，固定模型配对区间[11.86,42.37]个百分点。更晚核对615家，增强AP增量约0.005，区间仍含0。

结论：交易排序优于仅按低评分，但**额外公开信息未显示稳定的评分增量**，不能把交易的优势归于评价。产品优先采用交易基线，公开评价／履约作调查解释；本研究没有试图根据测试分数改模型、改标签来制造显著提升。

## 复现

Python3.12环境依赖见requirements-tested.txt。生成PDF需要系统XeLaTeX及fontspec、geometry、caption、titlesec、booktabs、array、float、indentfirst、fancyhdr等宏包。脚本从固定版本下载并校验Fandol字体。

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-tested.txt
.venv/bin/python scripts/download_dataset.py
OMP_NUM_THREADS=2 .venv/bin/python scripts/analyze_transactions.py --data-dir data
OMP_NUM_THREADS=2 .venv/bin/python scripts/check_later_anchor.py --data-dir data
.venv/bin/python scripts/audit_budget_pairs.py
.venv/bin/python scripts/package_results.py
MPLCONFIGDIR="$PWD/.mpl-cache" .venv/bin/python scripts/build_report.py
.venv/bin/python scripts/validate_submission.py
.venv/bin/python scripts/bundle_deliverables.py
```

更晚核对与主测试商户和未来窗口重叠，不是独立复验。更晚核对模型与原主测试模型预测一致性经过验证，未用主测试标签重训。Bootstrap只描述固定模型的测试样本不确定性，不覆盖拟合和调参。

当前PDF采用嵌入Fandol宋体，实测10.5磅、15.75磅行距、0段间距、21磅首行缩进。Word正文设为宋体；若组织方要求具体中易宋体，需在对应字体环境重新导出并复查正文≤8页。封面为285小组，姓名和学校不写入提交稿。

**初赛只提交新数据版这一份PDF，不交ZIP、Word、Excel、代码或历史稿。**
