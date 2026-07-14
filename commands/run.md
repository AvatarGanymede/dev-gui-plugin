---
description: 一键全自动跑完 dev-gui 7 阶段 pipeline（plan→draft→prefab→config→review→improve→learn），阶段间不停顿询问，缺信息留空+TODO
argument-hint: [panelId 与功能描述，例如：BagPanel 新增批量出售按钮，prefab=Assets/UI/Bag.prefab]
---

# /dev-gui-plugin:run — 全自动 GUI pipeline 编排（支持 resume + pcraft 绑定）

你现在是 **dev-gui-plugin pipeline 的编排者（orchestrator）**。本命令把 7 个阶段串成
一条**不间断**的流水线，**显式编排**，不依赖各 skill 描述里的「→ 进入下一阶段」暗示。

本次需求（原始输入）：

> $ARGUMENTS

---

## 铁律（全程适用，优先级高于各 skill 内的默认交互行为）

1. **执行全部 7 阶段**：gui-plan → gui-draft →（**gui-prefab ∥ gui-config 并行组**）→ gui-review
   →（按需）gui-improve → gui-learn。**逐个加载对应 SKILL.md 并执行**；其中
   **gui-prefab（主 agent，先编译再改 prefab）与 gui-config（按需 spawn subagent）并行**，
   两者都落定后才进 gui-review（详见步骤 3–8 的「并行组编排」）。
2. **阶段间不得停顿询问（gui-plan 阶段除外）**：
   - **gui-plan 是唯一的交互 + 人类审批关卡**：走 Claude Code 原生 plan mode，**允许** `AskUserQuestion`
     澄清需求、并在 `ExitPlanMode` 处**等人类审批**。此阶段发生在 autorun 哨兵创建**之前**，Stop 钩子
     不驱动，可自由停顿。
   - **从 gui-draft 起**（哨兵已建、pipeline 正式全自动）才适用铁律：禁止使用 `AskUserQuestion`，
     禁止在阶段之间停下来等用户确认、征求选择或要求补充信息。一个阶段做完，**立即**进入下一个阶段。
3. **缺必要信息 → 先留空实现并留下 TODO 注释**：
   - 若 `panelId` / 功能描述 / Prefab 路径 / ViewModel 类型等缺失或无法从
     `code/LuaScripts/client/data/ui_data.lua` 推断，**不要追问**。
   - 取一个合理的占位值继续推进，并在产物中显式标注：代码里写
     `-- TODO(dev-gui:run): <缺什么 / 需人工确认什么>`（Lua）或
     `// TODO(dev-gui:run): ...`（C#）；文档/PRD 里写 `**[TODO: 待人工确认] ...**`。
   - 所有这些 TODO 同时汇总进 `HUMAN_REVIEW.md`，由末尾统一人工复核收口。
4. **某一步执行失败 → 先绕过，绕不过就跳过，绝不追问、绝不停下**：
   - 一步出错（命令报错、生成工具失败、文件找不到、依赖未就绪等）时，**禁止**因此向用户提问或中止流水线。
   - **优先想办法绕过**：能用等价手段达成同样产物的，就自己实现。例：导出产物（ViewModel 生成文件、配表
     `*_data.lua` 等）应**优先用工具导出**；工具导出失败 / 不可用时，按通用硬规则**降级手改补齐**（见
     `mvvm-contract §3`）——手写本应由工具产出的内容并在每处加 `TODO(模拟导出): 工具导出失败手改，待工具正式重新导出覆盖`，
     使后续 Phase 3 / View / Panel 能照常推进。
   - **绕不过 → 跳过该步**：把这一步的失败原因、已做到哪一步、人工需要补做什么写成一条 TODO 记入
     `HUMAN_REVIEW.md`，然后把该阶段状态置为 `skipped`（**不要置 `failed`**——`failed` 不是「已推进」状态，
     调度器会把你反复拉回同一阶段死循环）。随即进入下一阶段。
   - 绕过成功则照常 `set <phase> done`；只是无法验证而非失败的，按第 5 条降级标注。
5. **能力缺失（无对应 MCP / Unity 未开等）不阻塞**：按各 skill 规则降级标
   `BLOCKED` / `NOT_APPLICABLE` 记入 `HUMAN_REVIEW.md`，继续往下跑。
6. **绝不在中途结束本次任务**：必须一路跑到 `gui-learn` 完成、产出齐全后才收尾。
7. **所有遗留项最终汇总成一份 todo list 清单**：缺信息的 TODO、被跳过的步骤、绕过/模拟实现、
   `BLOCKED` / `FAILED` / 降级项，全部收口到 `HUMAN_REVIEW.md` 的勾选清单（见收尾步骤），交给用户自查，
   **流水线本身不为任何一项停顿等待**。

> 运行产物目录：`${CLAUDE_PROJECT_DIR}/.claude/dev-gui-runs/<panelId>__<sessionId>/`
> （run 目录与状态文件按**会话隔离**：同一面板在不同会话互不干扰。`<panelId>__<sessionId>`
> 这个 run_id 由 `gui_run_state.py` 内部统一拼接——**所有调用一律只传裸 `panelId`**。）
> 工具目录：`${CLAUDE_PLUGIN_ROOT}/tools/`
> 可选参数：`resume=true`（显式断点续跑，仅在**同一会话**内有效）。不带 `resume` 即视为
> **全新一跑**：先清空该 run 目录再开始（跨会话恢复是**非目标**——新会话 = 新 run_id = 干净起步）。

### pcraft 环境变量（可选，存在则自动绑定）

- `PCRAFT_TASK_ID`：当前 pcraft 任务 ID（用于收尾通知 DONE）
- `PCRAFT_API_URL`：pcraft 后端地址（如 `http://127.0.0.1:9999`）
- `P4CHANGE`：关联 changelist（只读记录到 run metadata）
- `P4CLIENT`：关联 workspace/client（只读记录到 run metadata）

---

## 执行步骤

### 0. 硬断言 session_id + 解析输入（纯只读；先不落地任何文件）

**硬先决条件（不可降级）**：本 run 的隔离键是 `panelId__<sessionId>`。下方脚本用
`gui_run_state.py runid` 取 `RID` 做断言；**若它失败（退出码非 0，拿不到 `CLAUDE_SESSION_ID`），
立即结束本次 `/run`**：把脚本打印到 stderr 的原因**原样转告用户**，**不建目录、不写哨兵、
不进入任何后续阶段**。绝不用空串或退回裸 `panelId` 降级——那会让不同会话的 run 互相覆盖。

> **重要时序**：gui-plan 走 plan mode，其间**不得有任何写操作**。所以建 run 目录 / `gui_run_state start` /
> 写 `run_meta.json` / 写 `GUI_PLAN.md` / 建 `.autorun.json` 哨兵，**全部推迟到步骤 2「gui-plan 审批
> 通过后」**一次性落地。本步骤（0）只做**只读断言 + 解析输入**，`runid` 仅打印 run_id，不写盘。

- 由编排者从需求中解析出 `panelId` 作为 `PID`（缺失则取合理 PascalCase 占位并记 TODO）。
- 由编排者判定 `RESUME_MODE`：原始输入（上面的需求）含 `resume=true/1/yes`（大小写不敏感）→ `1`，
  否则 `0`；把结论作为**字面量**填入下方 `RESUME_MODE=<0|1>`。
- **所有 `gui_run_state.py` 子命令一律只传裸 `$PID`**（工具内部会把 `PID` 拼成同一个会话作用域
  `RID`）。shell 变量不跨 Bash 块保留，后续每个块都按下式重新取 `RID`。

```bash
PID="<panelId>"          # ← 编排者用解析出的真实 panelId 替换
RESUME_MODE=<0|1>        # ← 编排者按是否显式 resume 填 0 或 1

# —— 硬断言：取会话作用域 run_id；拿不到 session_id 这里就退出 1 并打印原因 ——
# 注意：runid 只读打印，不写任何文件；此处仅断言，不建目录、不 start、不写哨兵。
if ! RID="$(python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_run_state.py" runid "$PID")"; then
  echo "DEVGUI_ABORT: 见上方原因，已终止 /run（未建目录、未写哨兵、未进入任何阶段）。" >&2
  exit 1
fi
echo "session-scoped run_id = $RID（此刻仅断言，尚未落地任何文件；写操作待 gui-plan 审批后）"
```

### 1. 计算执行起点

- **全新一跑（RESUME_MODE=0）**：直接进入步骤 2 的 gui-plan（plan mode）。run 目录/state 此刻
  **尚不存在是正常的**——它们在 gui-plan 审批后才建。
- **断点续跑（RESUME_MODE=1）**：由于 run 目录/state 现在「gui-plan 审批后」才建，故取断点前
  目录可能不存在：

```bash
PID="<panelId>"   # 同步骤 0；只传裸 PID，工具内部拼接会话作用域 run_id
RESUME_PHASE=""
if [ "$RESUME_MODE" = "1" ]; then
  RESUME_PHASE="$(python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_run_state.py" resume "${CLAUDE_PROJECT_DIR}" "$PID" 2>/dev/null || true)"
fi
```

- `RESUME_PHASE` 语义：
  - 空值（全新跑；或 `resume=true` 但目录/state 尚不存在＝审批前就中断）→ 从 **gui-plan（plan mode）** 重新开始
  - `gui-plan`：仍从 gui-plan 开始（通常意味着审批前中断，重走 plan mode 审批）
  - `gui-draft`...`gui-learn`：从该阶段继续（哨兵已在，全自动）
  - `COMPLETE`：7 阶段均 terminal（直接进入步骤 9）

### 2. gui-plan：plan mode 交互 + 人类审批 → 审批后 pipeline 启动

> 仅当起点为 `gui-plan`（全新跑，或 resume 但尚未审批）时执行本步骤；若 `RESUME_PHASE` 已是
> `gui-draft`..`gui-learn`（审批后中断续跑），跳过本步骤，直接进入步骤 3。

1. **进入 plan mode**：加载并执行 `${CLAUDE_PLUGIN_ROOT}/skills/gui-plan/SKILL.md`。若会话尚未处于
   plan mode，编排者主动 `EnterPlanMode`（已在则跳过）。plan mode 内**只做只读**：`Read`
   `code/LuaScripts/client/data/ui_data.lua` 定位 Prefab/脚本/ViewModel；用 SessionStart 已注入
   上下文的两库 query_pack 坑点。
2. **查代码自答，无法确定必须提问**：需求有缺口时先穷尽代码仓库（`ui_data.lua`、同目录现有
   panel/View/ViewModel、`shared-references`、已注入的 query_pack），能推断的一律自己定；
   **无法从代码确定的、需要用户确认的，必须向用户提问澄清，不得用 TODO 占位绕过**。
   用 `AskUserQuestion` 一次性问完所有此类问题（此阶段无哨兵，可停顿）。
3. **写计划 → `ExitPlanMode` 等人类审批**。被拒/要求改 → 回 plan mode 按反馈改，再 `ExitPlanMode`，
   循环直到通过。

**审批通过后**（已退出 plan mode，pipeline 正式启动）——一次性落地这批写操作：

```bash
PID="<panelId>"          # 同步骤 0
RESUME_MODE=<0|1>        # 同步骤 0
RID="$(python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_run_state.py" runid "$PID")" || {
  echo "DEVGUI_ABORT: 拿不到会话作用域 run_id，终止。" >&2; exit 1; }
RUN_DIR="${CLAUDE_PROJECT_DIR}/.claude/dev-gui-runs/$RID"

# 非 resume = 全新一跑：先清空旧目录，保证干净起步（同会话同面板重跑不会撞旧状态）。
if [ "$RESUME_MODE" != "1" ]; then
  rm -rf "$RUN_DIR"
fi
mkdir -p "$RUN_DIR"

# 初始化 run state（此刻先不 set gui-plan done——见下方顺序说明）。只传裸 PID。
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_run_state.py" start "${CLAUDE_PROJECT_DIR}" "$PID" \
  --pcraft-task-id "${PCRAFT_TASK_ID:-}" \
  --p4-changelist "${P4CHANGE:-}"

cat > "$RUN_DIR/run_meta.json" <<EOF
{
  "run_id": "$RID",
  "panel_id": "$PID",
  "session_id": "${CLAUDE_SESSION_ID:-}",
  "resume_mode": "$RESUME_MODE",
  "pcraft_task_id": "${PCRAFT_TASK_ID:-}",
  "pcraft_api_url": "${PCRAFT_API_URL:-}",
  "p4_changelist": "${P4CHANGE:-}",
  "p4_client": "${P4CLIENT:-}"
}
EOF
```

- **写 `GUI_PLAN.md`**：把用户刚审批过的计划**高度精炼**成需求契约，写到 `$RUN_DIR/GUI_PLAN.md`
  （格式见 `skills/gui-plan/SKILL.md`）。这是 gui-review 独立审查者（全新上下文）唯一能读到的
  需求基准——**不是**让 AI 重写一份 PRD，而是把审批结果原样落盘。缺失项标 `**[TODO: 待人工确认]**`
  并汇总进 `HUMAN_REVIEW.md`。

- **标记 gui-plan done → 建哨兵**（顺序是硬约束，不可颠倒）：

> **落地顺序不变量**：`start → run_meta → 写 GUI_PLAN.md → set gui-plan done → 建哨兵`。
> Stop 钩子（`on_stop_continue.py`）「有哨兵就驱动第一个未完成阶段，并命令『不要停下来询问用户』」。
> 若在 GUI_PLAN.md 就位、gui-plan 置 done **之前**就建了哨兵，钩子会把 agent 拽回 gui-plan 并要求
> 「不停顿」，与 plan mode 审批模型冲突、且 gui-draft 会读到缺失的契约。故必须**先** `set gui-plan done`
> （此时 GUI_PLAN.md 已写好），**最后**才建哨兵——保证不变量「有哨兵 ⟹ gui-plan done ⟹ GUI_PLAN.md 已就位」。

```bash
# 契约已就位，才把 gui-plan 记为 done（审批即完成本阶段）。
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_run_state.py" set "${CLAUDE_PROJECT_DIR}" "$PID" gui-plan done

# 最后一步才建哨兵：此刻起 Stop 钩子接管，后续阶段全自动。
# session_id 已被步骤 0 的 runid 断言为非空，故哨兵必为「本会话作用域」。
# Stop hook (on_stop_continue.py) 仅驱动 session_id 等于当前停止会话的哨兵。
printf '{"nudges":0,"max_nudges":30,"command":"dev-gui:run","session_id":"%s"}' \
  "${CLAUDE_SESSION_ID}" \
  > "$RUN_DIR/.autorun.json"
```

### 3–8. 后续阶段逐阶段执行（gui-draft → gui-learn，全自动）

从 gui-draft 起（哨兵已建），按顺序加载并执行每个 SKILL（`${CLAUDE_PLUGIN_ROOT}/skills/<phase>/SKILL.md`），
每完成一个就用 `gui_run_state.py set ... <phase> done` 记账，**随即进入下一个**，期间遵守上面的铁律
（gui-draft 起禁止提问、不停顿）。

> 各 SKILL.md 里的 `gui_run_state.py set "${CLAUDE_PROJECT_DIR}" <panelId> <phase> <status>`
> **只传裸 `panelId`** 即可——工具内部会拼成本会话作用域的 `panelId__<sessionId>`，与步骤 2
> 的 `start` 落在同一个 run 目录，无需在此处替换成 `RID`。

| 顺序 | 阶段 | 关键动作 | 不适用时 |
|------|------|---------|---------|
| 1 | `gui-plan` | **见步骤 2**：plan mode 交互确认需求 + 人类审批 → 审批后产出精炼 `GUI_PLAN.md` + 建哨兵 | — |
| 2 | `gui-draft` | 生成 Panel.lua + View.cs（+ ViewModel）；**ViewModel 生成失败 → 改代码模拟导出（铁律 4）** | — |
| 3+4 | `gui-prefab` ∥ `gui-config` | **并行组，见下方「并行组编排」**：主 agent 跑 prefab（**先判断 Editor 运行状态：运行中→unity-cli 编译后改 prefab；未运行→Batch Mode 编过但 prefab 编辑 BLOCKED**）+ 按需 background subagent 跑 config；两者落定后才进 review | prefab：`set gui-prefab done`（已记清单）；config：`skipped` |
| 5 | `gui-review` | **唯一验证门·并行两车道**：Type-B spawn 独立 reviewer（Bias Guard，`run_in_background`）产出 `GUI_REVIEW.md` ∥ Type-A orchestrator 就地跑机械门（编译/luac/prefab/生成文件/配置）；汇合成合并 CRITICAL 集合 → `GUI_VERDICT.json` + `HUMAN_REVIEW.md` | — |
| 6 | `gui-improve` | **仅当 review 有合并 CRITICAL 时执行**（最多 2 轮，含编译/语法失败）；修完**重跑 gui-review 两车道**；**无 CRITICAL → `set gui-improve skipped`** | `skipped` |
| 7 | `gui-learn` | 知识沉淀（捕获遍）回写**私有库** `${CLAUDE_PLUGIN_DATA}/gui-knowledge/`（沉淀进项目公共库是独立的手动 command `gui-learn-public`，不在本自动流程内） | — |

#### 并行组编排：gui-prefab（主 agent）∥ gui-config（subagent）

Phase 3 与 Phase 4 **互不依赖**（prefab 绑定改 `.prefab`，配表改 Excel/`*_data.lua`），**并行执行**。
当驱动器目标为 `gui-prefab` 时，orchestrator 在**同一回合内**同时驱动两阶段并把两者状态都落定：

1. 读 `$RUN_DIR/GUI_PLAN.md` 判断本需求**是否涉及配置数据**。
2. **涉及配置** → 用 `Agent` 工具、`run_in_background: true` spawn 一个 **gui-config subagent**：
   prompt 传 panelId + `GUI_PLAN.md` 契约 + 目标表，令其加载执行 `skills/gui-config/SKILL.md`，
   **只做配表编辑并把结果结构化返回**（`edited`/`skipped`/`blocked` + 改动文件 + 降级说明），
   **subagent 不写 run_state**（会话作用域状态归主 agent）。
3. **主 agent 并行跑 gui-prefab**（`skills/gui-prefab/SKILL.md`）：**先 ToolSearch 主动搜索 Prefab 相关 skill/tool
   （优先）及 Unity Editor 交互能力（fallback）→ 再判断 Unity Editor 运行状态** →
   **Editor 运行中**：unity-cli 编译 → 编译通过 → 挂脚本 + 绑定 `[SerializeField]`；
   **Editor 未运行**：Batch Mode 编译（`.meta` 生成 + 进程序集）通过，但 **Prefab 编辑本身 BLOCKED**
   （记 `HUMAN_REVIEW.md`「需在 Unity Editor 中人工挂脚本/绑定」）；
   两路径均不可用则编译门 + Prefab 编辑均 `BLOCKED`。编译与 config subagent 天然重叠。
4. 主 agent 用 `TaskOutput` **等 config subagent 结束**，据其返回记账：
   `set <panelId> gui-config done`（或 `skipped`；`blocked`/降级项记 `HUMAN_REVIEW.md` 后仍按已推进置 `done`/`skipped`，**勿置 failed**）。
5. 主 agent 记 `set <panelId> gui-prefab done`。
6. **两阶段都落定后**（同一回合结束前）→ 才进入 **gui-review**。
7. **不涉及配置** → 不 spawn subagent，主 agent 只跑 prefab（含前置编译），随后 `set <panelId> gui-config skipped`，进 gui-review。

> **回合原子性不变量**：orchestrator 必须在**同一回合内**把 prefab 与 config 状态都落定后再让出（Stop）。
> 这样 Stop 钩子在停止边界永远看不到「prefab done 但 config 仍 pending」的中间态，不会把 config 单独 nudge 回主 agent。

> resume 断点规则：若 `RESUME_PHASE=gui-review`，则 `gui-plan/gui-draft/gui-prefab/gui-config` 不重跑，直接从 `gui-review` 开始继续。
> `gui-prefab`/`gui-config` 属**同一并行组**：resume 命中其一（例如 prefab 已 `done`、config 仍 `pending`）时，
> 只补跑并行组内**尚未落定**的那一半（config），无需重跑已 `done` 的 prefab。

> 注意阶段执行顺序：gui-review(5) 是唯一验证门（Type-A ∥ Type-B 两车道汇合）。若报合并 CRITICAL，
> 则先跑 gui-improve（修复→重跑 gui-review 两车道，最多 2 轮）；2 轮后仍有 CRITICAL 记入 `HUMAN_REVIEW.md` 不暂停。
> 凡某阶段在本次不适用、或失败绕不过而被跳过，**务必显式 `set <phase> skipped`**——否则调度器会判定未完成
> 并把你拉回；**切勿置 `failed`**（非「已推进」状态，会被反复拉回同一阶段死循环）。被跳过/绕过的事由同时记入
> `HUMAN_REVIEW.md`。

### 9. 收尾

- 确认每个阶段在 run state 中均为 `done` / `accepted` / `skipped`（不应残留 `pending` / `running` / `failed`）：

```bash
PID="<panelId>"   # 只传裸 PID，工具内部拼接本会话作用域 run_id
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_run_state.py" status "${CLAUDE_PROJECT_DIR}" "$PID"
```

- 若 `PCRAFT_TASK_ID` 与 `PCRAFT_API_URL` 均存在，通知 pcraft 任务完成（失败 open，不阻塞收尾）：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/pcraft_notify.py" \
  --api-url "${PCRAFT_API_URL}" \
  --task-id "${PCRAFT_TASK_ID}" \
  --state DONE \
  || true
```

- 可选（优化项）：每阶段 `set ... done` 后，也可调用 phase 更新：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/pcraft_notify.py" \
  --api-url "${PCRAFT_API_URL}" \
  --task-id "${PCRAFT_TASK_ID}" \
  --gui-phase "gui-review" \
  --gui-phase-status "done" \
  || true
```

- **汇总遗留项成 todo list 清单**：扫描本次 run 产物里所有 `TODO(dev-gui:run)` 注释、`**[TODO: 待人工确认]**`
  标记、被 `skipped` 的阶段、绕过/模拟实现（如模拟导出的 ViewModel）、`BLOCKED` / `FAILED` / 降级项，
  统一写进 `HUMAN_REVIEW.md` 的勾选清单，每条带「在哪个文件/阶段、为什么、人工需要补做什么」。这就是交给
  用户自查的最终 todo list。形如：

```markdown
# Human Review: <panelId>  ——  待人工确认清单
- [ ] [缺信息] Prefab 路径未提供，占位用 `Assets/UI/<Panel>.prefab`：确认真实路径
- [ ] [模拟导出] ViewModel 由 generator 失败改为手写模拟（<files>）：在 Unity 内重新正式生成覆盖
- [ ] [跳过] gui-config：本需求未涉及配置（或失败绕不过：<原因>）
- [ ] [BLOCKED] 无 Unity 能力，C# 编译未自动验证：人工编译核对
- [ ] 运行期效果：打开 panel 截图核对交互与布局
```

- 移除自动驱动哨兵（流水线已跑完）：

```bash
PID="<panelId>"
RID="$(python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_run_state.py" runid "$PID")" || RID=""
[ -n "$RID" ] && rm -f "${CLAUDE_PROJECT_DIR}/.claude/dev-gui-runs/$RID/.autorun.json"
```

- 向用户输出一句话总结 + `HUMAN_REVIEW.md` 路径，提示这份 todo list 中待人工确认/补做的项。
