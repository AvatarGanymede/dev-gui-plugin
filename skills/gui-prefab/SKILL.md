---
name: gui-prefab
user-invocable: false
description: >-
  Atom Game GUI pipeline 第 3 阶段。把 View.cs 挂到 Prefab 并绑定 [SerializeField] 引用。
  自包含的 Prefab 编辑指引，不依赖外部 edit-prefab skill。在 gui-draft 生成 View.cs 后使用。
  控制 Prefab 绑定漂移。
---

# Phase 3: gui-prefab — Prefab 编辑

**职责**：自包含的 Prefab 编辑。**控制：Prefab 绑定漂移。**
输入：gui-draft 输出的 `View.cs` + ui_data.lua 的 prefab 路径。

> **执行位置与并行**：本阶段**跑在主 agent**。gui-config（Phase 4）与本阶段**并行**——
> 若本需求涉及配置数据，由 orchestrator 把 gui-config **spawn 到 subagent** 与本阶段同时跑；
> 不涉及配置则直接 `skipped`。两阶段都落定后才进入 gui-review（编排细节见 `commands/run.md`）。

> 动手前先读 `${CLAUDE_PLUGIN_ROOT}/shared-references/prefab-binding-contract.md`。

## 编辑内容

- 把 `<PanelName>View.cs` 挂到 Prefab **根节点**。
- 绑定每个 `[SerializeField]` 引用（按钮、文本、图片、列表节点）。
- `StylesModule<TEnum>`：分组节点齐全 + 设默认 `m_SelectedIndex`。
- `ListModule`：Template 节点保持 **inactive**。
- 静态格式文本保留在 Prefab 文本节点。

## 工具使用（不硬绑定 MCP）

- 运行时**已加载** unity-prefab 等 Prefab 能力 → 用它读写 Prefab 完成绑定。
- **未加载** → 不臆造绑定；在 `HUMAN_REVIEW.md` 标注「需在 Unity 中人工挂脚本/绑定」，
  本阶段判降级，管线继续。

## 流程

0. **前置 C# 编译（硬门，改 prefab 之前必做）**：先触发 Unity C# 编译，让 gui-draft 产出的
   `<PanelName>View.cs`（及本次新增/改动的 ViewModel）**进程序集**——只有编译通过、MonoScript 生成
   稳定 GUID 后，才能把 View 脚本挂到 Prefab 根节点、并让 `[SerializeField]` 字段在 Inspector 可见可绑。
   **编译通过后才进入第 1 步**；编译报错先按报错修 draft 产物再重编。缺编译能力（Unity 未开 / 无对应刷新能力）
   → 该门判 `BLOCKED` 记入 `HUMAN_REVIEW.md`，不阻塞（措辞同 `gui-draft` 4b/4d 两道编译门）。
1. 列出 View.cs 中所有 `[SerializeField]` 字段（名称 + 类型）。
2. 对照 Prefab hierarchy 逐一绑定（或记录待人工绑定项）。
3. 校验 prefab-binding-contract 的清单（悬空字段 / 孤儿绑定 / 类型匹配 / 数量一致）。
4. 记录状态（**由 orchestrator 在主 agent 侧执行**）：
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_run_state.py" set "${CLAUDE_PROJECT_DIR}" <panelId> gui-prefab done
   ```

## Gate

- **前置编译门**：改 prefab 前 C# 已编译通过（View/ViewModel 进程序集）；缺编译能力则该门 `BLOCKED`，记入清单，不阻塞。
- View.cs 中每个 `[SerializeField]` 在 Prefab 中都有对应绑定节点（数量一致）。
  缺 Prefab 能力时该 Gate → `BLOCKED`，记入清单，不阻塞。

→ gui-config（Phase 4）由 orchestrator **并行 spawn 于 subagent**（本需求不涉及配置则 `skipped`）。
**prefab 与 config 两阶段均落定后** → 进入 **gui-review**。
