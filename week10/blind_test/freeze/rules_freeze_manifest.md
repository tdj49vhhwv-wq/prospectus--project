# 规则冻结清单（盲测用）

**冻结日期**：2026-08-07
**基线 commit**：`9ff43a5d3c92150865a3a89ce951b13db3e55bb0`（Week 7：补充质量审计与可复现证据包）

## 1. 冻结范围

Week 10 盲测运行必须使用下列文件的当前内容；运行前用 `rules_freeze_manifest.json` 中的 sha256 校验，任何不匹配都必须停止运行并查明原因。

| 文件 | 角色 |
|------|------|
| `week6/pipeline/run_md_pipeline.py` | Markdown 候选管线与 PATTERNS 正则规则 |
| `week6/pipeline/config.py` | 公司清单与提取配置 |
| `week6/pipeline/event_category_definitions.json` | 事件类型定义 |
| `week6/pipeline/event_type_mapping.md` | 事件类型映射文档 |
| `week6/pipeline/extract_pevc.py` | PE/VC 抽取逻辑 |
| `week6/pipeline/markdown_source.py` | Markdown 输入与章节定位 |

## 2. 输入文件

| 文件 | 角色 |
|------|------|
| `week1/review/688795_摩尔线程_招股书_正式稿_20251128.md` | 688795 盲测输入 |
| `week1/review/688802_沐曦股份_招股书_正式稿_20251211.md` | 688802 盲测输入 |

## 3. 允许与禁止的变更

允许：
- 在独立 commit 中向 `run_md_pipeline.py` 的 `COMPANIES` 与 `markdown_source.py` 的 `MD_FILES` 增加 688795/688802 两条输入映射；
- 记录 Gold 标注文件与 decision log。

禁止（直到盲测结果写入报告并解锁）：
- 修改 `PATTERNS` 中任何正则；
- 修改事件类型映射、分类规则或抽取逻辑；
- 修改 Gold 口径后静默重标（必须走 `gold_change_log`）。

## 4. 校验命令

```bash
cd /Users/zhaobingqing/Documents/Codex/2026-08-07/ni/work/prospectus--project-shallow
shasum -a 256 -c week10/blind_test/freeze/rules_freeze_manifest.sha256
git diff 9ff43a5d3c92150865a3a89ce951b13db3e55bb0 -- week6/pipeline/run_md_pipeline.py | rg 'PATTERNS|^\+\s*r\('
```

第二条命令应无输出（即相对基线只允许公司清单变更，不得出现正则改动）。

## 5. 冻结记录

详细 hash 见 `rules_freeze_manifest.json`。运行后把结果目录 hash、Gold 版本和 commit 写入 Week 10 盲测报告。
