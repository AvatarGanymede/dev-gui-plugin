# ScrollRect Pattern (Virtualized Scroll List)

Use `AtomScrollRect` for large, scrollable lists that need virtualization (inventories, player lists, item shops). Built on FancyScrollView — only visible cells are instantiated, with automatic pooling and recycling.

**Location:** `client/Assets/Scripts/Game/UI/Components/ScrollView/AtomScrollRect.cs`

## When to Use

| Scenario | Use |
|----------|-----|
| Large scrollable list (10+ items, unbounded) | AtomScrollRect |
| Small fixed list (all visible, no scroll) | ListModule |
| Grid layout with scrolling | AtomScrollGrid (same API as AtomScrollRect) |

## AtomScrollRect API

```csharp
// Setup (call in Initialize, before first UpdateScroll)
m_ScrollRect.SetUpdateCellHandler(Action<AtomScrollRectCell, object> handler);
m_ScrollRect.SetNavigationSelectHandler(Action<int, bool, AtomScrollRectCell> handler);
m_ScrollRect.SetTemplateIdGetter(Func<object, int> getter);  // multi-template only

// Data
m_ScrollRect.UpdateScroll(IEnumerable items);  // refresh with new data

// Navigation & Selection
m_ScrollRect.ScrollToIndex(int index, float duration, float alignment = 0.5f, Action onComplete = null);
m_ScrollRect.SelectAndAutoScroll(int index, bool alignToHead);
m_ScrollRect.SelectAndAutoScroll(int index, float alignment, float duration = 0f);
m_ScrollRect.NavigationAutoScroll(int index, bool alignToHead);  // scrolls only if not visible

// Cell access
AtomScrollRectCell cell = m_ScrollRect.GetCell(int index);  // null if not visible
```

## AtomScrollRectCell

Each cell wraps a `BaseView` and handles visibility/recycling:

```csharp
public class AtomScrollRectCell
{
    public BaseView View { get; }           // The item View component
    public Selectable Selectable { get; }   // For UI navigation

    // Lifecycle (managed by framework):
    // Initialize() → find View component
    // UpdateContent(object data) → invoke UpdateCellHandler
    // SetVisible(bool) → Reset ViewModel when hidden
    // Select() → register navigation
    // Destroy() → unregister navigation
}
```

## Step 1: Create Item View (for scroll cells)

Item Views for scroll cells use `UpdateView()` instead of `Initialize()` because cells are recycled. Use `SetPropertyChangeHandler` (not `Register`) since the same View instance binds to different ViewModels over its lifetime:

```csharp
public class MyItemView : BaseView
{
    private enum UIMessageId
    {
        OnItemClick = 1,
    }

    [SerializeField] private AtomUIText m_NameText;
    [SerializeField] private AtomUIImage m_Icon;

    private MyItemViewModel m_VM;

    // Called on each recycle — use Set (not Register) for reusable views
    public void UpdateView(MyItemViewModel vm)
    {
        m_VM = vm;
        m_NameText.SetText(vm.Name);
        m_Icon.SetImage(vm.Icon);

        // SetPropertyChangeHandler overwrites silently (safe for recycled views)
        vm.SetPropertyChangeHandler<string>(MyItemViewModel.NAME, UpdateName);
        vm.SetPropertyChangeHandler<long>(MyItemViewModel.ICON, UpdateIcon);
    }

    private void UpdateName(string name) { m_NameText.SetText(name); }
    private void UpdateIcon(long icon) { m_Icon.SetImage(icon); }

    public void OnItemClick()
    {
        SendUIMessage((int)UIMessageId.OnItemClick, m_VM.Index);
    }
}
```

## Step 2: Wire Up in Parent View

```csharp
public class MyListView : BaseView
{
    [SerializeField] private AtomScrollRect m_ScrollRect;

    private MyListViewModel m_VM;

    public override void Initialize(BaseViewModel viewModel)
    {
        if (viewModel is not MyListViewModel vm) return;
        m_VM = vm;

        // 1. Set cell update handler (before first UpdateScroll)
        m_ScrollRect.SetUpdateCellHandler(OnUpdateCell);

        // 2. Bind to ViewModel list changes
        m_VM.RegisterPropertyChangeHandler<IList>(MyListViewModel.ITEMS, OnItemsChanged);

        // 3. Initial display
        if (m_VM.Items != null)
        {
            m_ScrollRect.UpdateScroll(m_VM.Items);
        }
    }

    private void OnUpdateCell(AtomScrollRectCell cell, object data)
    {
        var view = cell.View as MyItemView;
        if (data is MyItemViewModel itemVM)
        {
            view.BelongedPanelId = BelongedPanelId;
            view.UpdateView(itemVM);
        }
    }

    private void OnItemsChanged(IList items)
    {
        m_ScrollRect.UpdateScroll(m_VM.Items);
    }
}
```

## Step 3: Lua Panel Side

```lua
function MyPanel:prepareViewModel(panelData)
    -- Create CustomViewModelList for scroll items
    self.rootViewModel.Items = self:createCustomViewModelList(uiViewModelDefine.MyItem)
end

function MyPanel:refreshItems(dataList)
    local items = self.rootViewModel.Items
    items:clear()

    for i, data in ipairs(dataList) do
        local vm = self:createViewModel(uiViewModelDefine.MyItem)
        vm.Index = i
        vm.Name = data.name
        vm.Icon = data.icon
        items:add(vm)
    end

    items:update()  -- triggers C# PropertyChangeHandler → UpdateScroll
end
```

## Multi-Template Support

For lists with different item types (e.g., headers + items, different card layouts):

```csharp
// In Initialize, set template ID getter
m_ScrollRect.SetTemplateIdGetter(data => {
    if (data is HeaderViewModel) return 0;  // template index 0
    return 1;  // template index 1 for items
});
```

In the Inspector, enable `m_IsMultipleTemplate` and add templates to the `m_Templates` list. Each template index corresponds to its position in this list.

## Gamepad/Keyboard Navigation

```csharp
// Register navigation handler
m_ScrollRect.SetNavigationSelectHandler((index, selected, cell) => {
    // index: selected item index
    // selected: true = focused, false = unfocused
    // cell: the AtomScrollRectCell instance
    if (selected)
    {
        OnItemFocused(index);
    }
});

// Programmatic navigation (from Lua Custom Event)
m_ScrollRect.SelectAndAutoScroll(m_VM.SelectIndex, m_VM.IsNext);
```

Item Views can implement `IScrollSelectHandler` to receive navigation callbacks:

```csharp
public class MyItemView : BaseView, IScrollSelectHandler
{
    public void OnNavigationSelect()
    {
        // Called when gamepad selects this item
    }
}
```

## Prefab Setup

```
ParentView (GameObject)
├── ParentView.cs (attached)
└── ScrollView (GameObject)
    ├── AtomScrollRect (component)
    ├── Scroller (component) — Vertical or Horizontal
    └── CellTemplate (child, with AtomScrollRectCell + MyItemView)
```

The cell template is set via `m_CellPrefab` in the AtomScrollRect Inspector. Unlike ListModule, the template does NOT need to be manually deactivated — AtomScrollRect manages its own pooling.

## Key Differences from ListModule

| Aspect | AtomScrollRect | ListModule |
|--------|----------------|-----------|
| Cell recycling | Yes (pooled) | No (all instantiated) |
| Template support | Single + Multi-template | Single only |
| Navigation | Built-in gamepad support | Manual implementation |
| Update handler | `SetUpdateCellHandler` | Override `UpdateView()` |
| Binding style | `SetPropertyChangeHandler` (recycled) | `RegisterPropertyChangeHandler` (one-time) |
| Use case | Inventory, long lists | HUD markers, few items |
