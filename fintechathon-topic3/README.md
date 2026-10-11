> 完整报告、Excel、图表和代码可下载本目录的 `analysis-package.zip`。原始数据和逐商户记录不上传GitHub。

# FinTechathon 赛题三：公开餐饮商户数据分析

已实际完成：固定公开子集下载及SHA256校验、字段与样本核对、清洗、12项指标、六个模型、商户级独立测试、1500次配对Bootstrap、10%/20%/30%复核预算验证、敏感性检查和中文结果底稿。

**尚未完成：当前官方数据条款及镜像再分发许可核实。** 网络配置草稿已添加Yelp官网等必要域名，但保存草稿不代表当前代理已放行。参赛发布前需核实当前官方条款与该教育比赛用途；历史学术协议不能代替当前许可。原始数据、具名商户及评论者记录不作为提交材料。

## 查看结果

- `outputs/阶段分析报告.md`：含真实数值、全部模型结果、图表和结论边界的中文分析底稿，尚非最终参赛PDF。
- `outputs/分析结果汇总.xlsx`：数据审计、描述分析、模型比较、复核预算、敏感性检查、指标说明和区间。
- `outputs/merchant_features.csv`：本地复现后生成，含674家匿名商户的12项指标及审计字段；未上传GitHub。
- `outputs/sample_split.csv`：本地复现后生成，未上传GitHub；记录固定划分。
- `outputs/model_metrics.csv`、`review_budget.csv`、`analysis_summary.json`：独立测试及不确定性结果。
- `outputs/test_predictions.csv`：本地复现后生成，未上传GitHub；支持核对复核名单。
- `outputs/fig01_*.png`至`fig05_*.png`：五张可用于报告的图。
- `sources/data_manifest.json`：准确来源、固定Git提交、文件哈希和许可核实状态。

## 主要发现

原始样本3164家商户、91057条评论；1361家餐饮商户中筛选674家，123家记录为停止营业。评论截至2017-07-26，营业状态采集时间未说明。验证集选择的增强逻辑回归在测试集的ROC-AUC为0.577、AP为0.220；相对质量基线AP增益0.009，95%区间包含0。

预设增强树模型测试ROC-AUC为0.631、AP为0.319，约10%复核预算命中7/14家停止营业商户，Lift点估计2.70；95%区间约0.96—3.75，仍包含1。该模型没有因为测试表现较高而被回头改为主模型。数据存在明显年代混杂，不能宣称提前预测停业、信用违约预测或2026年深圳适用性。

## 复现

在现有目录中运行，不需要新建Git worktree，也不修改原招股书项目：

```bash
cd /workspace/prospectus--project/fintechathon-topic3
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-tested.txt
.venv/bin/python scripts/download_data.py
.venv/bin/python scripts/prepare.py
OMP_NUM_THREADS=2 MPLCONFIGDIR="$PWD/.mpl-cache" .venv/bin/python scripts/analyze.py
.venv/bin/python scripts/write_report.py
.venv/bin/python scripts/package_results.py
.venv/bin/python scripts/validate_outputs.py
```

Python 3.12已验证。输入存在时下载脚本仅校验，不重复下载；哈希不匹配时会停止并保留原文件。新下载以TLS正常验证的HTTPS请求获取，校验成功后才启用。仅使用既有公开文件，没有采集平台实时网页、要求账户凭据或上传数据。

分析随机种子为20261011。窗口锚点为各商户最后评论日期，不能称为同一观察时点的前瞻设计。所有缺失填补和标准化只在拟合数据执行；调参和主模型选择只使用验证集。测试结果保留全部六模型，原始数据及完整评论文本不写入报告或Excel。

下载涉及第三方历史子集，应保留来源与历史局限的说明。数据集版本、标签采集日期和当前使用许可未证实部分均在清单及报告中明确标注。
