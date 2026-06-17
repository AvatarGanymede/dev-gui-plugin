# ListModule Pattern (Non-Scrolling Dynamic List)

Use `ListModule<TView, TViewModel>` (`Game.UI.Modules`) for **non滚动列表**场景——即列表项数量较少、无需虚拟化回收、全部实例化显示的动态列表。框架自动处理实例化、更新和销毁。

**适用场景：** HUD 标记点、少量 Tag 标签、固定数量的状态图标等不需要滚动的动态列表
**不适用场景：** 大量数据的滚动列表（应使用 ScrollRect + 虚拟化方案）

**Location:** `client/Assets/Scripts/Game/UI/Modules/ListModule.cs`

## ListModule Base Class API

```csharp
// ListModule<TView, TViewModel> key members:
[Required] public RectTransform Content;   // Container for instantiated items
[Required] public TView Template;          // Prefab template (should be inactive in scene)
public List<TView> Views { get; }          // Currently active view instances

public void Update(IReadOnlyList<TViewModel> vm);  // Sync views to match ViewModel list
```

Calling `Update(vmList)` will:
1. Destroy excess views if `vmList.Count < Views.Count`
2. Update existing views via `UpdateView()`
3. Instantiate new views via `CreateView()` if `vmList.Count > Views.Count`

## Step 1: Create a ListModule Subclass

Create a concrete subclass to pass `BelongedPanelId` and call item-specific `UpdateView`:

```csharp
using System;
using System.Collections.Generic;
using Game.UI.Modules;
using Game.UI.ViewModel;

namespace Game.UI.View.MyFeature
{
    [Serializable]
    public class MyItemList : ListModule<MyItemView, MyItemViewModel>
    {
        public int BelongPanelId;

        protected override void UpdateView(MyItemView view, int index, IReadOnlyList<MyItemViewModel> vmList)
        {
            base.UpdateView(view, index, vmList);
            view.BelongedPanelId = BelongPanelId;
            view.UpdateView(vmList[index], index);
        }
    }
}
```

## Step 2: Create Item View

Each item View receives its ViewModel and index via `UpdateView`:

```csharp
public class MyItemView : BaseView
{
    private enum UIMessageId
    {
        OnItemClick = 1,
    }

    [SerializeField] private AtomUIText m_NameText;
    [SerializeField] private AtomUIText m_PriceText;

    private MyItemViewModel m_VM;
    private int m_Index;

    public void UpdateView(MyItemViewModel vm, int index)
    {
        m_VM = vm;
        m_Index = index;
        m_NameText.SetText(vm.Name);
        m_PriceText.SetText(vm.Price.ToString());
    }

    public void OnItemClick()
    {
        SendUIMessage((int)UIMessageId.OnItemClick, m_Index);
    }
}
```

## Step 3: Wire Up in Parent View

The parent View serializes the ListModule and drives it from ViewModel list changes:

```csharp
public class MyParentView : BaseView
{
    [SerializeField] private MyItemList m_ItemList;

    private MyParentViewModel m_VM;

    public override void Initialize(BaseViewModel viewModel)
    {
        if (viewModel is not MyParentViewModel vm) return;
        m_VM = vm;

        // Pass panelId so items can SendUIMessage to Lua
        m_ItemList.BelongPanelId = BelongedPanelId;
        InitializeView();
        InitializeEvents();
    }

    private void InitializeView()
    {
        if (m_VM.Items != null)
        {
            m_ItemList.Update(m_VM.Items);
        }
    }

    private void InitializeEvents()
    {
        m_VM.RegisterPropertyChangeHandler<IList>(MyParentViewModel.ITEMS, OnItemsChanged);
    }

    private void OnItemsChanged(IList items)
    {
        m_ItemList.Update(m_VM.Items);
    }
}
```

## Step 4: Lua Panel Side

```lua
function MyPanel:prepareViewModel(panelData)
    self.rootViewModel.Items = self:createCustomViewModelList(uiViewModelDefine.MyItem)
end

function MyPanel:updateItems(dataList)
    local items = self.rootViewModel.Items
    items:clear()
    for _, data in ipairs(dataList) do
        local vm = self:createViewModel(uiViewModelDefine.MyItem)
        vm.Name = data.name
        vm.Price = data.price
        items:add(vm)
    end
    items:update()  -- triggers OnItemsChanged in C# View
end
```

## Prefab Setup

```
ParentView (GameObject)
├── ParentView.cs (attached)
└── ItemContainer (child GameObject)
    ├── RectTransform (drag to m_ItemList.Content)
    └── ItemTemplate (child GameObject, SetActive(false))
        └── MyItemView.cs (attached, drag to m_ItemList.Template)
```

**Key points:**
- Template should be **inactive** in the scene (the framework activates clones)
- Content is the `RectTransform` parent under which items are instantiated
- The `[Serializable]` attribute on the ListModule subclass is required for Inspector serialization
