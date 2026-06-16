---
name: gui-prefab
description: >-
  Atom Game GUI pipeline 第 3 阶段。把 View.cs 挂到 Prefab 并绑定 [SerializeField] 引用。
  自包含的 Prefab 编辑指引，不依赖外部 edit-prefab skill。在 gui-draft 生成 View.cs 后使用。
  控制 Prefab 绑定漂移。
---

# Phase 3: gui-prefab — Prefab 编辑

**职责**：自包含的 Prefab 编辑。**控制：Prefab 绑定漂移。**
输入：gui-draft 输出的 `View.cs` + ui_data.lua 的 prefab 路径。

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

1. 列出 View.cs 中所有 `[SerializeField]` 字段（名称 + 类型）。
2. 对照 Prefab hierarchy 逐一绑定（或记录待人工绑定项）。
3. 校验 prefab-binding-contract 的清单（悬空字段 / 孤儿绑定 / 类型匹配 / 数量一致）。
4. 记录状态：
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_run_state.py" set "${CLAUDE_PROJECT_DIR}" <panelId> gui-prefab done
   ```

## Gate

View.cs 中每个 `[SerializeField]` 在 Prefab 中都有对应绑定节点（数量一致）。
缺 Prefab 能力时该 Gate → `BLOCKED`，记入清单，不阻塞。

→ 进入 **gui-config**（按需，可跳过）。
