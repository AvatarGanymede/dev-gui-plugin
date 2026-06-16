---
description: 一键全自动跑完 dev-gui 8 阶段 pipeline（plan→draft→prefab→config→review→verify→improve→learn），阶段间不停顿询问，缺信息留空+TODO
argument-hint: [panelId 与功能描述，例如：BagPanel 新增批量出售按钮，prefab=Assets/UI/Bag.prefab]
---

# /dev-gui-plugin:run — 全自动 GUI pipeline 编排

你现在是 **dev-gui-plugin pipeline 的编排者（orchestrator）**。本命令把 8 个阶段串成
一条**不间断**的流水线，**显式编排**，不依赖各 skill 描述里的「→ 进入下一阶段」暗示。

本次需求（原始输入）：

> $ARGUMENTS

---

## 铁律（全程适用，优先级高于各 skill 内的默认交互行为）

1. **依次执行全部 8 阶段**：gui-plan → gui-draft → gui-prefab → gui-config → gui-review
   → gui-verify →（按需）gui-improve → gui-learn。**逐个加载对应 SKILL.md 并执行**。
2. **阶段间不得停顿询问**：禁止使用 `AskUserQuestion`，禁止在阶段之间停下来等用户确认、
   征求选择或要求补充信息。一个阶段做完，**立即**进入下一个阶段。
3. **缺必要信息 → 先留空实现并留下 TODO 注释**：
   - 若 `panelId` / 功能描述 / Prefab 路径 / ViewModel 类型等缺失或无法从
     `code/LuaScripts/client/data/ui_data.lua` 推断，**不要追问**。
   - 取一个合理的占位值继续推进，并在产物中显式标注：代码里写
     `-- TODO(dev-gui:run): <缺什么 / 需人工确认什么>`（Lua）或
     `// TODO(dev-gui:run): ...`（C#）；文档/PRD 里写 `**[TODO: 待人工确认] ...**`。
   - 所有这些 TODO 同时汇总进 `HUMAN_REVIEW.md`，由末尾统一人工复核收口。
4. **能力缺失（无对应 MCP / Unity 未开等）不阻塞**：按各 skill 规则降级标
   `BLOCKED` / `NOT_APPLICABLE` 记入 `HUMAN_REVIEW.md`，继续往下跑。
5. **绝不在中途结束本次任务**：必须一路跑到 `gui-learn` 完成、产出齐全后才收尾。

> 运行产物目录：`${CLAUDE_PROJECT_DIR}/.claude/dev-gui-runs/<panelId>/`
> 工具目录：`${CLAUDE_PLUGIN_ROOT}/tools/`

---

## 执行步骤

### 0. 解析输入 + 开启自动驱动哨兵

- 从上面的需求中解析出 `panelId`（缺失则取合理占位，如从功能描述推一个 PascalCase 名，
  并记 TODO）。设环境变量便于后续命令复用：`PID=<panelId>`。
- 初始化 run state 并**写自动驱动哨兵**（让 Stop hook 调度器在你意外停下时把你拉回流水线）：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_run_state.py" start "${CLAUDE_PROJECT_DIR}" "$PID"
mkdir -p "${CLAUDE_PROJECT_DIR}/.claude/dev-gui-runs/$PID"
printf '{"nudges":0,"max_nudges":30,"command":"dev-gui:run"}' \
  > "${CLAUDE_PROJECT_DIR}/.claude/dev-gui-runs/$PID/.autorun.json"
```

### 1–8. 逐阶段执行

按顺序加载并执行每个 SKILL（`${CLAUDE_PLUGIN_ROOT}/skills/<phase>/SKILL.md`），每完成一个就用
`gui_run_state.py set ... <phase> done` 记账，**随即进入下一个**，期间遵守上面的铁律：

| 顺序 | 阶段 | 关键动作 | 不适用时 |
|------|------|---------|---------|
| 1 | `gui-plan` | 产出 `GUI_PRD.md`；**此模式下不 AskUserQuestion**，缺信息占位+TODO | — |
| 2 | `gui-draft` | 生成 Panel.lua + View.cs（+ ViewModel） | — |
| 3 | `gui-prefab` | 绑定 `[SerializeField]`；无 prefab 能力 → 标 BLOCKED 入清单 | `set gui-prefab done`（已记清单） |
| 4 | `gui-config` | 改 Excel 源表 + 镜像 `*_data.lua`；**本需求不涉及配置 → `set gui-config skipped`** | `skipped` |
| 5 | `gui-review` | spawn 独立 reviewer（Bias Guard）产出 `GUI_REVIEW.md` | — |
| 6 | `gui-improve` | **仅当 review 有 CRITICAL 时执行**（最多 2 轮）；**无 CRITICAL → `set gui-improve skipped`** | `skipped` |
| 7 | `gui-verify` | Type-A/B 验证 → `GUI_VERDICT.json` + `HUMAN_REVIEW.md` | — |
| 8 | `gui-learn` | 知识沉淀（捕获遍）回写 `${CLAUDE_PLUGIN_DATA}/gui-knowledge/` | — |

> 注意阶段执行顺序：review(5) 先于 verify。若 review 报 CRITICAL，则在 verify 前先跑
> gui-improve（修复→重新审查，最多 2 轮）；2 轮后仍有 CRITICAL 记入 `HUMAN_REVIEW.md` 不暂停。
> 凡某阶段在本次不适用，**务必显式 `set <phase> skipped`**——否则调度器会判定未完成并把你拉回。

### 9. 收尾

- 确认每个阶段在 run state 中均为 `done` / `accepted` / `skipped`：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_run_state.py" status "${CLAUDE_PROJECT_DIR}" "$PID"
```

- 移除自动驱动哨兵（流水线已跑完）：

```bash
rm -f "${CLAUDE_PROJECT_DIR}/.claude/dev-gui-runs/$PID/.autorun.json"
```

- 向用户输出一句话总结 + `HUMAN_REVIEW.md` 路径，提示其中待人工确认/TODO 项。
