# Week 10 盲测执行清单

## 0. 前置条件

- [ ] 两家事件级 Gold 已冻结（`gold/annotation_status.md` 两行均为 `frozen`）；
- [ ] Gold 变更日志与 hash 已记录；
- [ ] Week 8/9 dev 基线（全样本 + 分公司 P/R/F1）已保存；
- [ ] 本包已提交，冻结 hash 与 commit 一致。

## 1. 输入变更（唯一允许的代码改动）

```bash
# 在独立 commit 中，只增加：
# run_md_pipeline.py  COMPANIES 增加 ("688795", "摩尔线程"), ("688802", "沐曦股份")
# markdown_source.py  MD_FILES 增加对应映射
```

提交前校验：

```bash
git diff 9ff43a5d3c92150865a3a89ce951b13db3e55bb0 -- week6/pipeline/run_md_pipeline.py | rg 'PATTERNS|^\+\s*r\('   # 应无输出
```

## 2. 只读运行

```bash
cd /Users/zhaobingqing/Documents/Codex/2026-08-07/ni/work/prospectus--project-shallow
unset DB_HOST DB_NAME DB_USER DB_PASSWORD DEEPSEEK_API_KEY
cd week6
python3 pipeline/run_md_pipeline.py
cd ..
```

验收：
- 终端出现“入库跳过(数据库不可用)”且不写数据库；
- 输出目录出现 688795、688802 的 JSONL；
- 记录候选数、运行时间、环境与结果目录 hash。

## 3. 评价

- [ ] 按 `matching_spec.md` 实现或复用 Week 8 事件级评价器；
- [ ] 输出全样本、分公司、分事件类型 P/R/F1；
- [ ] 输出字段级一致率（金额、估值、轮次、日期）；
- [ ] 每个 FP/FN 可回 Auto 行、Gold 行、原文页码。

## 4. 报告与判定

- [ ] 填写 `week10/blind_test_report.md`（含输入 hash、运行 commit、Gold 版本、三层指标、字段一致率）；
- [ ] 与 dev 基线对比，按第 7 节预注册规则给出“通过 / 过拟合嫌疑 / 单家崩坏”结论；
- [ ] 结论写入 decision log，之后才允许修改规则。

## 5. 解锁

- [ ] 盲测报告定稿；
- [ ] decision log 记录解锁时间与后续 Week 9/10 修复优先级；
- [ ] 规则修改必须带失败测试并报告 P/R/F1 前后变化。
