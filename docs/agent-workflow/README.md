# Codex 与 Cursor 的验证流程

本仓库通过根目录 `AGENTS.md` 为 Codex 提供项目约束，通过
`.agents/skills/` 提供两项 pstack 官方验证技能，并用 GitHub Actions
运行离线检查。无须安装 Cursor 即可使用这些仓库文件。重新开启 Codex
任务可发现新增的仓库技能；当前任务已经使用它们的原则配置验证流程。

这些文件是项目配置，不是完整 pstack 插件安装。未引入其 Cursor 专用
模型路由、并行代理、自动合并或外部消息自动化。

## 使用

从仓库根目录执行：

```bash
bash scripts/setup_agent_env.sh
.venv/bin/python scripts/verify_agent_workflow.py
```

验证器检查现有测试、8 家公司 Markdown 提取和冻结版投资人评价。
它打印临时输出目录，保留本次结果供检查；不会覆写历史研究输出。
核心依赖沿用 `week6/requirements.txt` 的版本范围，仅排除 README 标为
可选的 PaddleOCR/PaddlePaddle。仓库没有锁文件，新环境解析的版本可能变化。

初始测试基线为 42 通过、5 项数据库测试跳过、1 项失败。
失败项 `test_issued_shares_converted_to_wan` 暴露已有股数解析缺陷，
因此 CI 目前应显示失败；本次配置不修改提取逻辑或测试。
冻结版评价基线为 Gold 42、Auto 45、TP 42、F1 96.55%。
候选数量不等于准确率；本次 Markdown 输出 291 条候选。
OCR、PDF 数据获取、远程数据库和 DeepSeek API 不在离线验证范围。

## 以后使用 Cursor

在 Cursor 中执行官方命令：

```text
/add-plugin pstack
/setup-pstack
```

按实际可用模型完成设置后，可用 `/poteto-mode` 启动其工作流。
这些命令需要在你的 Cursor 客户端执行，提交仓库配置不会安装桌面插件。
阅读文献时，仍须逐条核实论文原文、引用及模型总结；代码验证不能替代文献证据。

## 来源与许可证

官方来源：https://github.com/cursor/plugins/tree/main/pstack

本次导入的两项技能保持原文，来自 `cursor/plugins` commit
`1dcc2bacde73ddd284803b7af28164d0436198fc`，pstack 版本 `0.15.21`：

- `skills/principle-prove-it-works/SKILL.md`
- `skills/principle-test-behavior-not-implementation/SKILL.md`

上游 MIT 许可证保存在本目录 `PSTACK-LICENSE`。项目验证器、CI 和
`AGENTS.md` 是针对此仓库编写的配置，不属于上游官方插件。
