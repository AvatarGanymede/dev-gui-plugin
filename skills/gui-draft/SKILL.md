---
name: gui-draft
user-invocable: false
description: >-
  Atom Game GUI pipeline 第 2 阶段。生成 MVVM 代码（Panel.lua + View.cs + 如需的 ViewModel）。
  自包含的 MVVM 指引，不依赖外部 atomgui skill。在 gui-plan 产出 GUI_PRD.md 后使用。控制代码
  实现漂移（相对需求规格）。
---

# Phase 2: gui-draft — MVVM 代码生成

**职责**：自包含的 MVVM 代码生成。**控制：代码实现漂移。**
输入：`GUI_PRD.md` + `${CLAUDE_PLUGIN_DATA}/gui-knowledge/query_pack.md`。

> 动手前先读 `${CLAUDE_PLUGIN_ROOT}/shared-references/mvvm-contract.md`。

## 核心规则（内嵌，不引用 atomgui）

- Panel (Lua) **写** ViewModel，View (C#) **只读**（单向数据流）。
- 需新增/改 ViewModel 属性 → 走 3-Phase：ViewModelDes → 生成 → View/Panel（见 mvvm-contract §3）。
- **禁止手改** `*_viewmodel.lua` / `*ViewModel.cs`（自动生成文件）。
- Panel：`<PanelName>Panel.lua` 继承 `UIPanelBase`；View：`<PanelName>View.cs` 继承 `UIViewBase`。

## ⚠ 生命周期方法名以运行期真实基类为准

下列模板**仅示范结构**。**动手前先读真实 `UIPanelBase` / `UIViewBase`** 确认生命周期方法名——
本项目实际形如 `OnInstanceMethodIsEmpty`、`OnContentRefresh` 等，与通用 Unity 命名不同。
模板里的 `OnCreate`/`OnCreated`/`OnDestroy(ed)` 仅占位，**不要照抄**。

```lua
-- Panel 模板（结构示意）
local PanelNamePanel = Class("PanelNamePanel", UIPanelBase)

function PanelNamePanel:OnCreate()
    self.viewModel.someProperty = someValue   -- 只写 ViewModel
end

function PanelNamePanel:OnDestroy()
    -- 清理
end

return PanelNamePanel
```

```csharp
// View 模板（结构示意）
public class PanelNameView : UIViewBase
{
    [SerializeField] private Button _btnConfirm;
    [SerializeField] private TextMeshProUGUI _txtTitle;
    [SerializeField] private StylesModule<SomeEnum> _stylesModule;

    protected override void OnCreated()
    {
        _btnConfirm.onClick.AddListener(OnConfirmClick);   // 订阅
    }

    private void OnConfirmClick() { }

    protected override void OnDestroyed()
    {
        _btnConfirm.onClick.RemoveListener(OnConfirmClick); // 配对退订
    }
}
```

## 流程

1. 读 GUI_PRD.md + query_pack 相关坑点。
2. 读目标目录下**同类现有 panel** 与真实基类，对齐命名/生命周期/惯例。
3. 生成 Panel.lua + View.cs（+ 走 3-Phase 处理 ViewModel 新增）。
4. 自检 Gate（见下）。
5. 记录状态：
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_run_state.py" set "${CLAUDE_PROJECT_DIR}" <panelId> gui-draft done
   ```

## Gate

- Panel 写的每个 ViewModel 属性 → View 中有对应读取/绑定（双向匹配）。
- 自动生成文件未被手改。
- 生命周期订阅↔退订配对。

→ 进入 **gui-prefab**。
