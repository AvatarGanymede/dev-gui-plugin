# UILib Pattern (Reusable Lua+C# Component)

UILib is a reusable UI component that bundles its own ViewModel, C# View, and Lua logic. Unlike SubView (which is purely a C# code organization pattern), UILib has framework-level support for event routing and lifecycle management.

## When to Use UILib vs SubView

| Feature | SubView | UILib |
|---------|---------|-------|
| C# Base Class | `BaseView` | `BaseLibView` |
| Lua Base Class | None (logic in Panel) | `UIBaseLib` |
| Event Routing | Via parent's `BelongedPanelId` | Auto-remapped via `runtimeViewModelId * 256 + eventId` |
| Lua Logic | Lives in Panel | Self-contained in `ui_lib_xxx.lua` |
| Lifecycle | Managed by parent View | Auto-tracked and disposed by Panel |
| Best For | Fixed sub-sections of a View | Reusable components across multiple Panels |

## Architecture

```
┌─────────────────────┐     ┌──────────────────────┐
│  BaseLibView (C#)   │◄────│  ViewModel (C#+Lua)  │
│  - Initialize(vm)   │     │  (auto-generated)    │
│  - SendUIMessage()  │     └──────────────────────┘
│    (auto-remapped)  │              ▲
└─────────────────────┘              │ Write Only
                                     │
                          ┌──────────────────────┐
                          │  UIBaseLib (Lua)      │
                          │  - registerEvent()   │
                          │  - createLib()       │
                          │  - createViewModel() │
                          └──────────────────────┘
                                     ▲
                                     │ createLib()
                          ┌──────────────────────┐
                          │  Panel (Lua)         │
                          │  self:createLib(cls, vm)│
                          └──────────────────────┘
```

## Step 1: Define ViewModelDes (for the Lib's ViewModel)

```csharp
namespace Game.UI.ViewModelDes
{
    [ViewModel("common", "common_item_viewmodel")]
    public class CommonItem
    {
        public int ItemId;
        public long Icon;
        public string Name;
        public int Num;
        public bool ShowNum;
        public long QualityColor;
    }
}
```

## Step 2: Create C# LibView (inherits BaseLibView)

```csharp
using AtomGUI.Runtime;
using Game.UI.ViewModel;
using Atom.UI.Runtime.Components;
using UnityEngine;

namespace Game.UI.View
{
    public class CommonItemLibView : BaseLibView
    {
        // Event IDs must be in [0, 255]
        private enum UIMessage
        {
            OnItemClick = 1,
            OnItemLongTouch = 2,
        }

        [SerializeField] private AtomUIImage m_Icon;
        [SerializeField] private AtomUIText m_NameText;
        [SerializeField] private AtomUIText m_NumText;
        [SerializeField] private AtomUIButton m_Button;

        // Access typed ViewModel via m_InternalViewModel
        public CommonItemViewModel ViewModel => (CommonItemViewModel)m_InternalViewModel;

        // BaseLibView.Initialize(vm) sets m_InternalViewModel
        // Override to add binding and setup
        public override void Initialize(BaseViewModel viewModel)
        {
            base.Initialize(viewModel);  // MUST call base
            InitializeView();
            InitializeEvents();
        }

        private void InitializeView()
        {
            m_Icon.SetImage(ViewModel.Icon);
            m_NameText.SetText(ViewModel.Name);
            m_NumText.SetText(ViewModel.Num.ToString());
            m_NumText.gameObject.SetActive(ViewModel.ShowNum);
        }

        private void InitializeEvents()
        {
            m_Button.OnClick = OnItemClick;
        }

        private void OnItemClick()
        {
            // SendUIMessage auto-remaps eventId using runtimeViewModelId
            SendUIMessage((int)UIMessage.OnItemClick);
        }
    }
}
```

**Key differences from BaseView:**
- Inherits `BaseLibView`, not `BaseView`
- Access ViewModel via `m_InternalViewModel` (protected field set by `Initialize`)
- `SendUIMessage` automatically remaps event IDs — no need to manually handle `BelongedPanelId`
- Event IDs **must be in [0, 255]** (8-bit range, because `uniqueEventId = runtimeViewModelId * 256 + eventId`)

## Step 3: Create Lua UILib (inherits UIBaseLib)

The canonical pattern is a **two-step lifecycle**:
1. **`ctor(belongedPanel, viewModel)`** — structural setup: register events, create sub-VMs and sub-libs
2. **`initialize(...)`** — data-driven setup: populate ViewModel with actual data

**Note:** `initialize` is a naming **convention**, not a framework method. Some libs use `simpleInit` or other names. The framework only enforces `ctor` and `dispose`.

```lua
local uiBaseLib = jn_require_ex("framework.ui.ui_base_lib")

local CommonItemLib = DefineClass("CommonItemLib", uiBaseLib.UIBaseLib)

-- Event listener mapping: eventId -> method name
local EVENT_LISTENER = {
    [1] = "onItemClick",
    [2] = "onItemLongTouch",
}

-- ctor: structural setup — register events here (NOT in initialize)
function CommonItemLib:ctor(belongedPanel, viewModel)
    uiBaseLib.UIBaseLib.ctor(self, belongedPanel, viewModel)
    for eventId, action in pairs(EVENT_LISTENER) do
        self:registerEvent(eventId, bdFunctor(self, action))
    end
end

-- initialize: data-driven setup (convention, not framework-enforced)
function CommonItemLib:initialize(itemInfo, args)
    self.showPopTips = args and args.showPopTips or false
    self:initializeViewModel(itemInfo)
end

function CommonItemLib:dispose()
    -- Unregister all events before base dispose
    for eventId, _ in pairs(EVENT_LISTENER) do
        self:unRegisterEvent(eventId)
    end
    uiBaseLib.UIBaseLib.dispose(self)
end

function CommonItemLib:initializeViewModel(itemInfo)
    local itemConfig = itemData.data[itemInfo.itemId]
    self.viewModel.ItemId = itemInfo.itemId
    self.viewModel.Icon = itemConfig.icon or 0
    self.viewModel.Name = itemConfig.name
    self.viewModel.Num = itemInfo.count or 0
    self.viewModel.ShowNum = true
end

function CommonItemLib:onItemClick()
    if self.showPopTips then
        bd.uiDataProxy.commonProxy:triggerItemTips(self.viewModel.ItemId, false)
    end
end

function CommonItemLib:onItemLongTouch()
    if self.showPopTips then
        bd.uiDataProxy.commonProxy:triggerItemTips(self.viewModel.ItemId, true)
    end
end
```

**Key points:**
- Inherits `uiBaseLib.UIBaseLib`
- Constructor receives `(belongedPanel, viewModel)` automatically from factory
- `self.viewModel` is the ViewModel instance (set by UIBaseLib ctor)
- `self.belongedPanel` is the owning Panel instance
- **Register events in `ctor`**, not in `initialize` — this is the canonical pattern
- `registerEvent(eventId, action)` — action must be a **function** (use `bdFunctor`), not a string
- Must `unRegisterEvent` in `dispose()` to clean up

## Step 4: Use Lib in Panel

```lua
local uiViewModelDefine = jn_require_ex("framework.ui.ui_viewmodel_define")
local CommonItemLib = jn_require_ex("ui.common.common_item_lib").CommonItemLib

function MyPanel:prepareViewModel(panelData)
    -- Create ViewModel for the lib
    local itemVM = self:createViewModel(uiViewModelDefine.CommonItem)
    -- Create lib instance (auto-tracked for disposal)
    local lib = self:createLib(CommonItemLib, itemVM)
    -- Initialize with data
    lib:initialize({ itemId = 1001, count = 5 }, { showPopTips = true })
    -- Assign ViewModel to parent's field so C# View can bind
    self.rootViewModel.ItemSlot = itemVM
end
```

## UIBaseLib API Reference

| Method | Description |
|--------|-------------|
| `self.viewModel` | The Lib's ViewModel instance |
| `self.belongedPanel` | The owning Panel instance |
| `self:registerEvent(eventId, action)` | Register event handler (eventId: 0-255, action: function) |
| `self:unRegisterEvent(eventId)` | Unregister event handler |
| `self:createLib(libClass, viewModel, ...)` | Create a nested sub-lib (delegates to Panel) |
| `self:createViewModel(modelDef)` | Create a tracked ViewModel (delegates to Panel) |
| `self:createCustomViewModelList(modelDef)` | Create a tracked ViewModel list (delegates to Panel) |
| `self:createVector2/3/4(vec)` | Create vector ViewModel (delegates to Panel) |
| `self:createColor(vec)` | Create color ViewModel (delegates to Panel) |
| `self:registerInputActions(handlers, target)` | Register input action handlers |
| `self:cleanInputActions(target)` | Clean up input action handlers |

| `self:createShortcutKeyLib(keyId, allowClick)` | Convenience: creates CommonKeyTip VM + lib + initialize (returns `viewModel, lib`) |

## createShortcutKeyLib Convenience API

`createShortcutKeyLib(keyId, allowClick)` is a convenience method that creates a `CommonKeyTip` ViewModel, a `CommonKeyTipLib`, and calls `initialize` — all in one step. Returns **two values**: `(viewModel, lib)`.

```lua
-- Typical usage — only capture viewModel (lib is auto-tracked)
self.rootViewModel.UseKey = self:createShortcutKeyLib(BAG_USE_ITEM_KEY)

-- When you need the lib reference too:
local vm, lib = self:createShortcutKeyLib(SKIP_KEY)
lib:setUseProgressBar(true)
self.rootViewModel.SkipKeyTip = vm
```

## TriggerCustomEvent (Lua → C# only)

When Lua updates lib ViewModel and needs C# View to react immediately (beyond normal property-change binding), use `TriggerCustomEvent` to send a one-shot notification from Lua to C#:

```lua
-- In Lua lib, after updating ViewModel:
AtomGUI.Runtime.AtomUIManager.Instance:TriggerCustomEvent(
    self.viewModel.runtimeViewModelId, LUA_CALL_CSHARP_REFRESH)
```

- This is a **Lua → C# only** mechanism — C# cannot trigger events back to Lua this way
- Custom event IDs can be **negative** (convention: negative IDs for system-level events)
- C# View handles via custom event override (specific to each `BaseLibView` subclass)

## Nesting Libs

A UILib can create sub-libs using `self:createLib()`. Sub-libs created this way are auto-tracked by the owning Panel for disposal — the parent lib does **not** need to manually dispose sub-libs.

```lua
function MyLib:initialize(data)
    local subVM = self:createViewModel(uiViewModelDefine.SubComponent)
    local subLib = self:createLib(SubComponentLib, subVM)
    subLib:initialize(data.subData)
    self.viewModel.SubComponent = subVM
end
```

**Note:** `createLib` and `createViewModel` called from a UILib delegate to the owning Panel's methods, so all created resources are tracked at the Panel level and disposed together when the Panel closes.

## Real Examples in Codebase

| Lua Lib | C# View | Purpose |
|---------|---------|---------|
| `ui/common/common_item_lib.lua` | (generic item view) | Base item display component |
| `ui/common_bag_item/common_bag_item_lib.lua` | `BattleInvCommonItemLibView.cs` | Bag item with drag, discard |
| `ui/common/common_key_tip_lib.lua` | `CommonKeyTipView.cs` | Keyboard/gamepad key tip |
| `ui/fashion/fashion_grid_lib.lua` | `FashionGridView.cs` | Fashion grid item |
| `ui/create_role/create_role_name_lib.lua` | `CreateRoleNameLibView.cs` | Character name input |
