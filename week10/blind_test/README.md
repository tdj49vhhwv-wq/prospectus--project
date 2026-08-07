# 盲测方案：2 家事件级 Gold 盲测

**决策日期**：2026-08-07
**执行周**：Week 10（2026-08-17—2026-08-23）
**范围**：688795 摩尔线程 + 688802 沐曦股份
**Gold 层级**：事件级（不标投资人明细级，不推导公司级结论）
**规则状态**：冻结（见 `freeze/rules_freeze_manifest.md`）

---

## 一、为什么是这两家

1. 两家都是 2025 年科创板申报公司，2020 年前后成立，融资历史密集，与现有 8 家开发公司在事件类型和章节结构上同构；
2. 摩尔线程、沐曦都是多轮 PE/VC 增资、股权转让、员工平台、股改齐备的公司，最能检验现有 8 家正则规则是否过拟合；
3. `week1/review/` 已有完整 Markdown 源（688795 为 39,084 行，688802 为 41,533 行），Gold 标注不依赖 PDF。

选 1 家只能看出“崩没崩”，看不出跨公司稳定性；选全部 11 家会绕过 Week 10 闸门，变成继续堆条数。2 家是本轮推荐范围。

## 二、为什么必须标 Gold

没有 Gold 就无法计算 Precision / Recall / F1，也就谈不上验证泛化。本次盲测对两家公司逐条人工确认事件级 Gold，然后只读运行冻结规则，得到全样本、分公司、分事件类型的 P/R/F1。

- Recall：规则能否找全两家公司的融资/股权事件；
- Precision：找到的事件是否真实、类型和日期是否正确。

投资人明细级（谁投、多少钱、多少股）本次不进入盲测 P/R/F1；字段级正确率单独报告，见 `matching_spec.md`。

## 三、执行顺序（冻结协议）

1. **Gold 先行**：按 `gold/` 的规范标注两家事件级 Gold，逐条人工确认后冻结为 Gold v1.0，并记录变更日志与 hash；
2. **规则冻结**：以 commit `9ff43a5` 的 PATTERNS 为基线；Week 10 运行只允许新增 688795/688802 的公司清单与 MD 文件映射，禁止修改任何正则或事件分类；
3. **只读运行**：不连数据库、不调 LLM，输出 Auto 事件候选；
4. **评价**：按 `matching_spec.md` 预注册口径计算 P/R/F1；
5. **判定**：与 Week 8/9 dev 基线对比，按预注册规则判定是否过拟合；
6. **解锁**：在 decision log 记录后才允许按 Week 9/10 计划修改规则。

## 四、Gold 范围与字段

- 融资历史事件流（P/R/F1 主口径）：E 设立、A 增资、B 股改、C 复合、D 股权转让、F 资本公积转增、G 吸收合并、H VIE、I IPO、J 员工激励；字段规范见 `gold/gold_event_level_schema.md`；
- IPO 进程事件流（辅助层，不参与本次 P/R/F1）：申报、受理、问询、上会、注册、发行等状态事件；字段规范见 `gold/gold_ipo_status_schema.md`；
- 每条 Gold 必须带逐字证据（`evidence_text`）与来源页码，可回原文核对。

## 五、文件地图

| 文件 | 内容 |
|------|------|
| `gold/gold_event_level_schema.md` | 融资事件级 Gold 字段规范与标注规则 |
| `gold/gold_ipo_status_schema.md` | IPO 进程事件流字段规范 |
| `gold/annotation_guide.md` | 标注指引、原文定位、日期/金额/估值规则 |
| `gold/annotation_status.md` | 两家 Gold 标注进度状态表 |
| `gold/gold_event_level_template.csv` | 融资事件级标注模板 |
| `gold/gold_ipo_status_template.csv` | IPO 进程标注模板 |
| `freeze/rules_freeze_manifest.md` / `.json` | 规则冻结清单与文件 hash |
| `matching_spec.md` | 预注册匹配口径与指标定义 |
| `execution_checklist_week10.md` | Week 10 执行清单 |

## 六、Week 8/9 边界

- 本包只钉死盲测范围，不改变 Week 8 本周唯一目标（评价器 + 可信基线）；
- Week 10 闸门不变：8 家事件级 Precision、Recall ≥ 90% 且投资人明细级 F1 ≥ 80% 仍是主门槛，2 家盲测是过拟合证据，不是替代门槛；
- Gold 标注可以安排在 Week 8 空闲时间，但不能挤占 Week 8 评价器开发时间。

## 七、风险与已知限制

- 两家合计约 25—35 个事件，统计功效有限；盲测结论以“崩没崩、是否明显掉点”为主，不宣称统计显著；
- 两家同属 AI 芯片赛道，若以后要扩样本，仍需覆盖其他板块；
- 招股书章节结构差异（VIE、员工平台、报告期外历史）可能暴露规则盲区，这正是盲测的目的。
