---
name: gui-config
description: >-
  Atom Game GUI pipeline 第 4 阶段（按需，可跳过）。编辑 design/tables 下的 Excel 配置源表，
  并镜像改动到对应 *_data.lua（模拟导表，零人工中断）。自包含的配置表编辑指引，不依赖外部
  edit-excel skill。仅当功能涉及配置数据时使用。控制配置数据漂移。
---

# Phase 4: gui-config — 配置表编辑（按需，可跳过）

**职责**：自包含的配置表编辑。**控制：配置数据漂移（Excel 源表 vs lua data 不同步）。**
若本需求不涉及配置数据 → **跳过**：
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_run_state.py" set "${CLAUDE_PROJECT_DIR}" <panelId> gui-config skipped
```

## 规则（模拟导表，零人工中断）

1. 改 `design/tables/` 下的 **Excel 源表**（真正的真相源）。
2. **同时镜像改动到对应 `*_data.lua` 行**，模拟「导表成功导出」，使运行期与后续阶段立即可见
   新配置。镜像须严格对齐 GDE 导出格式（按行定位、同字段同值）。
3. 区分两类「生成文件」，勿混淆：
   - `*_data.lua`（配表导出产物）—— 本阶段**故意镜像写入**，不是禁区。
   - `*_viewmodel.lua` / `*ViewModel.cs`（MVVM 生成）—— 仍**禁止**手改。

## 工具使用（不硬绑定 MCP）

- 运行时**已加载** excel-config / excel-mcp 等 → 用之读写 Excel 源表。
- **未加载** → 在 `HUMAN_REVIEW.md` 标出「需手工配表」，本阶段降级，管线继续。

## Gate

Excel 源表与对应 `*_data.lua` 改动**一致**（同字段、同值），运行期可读到新配置。

> ⚠ 正式导表仍需人工：手写的 `*_data.lua` 是**模拟产物**，正式 GDE 导表会覆盖它。
> 故「确认 Excel 配置正确并正式导表」列入 `HUMAN_REVIEW.md`（gui-verify 末），
> **绝不在管线中途停顿**。

记录状态后 → 进入 **gui-review**：
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_run_state.py" set "${CLAUDE_PROJECT_DIR}" <panelId> gui-config done
```
