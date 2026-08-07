# Week 8 目录说明

| 文件 | 内容 |
|------|------|
| `week8_plan.md` | 周任务书（含盲测范围决策） |
| `matching_spec.md` | 事件级匹配规范（预注册） |
| `evaluate_events.py` | 事件级 Auto-vs-Gold 评价器 |
| `event_eval/event_eval_summary.json` | 首版评价汇总 |
| `event_eval/event_eval_details.csv` | 每条 Gold/Auto 事件匹配明细与证据 |
| `classify_errors.py` | FP/FN 逐条误差分类脚本 |
| `error_classification.csv` | 93 条 FP/FN 分类明细 |
| `error_analysis_week8.md` | 误差分类与第一批修复报告 |
| `gold_definition_v1.1.md` | Gold v1.1 定义草案 |
| `gold_change_log.csv` | Gold 变更日志（7 条拟迁移） |
| `baseline_report_20260807.md` | 首版 P/R/F1 基线报告 |
| `decision_log_20260807.md` | 8/7 决策与执行记录 |
| `manual_review_queue_20260807.md` / `.csv` | VIE 轮次、Gold 口径、流程图跨块的人工/LLM 复核队列 |
| `tests/test_evaluate_events.py` | 评价器单测（本机无 pytest 时用内联 runner） |
| `tests/test_fixes_20260807.py` | 第一批修复回归测试 |

复现：

```bash
cd week6 && python3 pipeline/run_md_pipeline.py
cd .. && python3 week8/evaluate_events.py
```

评价器默认读取 `week6/auto_output_md/validated/`（验证层）；候选层指标用
`python3 week8/evaluate_events.py --auto week6/auto_output_md/candidate --out week8/event_eval_candidate`。
