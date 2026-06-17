---
name: gui-review
description: >-
  Atom Game GUI pipeline 第 5 阶段。spawn 独立 gui-reviewer subagent（全新上下文，Bias Guard）
  审查 Phase 2-4 的产出代码，产出 GUI_REVIEW.md（CRITICAL/MAJOR/MINOR + Overall Score）。
  也可单独用于审查已有 GUI 代码。控制逻辑质量漂移。
---

# Phase 5: gui-review — Subagent 审查

**职责**：spawn 独立 subagent 审查产出代码。Subagent 获得全新上下文，不知道实现过程。
**控制：逻辑质量漂移。**

## Bias Guard 规则（最关键）

- 每次审查用 **全新 subagent**（agent type: `gui-reviewer`），**不传**之前的 thread/context。
- 审查 prompt 中**不包含**「我们改了什么」「上一轮提到」等实现细节。
- 只传递：**当前代码文件 + GUI_PRD.md + 相关 shared-references**。
- 审查者只能从代码本身判断质量。

## 流程

1. 收集 Phase 2-4 的产出文件路径（Panel.lua / View.cs / 改动的 prefab / Excel↔data）。
2. spawn `gui-reviewer` subagent（用 Agent 工具，`subagent_type: "gui-reviewer"`），传入：
   - 待审代码文件
   - `${CLAUDE_PROJECT_DIR}/.claude/dev-gui-runs/<panelId>/GUI_PRD.md`
   - 相关 `${CLAUDE_PLUGIN_ROOT}/shared-references/*.md`（含 `patterns/` 下涉及的进阶模式文档）
   - **不传**任何实现叙述。
3. subagent 按 7 维度审查（见 `agents/gui-reviewer.md`），产出 `GUI_REVIEW.md` 到 run 目录。
4. 记录状态：
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_run_state.py" set "${CLAUDE_PROJECT_DIR}" <panelId> gui-review done
   ```
   若无 CRITICAL，可由本次 review 作为独立判定源 accept：
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_run_state.py" accept "${CLAUDE_PROJECT_DIR}" <panelId> gui-review \
       --reviewer gui-reviewer --verdict-id <run>/GUI_REVIEW.md
   ```

## 审查维度

MVVM 一致性 / 生命周期正确性 / 空安全 / 性能反模式 / 代码规范 / Prefab 绑定 / 配置完整性。
（详见 `${CLAUDE_PLUGIN_ROOT}/agents/gui-reviewer.md`。）

## 输出 `GUI_REVIEW.md`

```markdown
# GUI Review: <panelId>
## Overall Score: X/10
## Critical Issues
1. [CRITICAL] <描述> @ <file>:<line> — 修复建议: ...
## Major Issues
...
## Minor Issues
...
```

## Gate（分支）

- **CRITICAL == 0** → 跳过 gui-improve，直接进入 **gui-verify**。
- **有 CRITICAL** → 进入 **gui-improve**（迭代修复，最多 2 轮）。
