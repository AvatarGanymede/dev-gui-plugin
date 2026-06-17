---
name: gui-draft
user-invocable: false
description: >-
  Atom Game GUI pipeline 第 2 阶段。生成 MVVM 代码（Panel.lua + View.cs + 如需的 ViewModel）。
  自包含的 MVVM 指引。在 gui-plan 产出 GUI_PRD.md 后使用。控制代码
  实现漂移（相对需求规格）。
---

# Phase 2: gui-draft — MVVM 代码生成

**职责**：自包含的 MVVM 代码生成。**控制：代码实现漂移。**
输入：`GUI_PRD.md` + `${CLAUDE_PLUGIN_DATA}/gui-knowledge/query_pack.md`。

> 动手前先读 `${CLAUDE_PLUGIN_ROOT}/shared-references/mvvm-contract.md`。

## 核心规则

- Panel (Lua) **写** ViewModel，View (C#) **只读**（单向数据流，靠 SharedArray 共享）。
- 需新增/改 ViewModel 属性 → 走严格 3-Phase：ViewModelDes → 生成 → View/Panel（见 mvvm-contract §3，**生成成功前禁写 Phase 3 代码**）。
- **禁止手改** `*_viewmodel.lua` / `*ViewModel.cs` / `AtomViewModelFactory.cs` / `ui_viewmodel_define.lua`（自动生成）。
- Panel：`<PanelName>Panel.lua` 继承 `UIBasePanel`；View：`<PanelName>View.cs` 继承 `BaseView`。
- **优先 AtomUI* 公共组件，避免裸 UGUI**（`AtomUIText`/`AtomUIImage`/`AtomUIButton`）。

## 模板（真实写法）

> 仍**先读目标目录同类现有 panel** 对齐命名/惯例。生命周期钩子与 API 见 mvvm-contract §4-§7。

```lua
-- Panel（Model 层）
local enum = require("framework.utils.enum")
local uiBasePanel = jn_require_ex("framework.ui.ui_base_panel")
local PanelNamePanel = DefineClass("PanelNamePanel", uiBasePanel.UIBasePanel)

UIMessageId = enum "UIMessageId" { "OnConfirmClick" }              -- 与 C# enum 同步（从 1）
local panelMessageHandler = { [UIMessageId.OnConfirmClick] = "onConfirmClick" }
function PanelNamePanel:getPanelMessageHandler() return panelMessageHandler end

function PanelNamePanel:prepareViewModel(panelData)
    self.rootViewModel.SomeProperty = panelData.someValue          -- 只写 ViewModel
end

function PanelNamePanel:onPanelClose()
    -- 取消 timer / 移除监听 / dispose 创建的 Lib（清理是你的责任）
end

function PanelNamePanel:onConfirmClick() end
```

```csharp
// View（表现层）
public class PanelNameView : BaseView
{
    private enum UIMessageId { OnConfirmClick = 1 }                // 与 Lua enum 完全一致

    [SerializeField] private AtomUIButton m_BtnConfirm;
    [SerializeField] private AtomUIText m_TxtTitle;

    private PanelNameViewModel m_VM;

    public override void Initialize(BaseViewModel viewModel)
    {
        if (viewModel is not PanelNameViewModel vm) return;
        m_VM = vm;
        InitializeView();
        InitializeEvents();
    }

    private void InitializeView()
    {
        m_TxtTitle.SetText(m_VM.SomeProperty.ToString());
    }

    private void InitializeEvents()
    {
        m_VM.RegisterPropertyChangeHandler<string>(PanelNameViewModel.SOMEPROPERTY, OnSomeChange);
        m_BtnConfirm.OnClick = OnBtnConfirmClick;                  // 非 onClick.AddListener
    }

    private void OnSomeChange(string v) { m_TxtTitle.SetText(v); }
    private void OnBtnConfirmClick() { SendUIMessage((int)UIMessageId.OnConfirmClick); }
    // 普通 View 无需 override Destroy() 退订——框架自动清理 PropertyChangeHandler
}
```

## 流程

1. 读 GUI_PRD.md + query_pack 相关坑点。
2. 读目标目录下**同类现有 panel** 与真实基类，对齐命名/生命周期/惯例。
3. 判断模式：列表 / 可复用组件 / 世界坐标跟踪等场景先查 `shared-references/patterns/`（决策树见 `patterns/README.md`）。
4. 生成 Panel.lua + View.cs（+ 走 3-Phase 处理 ViewModel 新增）。
5. 自检 Gate（见下）。
6. 记录状态：
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_run_state.py" set "${CLAUDE_PROJECT_DIR}" <panelId> gui-draft done
   ```

## Gate

- Panel 写的每个 ViewModel 属性 → View 中有对应读取/绑定（双向匹配）。
- 自动生成文件未被手改。
- 生命周期订阅↔退订配对。

→ 进入 **gui-prefab**。
