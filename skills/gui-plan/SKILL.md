---
name: gui-plan
description: >-
  Atom Game GUI 开发 pipeline 的第 1 阶段（入口）。当用户要「开发/新增/修改一个 GUI 界面、
  panel、面板」或说「跑 gui pipeline / 做 GUI 需求」时使用。收集 panelId + 功能描述 + Prefab
  路径，查询长期知识库 query_pack，产出结构化需求 GUI_PRD.md，并初始化 pipeline 运行状态。
  随后通常顺序触发 gui-draft → gui-prefab → gui-config → gui-review → gui-verify →
  gui-improve → gui-learn。
---

# Phase 1: gui-plan — 信息收集 + 知识库查询

**职责**：收集 panelId、功能描述、Prefab 路径，缺失则一次性追问（全自动 run 模式下改为占位+TODO，不追问）；加载 gui-knowledge
query_pack 提供历史上下文；产出 `GUI_PRD.md`；初始化 run state。**控制：需求理解漂移。**

## 路径约定（所有阶段共用）

- 工具：`${CLAUDE_PLUGIN_ROOT}/tools/`
- 契约：`${CLAUDE_PLUGIN_ROOT}/shared-references/`
- 知识库种子（只读）：`${CLAUDE_PLUGIN_ROOT}/gui-knowledge-seed/`
- **长期知识库（持久化、可写）**：`${CLAUDE_PLUGIN_DATA}/gui-knowledge/`
- **本次运行产物（项目本地、gitignored）**：`${CLAUDE_PROJECT_DIR}/.claude/dev-gui-runs/<panelId>/`

## 流程

1. **检查输入齐全度**
   - 必须：`panelId`、功能描述
   - 可选但重要：Prefab 路径（可由 ui_data.lua 推断）
2. **缺失必须项的处理 —— 先判断当前是否在全自动 run 模式**：
   - **全自动模式**（本次 run 目录存在 `.autorun.json` 哨兵，即由 `/dev-gui-plugin:run` 驱动）：
     **禁止 `AskUserQuestion`、禁止停下来追问**。给缺失项取合理占位值（如从功能描述推一个 PascalCase
     panelId）继续推进，并在 `GUI_PRD.md` 标 `**[TODO: 待人工确认] <缺什么>**`，同时汇总进 `HUMAN_REVIEW.md`。
   - **手动单独调用**（无哨兵）：用 `AskUserQuestion` **一次性**收集所有缺失项（不要逐条追问）。
3. **定位资源**：读 `code/LuaScripts/client/data/ui_data.lua`，按 panelId 定位 Prefab 路径、
   Panel 脚本路径、ViewModel 类型。找不到则在 PRD 标注「待确认」。
4. **加载知识库**：
   - 若 `${CLAUDE_PLUGIN_DATA}/gui-knowledge/` 不存在 → 先初始化：
     ```bash
     python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_knowledge.py" init "${CLAUDE_PLUGIN_DATA}/gui-knowledge"
     ```
     （如需种子内容，可先把 `${CLAUDE_PLUGIN_ROOT}/gui-knowledge-seed/` 的内容复制过去再 init。）
   - 读 `${CLAUDE_PLUGIN_DATA}/gui-knowledge/query_pack.md`，提取与本需求相关的历史坑点/组件技巧。
     （SessionStart hook 已尝试预注入，此处兜底确认。）
5. **初始化运行状态**：
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_run_state.py" start "${CLAUDE_PROJECT_DIR}" <panelId>
   python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_run_state.py" set "${CLAUDE_PROJECT_DIR}" <panelId> gui-plan done
   ```
6. **产出 `GUI_PRD.md`** 到 run 目录。

## 输出格式 `GUI_PRD.md`

```markdown
# GUI PRD: <panelId>

## 基本信息
- panelId: xxx
- Prefab 路径: Assets/...
- Panel 脚本路径: code/LuaScripts/client/...
- ViewModel 类型: XXXViewModel

## 功能描述
[结构化需求描述]

## 相关历史经验（来自 gui-knowledge）
- [涉及的组件已知坑点]
- [类似界面曾出现的 bug]
```

## Gate

`panelId + 功能描述` 必须齐全 → 进入 **gui-draft**。

> 整条 pipeline 无中途人工暂停；需人确认项最终统一收口到 `HUMAN_REVIEW.md`（gui-verify 末）。
