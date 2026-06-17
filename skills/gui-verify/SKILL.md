---
name: gui-verify
user-invocable: false
description: >-
  Atom Game GUI pipeline 第 6 阶段。执行 Type-A（self-check）+ Type-B（subagent judge）验证门，
  产出 6 态裁决 GUI_VERDICT.json 与最终统一人工检查清单 HUMAN_REVIEW.md。全程无中途人工暂停。
  在 gui-review（无 CRITICAL）或 gui-improve 之后使用。
---

# Phase 6: gui-verify — 验证门

**职责**：执行 Type-A / Type-B 验证，输出 6 态裁决 + 最终人工清单。

> 基准文档：`${CLAUDE_PLUGIN_ROOT}/shared-references/verification-gates.md`
> 与 `acceptance-gate.md`。**全程无中途 HUMAN_CHECKPOINT**——需人确认的全部汇总进
> `HUMAN_REVIEW.md`，管线继续。

## Type-A 门（orchestrator 自判，机器可验证）

逐项判 `passed | failed | skipped`，缺能力判 `BLOCKED` 并记入清单：

- C# 编译通过（有 Unity 能力则读 Console / refresh，否则 BLOCKED）
- Lua 语法正确（`luac -p` 或热更无报错）
- Prefab 节点存在 / 绑定数量匹配（有 Prefab 能力则核实，否则 BLOCKED）
- 生成文件优先工具导出（`*_viewmodel.lua` / `*ViewModel.cs` 的 diff；`*_data.lua` 例外）
  - 例外：diff 带 `TODO(模拟导出)` 标记（工具导出失败的降级手改兜底）→ 判 `BLOCKED`「待工具正式重新导出覆盖」记入清单，**不判 failed、不触发 improve 回退**
  - 无标记的手改（本可用工具却未用）→ 仍判 failed
- 配置 Excel↔data 同步（无配置变更 → `NOT_APPLICABLE`）

## Type-B 门（spawn gui-reviewer subagent，Bias Guard）

- 交互逻辑正确性（模拟用户操作流程，检查状态转换）
- 性能反模式（扫描 Update/FixedUpdate 危险操作）
- UI 布局合理性（anchors / pivot / 层级）

## 6 态裁决 → `GUI_VERDICT.json`

```json
{
  "panel_id": "xxx",
  "verdict": "PASS|WARN|FAIL|NOT_APPLICABLE|BLOCKED|ERROR",
  "type_a_gates": { "compile": "passed", "...": "..." },
  "type_b_gates": { "interaction": "passed", "...": "..." },
  "summary": "...",
  "timestamp": "2026-06-16T..."
}
```

| Verdict | 含义 | 需人工签字 |
|---------|------|-----------|
| PASS | 全部通过 | 否 |
| WARN | 有 MAJOR/MINOR 无 CRITICAL | 否 |
| FAIL | 有 CRITICAL 未修复 | 是 |
| NOT_APPLICABLE | 不适用 | 否 |
| BLOCKED | 检查条件不满足 | 是 |
| ERROR | 检查执行出错 | 是 |

> 「需人工签字」≠ 停顿。FAIL/BLOCKED/ERROR 写进 `HUMAN_REVIEW.md`，继续跑到 gui-learn。

## 产出 `HUMAN_REVIEW.md`（最终统一人工检查清单）

```markdown
# Human Review: <panelId>
- [ ] Excel 配置正确性 + 正式 GDE 导表（覆盖模拟写入的 *_data.lua）
- [ ] 运行期效果：打开 panel 截图核对交互与布局
- [ ] 未解决 CRITICAL（如有）：<file:line + 原因>
- [ ] BLOCKED / 降级项：<因环境缺失未能自动验证的项>
```

## 记录状态

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_run_state.py" set "${CLAUDE_PROJECT_DIR}" <panelId> gui-verify done
# 若 verdict=PASS（确定性验证通过），accept：
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_run_state.py" accept "${CLAUDE_PROJECT_DIR}" <panelId> gui-verify \
    --reviewer type-a+type-b --verdict-id <run>/GUI_VERDICT.json
```

→ 进入 **gui-learn**（每次必做）。
