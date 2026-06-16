---
name: gui-improve
description: >-
  Atom Game GUI pipeline 第 7 阶段。对 GUI_REVIEW.md 中的 CRITICAL 问题迭代修复（最多 2 轮）：
  修复 → 全新 subagent 重新审查（Bias Guard）→ 记录 GUI_IMPROVEMENT_LOG.md。仅当 gui-review
  报出 CRITICAL 时使用。2 轮后仍有 CRITICAL 则记入 HUMAN_REVIEW.md，不暂停。
---

# Phase 7: gui-improve — 迭代修复循环

**职责**：修复 CRITICAL → 重新审查 → 重新验证，**最多 2 轮**。

## 流程

```
Round 1:
  1. 读 GUI_REVIEW.md 的 CRITICAL + MAJOR 问题
  2. 按优先级修复（CRITICAL → MAJOR）
  3. 重新 spawn gui-reviewer subagent（全新上下文，Bias Guard）审查
  4. 对比新旧审查结果
  5. 记录 GUI_IMPROVEMENT_LOG.md

Round 2（如仍有 CRITICAL）:
  重复 1-5，修复剩余 CRITICAL

2 轮后仍有 CRITICAL:
  → 把未解决项写入 HUMAN_REVIEW.md（逐条 file:line + 原因），不暂停
  → 继续跑 gui-verify + gui-learn，由最终人工清单统一收口
```

## Bias Guard 实现（每轮重新审查）

spawn 全新 `gui-reviewer` subagent，**不在 prompt 中包含**：
- 上一轮的审查结果
- 「我们已修复了 XXX」
- 之前 subagent 的 threadId

**只传递**：当前代码文件 + GUI_PRD.md + 相关 shared-references。
（理由见 `${CLAUDE_PLUGIN_ROOT}/shared-references/acceptance-gate.md`：执行者不能为自己的修复辩护。）

## 输出 `GUI_IMPROVEMENT_LOG.md`

```markdown
# GUI Improvement Log: <panelId>

| Round | Score Before | Score After | Key Changes |
|-------|-------------|------------|-------------|
| 1 | 5/10 | 7/10 | 修复空指针、补充事件退订 |
| 2 | 7/10 | 8/10 | 优化列表滚动性能 |

## Round 1
### Issues Fixed
1. [CRITICAL] ...
### Review After Fix
[新审查结果摘要]
```

## 记录状态

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_run_state.py" set "${CLAUDE_PROJECT_DIR}" <panelId> gui-improve done
```

→ 回到 **gui-verify** 出最终裁决，再进 **gui-learn**。
