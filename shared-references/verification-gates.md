# 验证门定义（verification-gates）

> `gui-review`（唯一验证阶段）的契约。gui-review 以**并行两车道**运行：Type-A（orchestrator
> 自跑机械门）∥ Type-B（独立 gui-reviewer subagent judge），汇合成合并 CRITICAL 集合与 6 态裁决。
> **全程无中途 HUMAN_CHECKPOINT**：能机器验证的全做完，需人确认的统一收口到 `HUMAN_REVIEW.md`，
> 管线不停顿（plan §六 / §九）。原独立的 gui-verify 阶段已并入本阶段。

## Type-A 车道（orchestrator 自行判断，机器可验证）

不需要品味/判断，静态或离线可验证：

| 检查项 | 验证方式 | 缺能力时 |
|--------|---------|----------|
| C# 编译通过 | 运行时若已加载 Unity 编译/刷新能力则读 Console / 触发 refresh | 判 `BLOCKED`，记入清单 |
| Lua 语法正确 | `luac -p` 或热更无报错 | 判 `BLOCKED` |
| Prefab 节点存在 | 读 Prefab hierarchy，核对 View 中 SerializeField 名称对应节点 | 判 `BLOCKED`/`NOT_APPLICABLE` |
| 绑定数量匹配 | View 中 SerializeField 数量 vs Prefab 实际绑定数量 | 判 `BLOCKED` |
| 生成文件优先工具导出 | 检查 `*_viewmodel.lua` / `*ViewModel.cs` 的 diff（`*_data.lua` 例外） | 直接可查；若 diff 带 `TODO(模拟导出)` 标记（工具导出失败的降级手改兜底，见 mvvm-contract §3）→ 判 `BLOCKED` 记入清单「待工具正式重新导出覆盖」，**不判 failed**，不触发 improve 回退；若**无标记的**手改（本可用工具却未用）→ 仍判 failed |
| 配置 Excel↔data 同步 | Excel 源表与对应 `*_data.lua` 改动一致（模拟导表已镜像） | 无配置变更则 `NOT_APPLICABLE` |

## Type-B 车道（subagent judge，需品味/领域知识）

| 检查项 | 验证方式 |
|--------|---------|
| 交互逻辑正确性 | subagent 模拟用户操作流程，检查状态转换 |
| 性能反模式 | subagent 扫描 Update/FixedUpdate 中的危险操作 |
| UI 布局合理性 | subagent 检查 anchors、pivot、层级结构 |

> Type-B 由 `gui-reviewer` subagent（Bias Guard，全新上下文）承担，产出 `GUI_REVIEW.md`；与
> Type-A 车道**并行**（`run_in_background`），两者只读不写、无竞态。这是全流程**唯一一遍**独立
> 品味评审——不再有第二个阶段重跑同一 reviewer。

## 6 态裁决

输出 `GUI_VERDICT.json`：

```json
{
  "panel_id": "xxx",
  "verdict": "PASS|WARN|FAIL|NOT_APPLICABLE|BLOCKED|ERROR",
  "type_a_gates": { "compile": "passed|failed|skipped", "...": "..." },
  "type_b_gates": { "interaction": "passed|failed|skipped", "...": "..." },
  "summary": "...",
  "timestamp": "2026-06-16T..."
}
```

| Verdict | 含义 | 需人工签字? |
|---------|------|-----------|
| PASS | 全部通过 | 否 |
| WARN | 有 MAJOR/MINOR 但无 CRITICAL | 否 |
| FAIL | 有 CRITICAL 未修复 | **需人工签字** |
| NOT_APPLICABLE | 某项检查不适用（如无配置变更则跳过 config gate） | 否 |
| BLOCKED | 检查条件不满足（Unity 未开、Prefab 不存在、缺对应 MCP） | **需人工签字** |
| ERROR | 检查执行出错（超时、工具异常） | **需人工签字** |

> 6 态相对 3 态的价值：显式区分「没查」(NOT_APPLICABLE)、「查不了」(BLOCKED)、「查出错」(ERROR)，
> 避免静默跳过。

## 「需人工签字」≠ 管线停顿

`FAIL` / `BLOCKED` / `ERROR` **不停管线**，而是写进 `HUMAN_REVIEW.md` 并继续跑到 `gui-learn`。
合入/上线前由人统一确认。

## 门失败处理策略（两车道汇合成合并 CRITICAL 集合）

- **合并 CRITICAL 集合** = `{Type-A 编译失败}` ∪ `{Type-A Lua 语法错误}` ∪ `{Type-B 报的 CRITICAL}`。
  Type-A 的编译 / 语法失败**升为 CRITICAL**（补上了原设计的漏洞：编译错误也能触发修复循环）。
- **合并 CRITICAL > 0** → 触发 `gui-improve` 修复循环（最多 2 轮），每轮修完**重跑 gui-review 两车道**。
- Type-A `BLOCKED`（缺 Unity/Prefab/MCP 能力、模拟导出待覆盖）/ `NOT_APPLICABLE`：**不进** CRITICAL
  集合（避免缺能力拖入死循环），记入 `HUMAN_REVIEW.md`，verdict 含 BLOCKED。
- Type-B 的 MAJOR/MINOR：写入 `GUI_REVIEW.md`，不触发 improve（仅 CRITICAL 触发）。

## HUMAN_REVIEW.md —— 最终统一人工检查清单

管线末尾一次性产出（不在中途打断），集中所有「agent 做不了 / 需人确认」项：

- [ ] **Excel 配置正确性**：源表字段/数值是否符合需求；**正式 GDE 导表**覆盖模拟写入的 `*_data.lua`
- [ ] **运行期效果**：启动客户端打开该 panel，截图核对交互与布局
- [ ] **未解决 CRITICAL**（如 2 轮修复后仍有）：逐条列出 file:line + 原因
- [ ] **BLOCKED / 降级项**：因环境缺失（Unity 未开、缺对应 MCP 等）未能自动验证的项

## 运行状态记录

各阶段 `done` / `accepted` 用 `gui_run_state.py` 落盘到
`${CLAUDE_PROJECT_DIR}/.claude/dev-gui-runs/<panelId>/run_state.json`：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_run_state.py" set "${CLAUDE_PROJECT_DIR}" <panelId> gui-review done
# 仅当合并 CRITICAL == 0（独立 reviewer + 确定性 Type-A 均通过），才 accept（记录 verdict 来源）：
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_run_state.py" accept "${CLAUDE_PROJECT_DIR}" <panelId> gui-review \
    --reviewer gui-reviewer+type-a --verdict-id <run>/GUI_VERDICT.json
```

> `done`（自报执行完成）与 `accepted`（独立审查通过）分离：一个 loop 可以 DRIVE，不能 ACQUIT
> 自己（见 `acceptance-gate.md`）。
