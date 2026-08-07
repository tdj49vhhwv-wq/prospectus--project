# Week 8 首版事件级 P/R/F1 基线

**赵秉清 | 2026-08-07**

---

## 一、结论

首版事件级基线：**全样本 Precision = 6.90%，Recall = 8.89%，F1 = 7.77%**。8 家公司中只有三协电机达到 Recall=100%（但 Precision 仅 21.43%），其余公司 P/R 均远低于 Week 10 门槛（事件级 P/R ≥ 90%）。

这说明 Week 7 的判断仍然成立：当前 Markdown 候选管线“过度召回、误报严重”，距离可信基线还有大量工作；也说明**不能把候选条数当准确率**。

## 二、口径与命令

```bash
# 候选层（只读，不连库）
cd week6 && python3 pipeline/run_md_pipeline.py

# 事件级评价
python3 week8/evaluate_events.py \
  --gold data/gold_standard \
  --auto week6/auto_output_md \
  --out week8/event_eval
```

输入与输出 hash：

```text
data/gold_standard/subscription_flow_gold.jsonl  46a6c8637cad7af3580064850f1b8215fb00d49a5ffd6c7c9d4d67d904ea3fc0
data/gold_standard/share_transfer_flow_gold.jsonl 5087a6c079a1a7b17ba47fa2e1f2568ef4490db397a6245eabaf53f0fd48c043
data/gold_standard/equity_snapshot_gold.jsonl    d04df8ae558ab8272394b40fbf123e50030f5d73aec244a9bffffc36cadde2b7
week6/auto_output_md/001282_subscription_flow.jsonl d38c8b2d7e980bd7a395b64bc8a905c07eb887b560e975cbb77579402403352a
week6/auto_output_md/301563_subscription_flow.jsonl 023d582b9c37135a4dec60f371d0c5b99c2042603bfed0e1bc8c8639d95f2aa4
week6/auto_output_md/301581_subscription_flow.jsonl 1cf428554d6026313f1f0db04cdde5420350f02a9ede70653a76358477465a96
week6/auto_output_md/603418_subscription_flow.jsonl d6f5ed0dd7525a93c6238f8f7d619f719a7e45d932a27595bb541dd31ca32779
week6/auto_output_md/688758_subscription_flow.jsonl f34bc1151b8356c9eec3f7b2b9b5bc9e2bee510e79c9494162299e52fb3a846c
week6/auto_output_md/688775_subscription_flow.jsonl 1b9e33cc9935cfb08671f84e888bc57ca7341a38ea9a674b9cae06ce7ae9dd9c
week6/auto_output_md/920100_subscription_flow.jsonl ccda08d0e0249256ab3471c51568dfd9db0b89f6830e7413783caa6d6da32d54
week6/auto_output_md/920116_subscription_flow.jsonl 01b51bd5ff9883f6a152917d19ed16e07650c9a0448719073087c17b16ab0a55
```

Gold 事件 45 条（subscription 38 + share transfer 7），Auto 事件 58 条（候选行按 `(公司, 日期, 类型)` 合并），其中 Auto 缺日期事件 11 条。

## 三、全样本结果

| 指标 | 值 |
|------|------|
| TP | 4 |
| FP | 54 |
| FN | 41 |
| Precision | 6.90% |
| Recall | 8.89% |
| F1 | 7.77% |

## 四、分公司结果

| 公司 | 代码 | TP | FP | FN | P | R | F1 |
|------|------|---:|---:|---:|---:|---:|---:|
| 三联锻造 | 001282 | 0 | 7 | 5 | 0.00% | 0.00% | N/A |
| 云汉芯城 | 301563 | 0 | 4 | 8 | 0.00% | 0.00% | N/A |
| 黄山谷捷 | 301581 | 0 | 8 | 8 | 0.00% | 0.00% | N/A |
| 友升股份 | 603418 | 1 | 5 | 3 | 16.67% | 25.00% | 20.00% |
| 赛分科技 | 688758 | 0 | 9 | 6 | 0.00% | 0.00% | N/A |
| 影石创新 | 688775 | 0 | 3 | 7 | 0.00% | 0.00% | N/A |
| 三协电机 | 920100 | 3 | 11 | 0 | 21.43% | 100.00% | 35.29% |
| 星图测控 | 920116 | 0 | 7 | 4 | 0.00% | 0.00% | N/A |

## 五、分事件类型结果

| 类型 | 名称 | TP | FP | FN | P | R | F1 |
|------|------|---:|---:|---:|---:|---:|---:|
| A | 增资 | 2 | 17 | 20 | 10.53% | 9.09% | 9.76% |
| B | 股改/整体变更 | 0 | 2 | 6 | 0.00% | 0.00% | N/A |
| C | 增资+转让（复合） | 0 | 0 | 5 | N/A | 0.00% | N/A |
| D | 股权转让 | 0 | 3 | 7 | 0.00% | 0.00% | N/A |
| E | 设立 | 2 | 30 | 1 | 6.25% | 66.67% | 11.43% |
| F | 资本公积转增 | 0 | 1 | 0 | 0.00% | N/A | N/A |
| G | 吸收合并 | 0 | 1 | 1 | 0.00% | 0.00% | N/A |
| J | 员工激励 | 0 | 0 | 1 | N/A | 0.00% | N/A |

## 六、主要问题（首版，未做完整误差分类）

1. **设立类 FP 集中**：E 类 FP=30，规则对“成立于/成立日期”过度匹配，含大量非融资主体文本；
2. **复合事件全部漏掉**：C 类 FN=5，规则不产出“增资及股权转让”复合类型；
3. **股权转让全部漏掉**：D 类 FN=7、FP=3，转让模式未命中 Gold 转让事件；
4. **Auto 缺日期事件 11 条**：无法参与匹配，按预注册口径全部计 FP；
5. **增资召回极低**：A 类 R=9.09%，Gold 中多轮增资的金额/股数表述未被规则命中。

## 七、Gold 版本说明

本基线使用 `data/gold_standard` 现有文件（v1.0 口径，124 + 7 条流量行）。Gold v1.1 定义草案与 7 条待迁移记录见 `gold_definition_v1.1.md`、`gold_change_log.csv`；老师确认后需重算基线。

## 八、下一步

- 8/8：FP Top 10 / FN Top 10 误差分类，修第一批明显误报（设立过度匹配、缺日期候选）；
- 8/9：全量复跑，输出 `week8_baseline_report.md` 终稿；
- 同步开发投资人明细级评价器。
