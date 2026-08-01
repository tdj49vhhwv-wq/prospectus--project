# Week 7 可复现性报告

**赵秉清 | 2026.08.01**

## 一、复现对象

- 对象：`week6/pipeline/run_md_pipeline.py` 的 Markdown 候选提取逻辑；
- 样本：8 家公司、9 个已纳入 Git 的 Markdown 文件；
- 当前基准提交：`ddcf1f8960f4bfdd5b7c6415a068a11bb6156de8`；
- 当前基准结果：325 个相关文本片段、645 条原始候选；
- 注意：本报告只复现候选生成，不连接数据库、不调用 LLM，也不等同于准确率评价。

## 二、运行环境

| 项目 | 值 |
|---|---|
| 操作系统 | Darwin 25.4.0 arm64 |
| Python | 3.9.6 |
| 输入文本 | `week1/review/*.md` |
| 核心代码 | `week6/pipeline/run_md_pipeline.py`、`markdown_source.py` |
| 网络/API | 不需要 |
| 数据库 | 不需要；只调用纯提取函数 |

为避免主程序写入 `auto_output_md` 或尝试连接数据库，复现时直接导入 `make_located_data()` 和 `extract_from_snippets()`，只在内存中统计。

## 三、复现命令

在仓库根目录运行：

```bash
for seed in 0 1 2 3; do
  PYTHONHASHSEED="$seed" python3 - <<'PY'
import sys
sys.path.insert(0, "week6/pipeline")
from markdown_source import make_located_data
from run_md_pipeline import COMPANIES, extract_from_snippets

total_snippets = 0
total_candidates = 0
for code, name in COMPANIES:
    located = make_located_data(code, name)
    snippets = located["pevc_snippets"]
    rows = extract_from_snippets(snippets, code, name)
    total_snippets += len(snippets)
    total_candidates += len(rows)
print(total_snippets, total_candidates)
PY
done
```

## 四、确定性检查结果

| `PYTHONHASHSEED` | 文本片段 | 候选数 | 是否与基准一致 |
|---:|---:|---:|---|
| 0 | 325 | 645 | 是 |
| 1 | 325 | 645 | 是 |
| 2 | 325 | 645 | 是 |
| 3 | 325 | 645 | 是 |

修复前，投资人集合未经排序就截取前 8 个，不同哈希种子曾产生 641—660 条候选。现在 `stable_unique_names()` 先去重并按 Unicode 排序，四次运行结果一致。

## 五、结果对账

| 检查项 | 结果 |
|---|---:|
| 公司数 | 8 |
| Markdown 文件数 | 9 |
| 相关文本片段 | 325 |
| 候选总数 | 645 |
| 缺少日期 | 214 |
| 缺少金额 | 311 |
| 缺少股数 | 637 |
| 缺少价格 | 645 |
| 设立 | 311 |
| 增资 | 276 |
| 股权转让 | 26 |
| 整体变更 | 16 |
| 吸收合并 | 8 |
| 资本公积转增 | 8 |

这些数字应与 `candidate_quality_audit.csv` 的合计行完全一致。

## 六、输入文件清单与 SHA-256

```text
62dd2d69c5d48aa0280cb7f6d4c751521f52c6b765916b5e85a173618246e102  week1/review/三联锻造_招股书_PyMuPDF.md
eb27ac74dffb38408fa295b48ee20b737e6df203c75fba672bb43fe044c5b16c  week1/review/云汉芯城_招股书_PyMuPDF.md
049b7725869734ef24579a1f35a6cd49b78139c54bf83324d81fdacedcd94869  week1/review/黄山谷捷_招股书_PyMuPDF.md
7711aa33eaa63444b9e18c7ea9b9a13f0b0f80227fde5d9853f389e9c8d34a08  week1/review/友升股份1.md
84f6db8035e5089017e3a033720dfa53881c6e6b8a650a175bf5446fae9debe1  week1/review/友升股份2.md
87e02693eea7838c39c198f2606a81a9c80b74118ddefa575d9224a6ab93b872  week1/review/688758_赛分科技_招股书_正式稿_20250106.md
69373a24f77ddc239d104aaaf576c0e30e7c15e105471c937f1f95fee29a75af  week1/review/688775_影石创新_招股书_正式稿_20250606.md
72ca307b7f371743f7684818b3d781bade8a7470de8884b03d5ed4e71f353dbf  week1/review/三协电机_招股书_正式稿_20250711.md
9d3339ed973dbca36d76335a4104c6dcd8e0305a320f81be322ff24d7f63ee50  week1/review/星图测控_招股书_正式稿_20241220.md
```

复核输入：

```bash
shasum -a 256 week1/review/*.md
```

## 七、已知限制

1. `extracted_at` 使用运行时间，因此逐条 JSON 内容哈希不会天然一致；本次只验证统计结果的确定性。
2. 当前没有锁定完整 Python 依赖版本；下一步应增加 requirements 或 lock 文件。
3. Markdown 的 `MD pXX` 是文本分段页码线索，不应未经核验就当作 PDF 法定页码。
4. 候选稳定不代表候选正确；Precision、Recall、F1 要等 Week 8 的 Auto-vs-Gold 评价器完成后再报告。
5. 明显非投资人 120 条是基于保守规则得到的误报下界，不是完整 FP 数。

## 八、验收记录

| 验收项 | 结果 |
|---|---|
| 4 个 `PYTHONHASHSEED` 复跑 | 均为 325 个片段、645 条候选 |
| CSV 分公司数据与合计行对账 | 通过 |
| 24 条错误案例是否真实出现在候选中 | 通过 |
| `week6/tests` | 7 passed，5 skipped（数据库未配置） |
| `week6/pipeline/test_vie_regression.py` | 5 passed |
| `week5/scripts/test_vie_regression.py` | 5 passed |
| `git diff --check` | 通过 |

仓库中 Week 5 与 Week 6 各有一个同名 `test_vie_regression.py`，一次性从仓库根目录收集会触发 pytest 的模块名冲突，因此上述两个文件分别运行。该命名问题应作为后续工程清理项，不影响各自测试结果。

## 九、复现结论

当前代码在固定输入上已经解决“不同哈希种子导致候选数漂移”的问题，可稳定得到 645 条候选；但数据质量仍不足以进入最终研究数据集。Week 8 的重点是冻结 Gold、建立匹配器并得到第一组严格评价指标。
