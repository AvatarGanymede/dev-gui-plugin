# Data Binding Patterns

## RegisterPropertyChangeHandler API

Two overloads:
```csharp
// 2-arg: simple instance handler (preferred)
m_VM.RegisterPropertyChangeHandler<T>(int propertyId, Action<T> handler);

// 3-arg: target object + static delegate (for performance or CommonHandler)
m_VM.RegisterPropertyChangeHandler<T>(int propertyId, object obj, Action<object, T> handler);
```

**Register vs Set:** `RegisterPropertyChangeHandler` uses `Dictionary.Add()` — throws if key already exists. `SetPropertyChangeHandler` uses indexer — silently overwrites. Use `Set` in `UpdateView` methods that may be called multiple times; use `Register` in one-time `Initialize`.

**Unregister:** `m_VM.UnRegisterPropertyChangeHandler(int propertyId)` — removes the handler. For normal Views, the framework auto-cleans handlers on destroy — you do NOT need to manually unregister. Only use explicitly in special cases (e.g., re-binding to a different ViewModel mid-lifecycle).

## Basic Property Binding

```csharp
// Style 1: Non-static instance method (simplest, preferred)
m_VM.RegisterPropertyChangeHandler<int>(MyViewModel.CURRENTHP, OnHpChange);
private void OnHpChange(int newHp) { m_HpText.SetText(newHp.ToString()); }

// Style 2: Static delegate (avoids allocation)
private static Action<object, int> s_HpHandler =
    (o, v) => ((MyView)o).OnHpChange(v);
m_VM.RegisterPropertyChangeHandler(MyViewModel.CURRENTHP, this, s_HpHandler);

// Style 3: CommonHandler (built-in for standard operations)
m_VM.RegisterPropertyChangeHandler(MyViewModel.NAME, m_NameText,
    AtomUIText.CommonHandler.TextChangeHandler);
```

## SubViewModel Binding

```csharp
m_VM.RegisterPropertyChangeHandler<BaseViewModel>(
    MyViewModel.PLAYERINFO, OnPlayerInfoChange);

private void OnPlayerInfoChange(BaseViewModel v)
{
    m_SubView.BelongedPanelId = BelongedPanelId;
    m_SubView.Initialize(v);
}
```

## List Binding

```csharp
m_VM.RegisterPropertyChangeHandler<IList>(
    MyViewModel.ITEMS, OnItemsChanged);

private void OnItemsChanged(IList items)
{
    m_ItemList.Update(m_VM.Items);
}
```

## ViewModel Casting

Two ways to cast the ViewModel in `Initialize()`:

```csharp
// Pattern 1: is-not pattern (preferred)
public override void Initialize(BaseViewModel viewModel)
{
    if (viewModel is not MyViewModel vm) return;
    m_ViewModel = vm;
}

// Pattern 2: TryCastTo (safe cast with out parameter)
public override void Initialize(BaseViewModel viewModel)
{
    if (!viewModel.TryCastTo(out m_ViewModel)) return;
}

// Pattern 3: CastTo (throws if wrong type — use when type is guaranteed)
m_ViewModel = viewModel.CastTo<MyViewModel>();
```

## Custom Event System

Custom events are one-shot notifications (no data payload) separate from property changes. Useful when Lua needs to trigger a C# action that isn't tied to a specific property (e.g., "scroll to index", "play animation").

```csharp
// C# View — register handler
private const int SCROLL_TO_INDEX = -1;  // negative IDs common for custom events

m_VM.RegisterCustomEvent(SCROLL_TO_INDEX, OnScrollToIndex);
m_VM.SetCustomEventHandler(REFRESH_EVENT, OnRefresh);  // overwrite version

// Cleanup in Destroy()
m_VM.UnRegisterCustomEvent(SCROLL_TO_INDEX);
```

Custom events are triggered from the Lua side when ViewModel properties change. They complement property change handlers for scenarios where you need a "signal" rather than a "value change".

## Destroy() Override — When Needed

**Normal Views do NOT need to override `Destroy()` to unregister property change handlers** — the framework automatically cleans them up.

Override `Destroy()` only when you need to:
- Call `Destroy()` on SubViews (parent manages SubView lifecycle)
- Clean up custom resources (e.g., `UnRegisterCustomEvent`)

```csharp
// Example: only needed when View has SubViews or custom events
public override void Destroy()
{
    m_SubView?.Destroy();                             // SubView cleanup
    m_ViewModel?.UnRegisterCustomEvent(SCROLL_TO_INDEX); // custom event cleanup
    base.Destroy();
}
```

The framework calls `Destroy()` on the root View when the panel closes. For SubViews, the parent View must call `Destroy()` on them manually in its own `Destroy()`.

## Available CommonHandler Delegates

| Component | Handler | Type |
|-----------|---------|------|
| `AtomUIText.CommonHandler` | `TextChangeHandler` | `Action<object, string>` |
| `AtomUIText.CommonHandler` | `TextColorChangeHandler` | `Action<object, string>` |
| `AtomUIImage.CommonHandler` | `SetImageHandler` | `Action<object, long>` |
| `AtomUIImage.CommonHandler` | `SetGreyHandler` | `Action<object, bool>` |
| `AtomUIImage.CommonHandler` | `SetAlphaHandler` | `Action<object, float>` |
| `AtomUIImage.CommonHandler` | `SetColorHandler` | `Action<object, string>` |
| `AtomUIImage.CommonHandler` | `SetFillAmountHandler` | `Action<object, float>` |
| `AtomUIButton.CommonHandler` | `InteractableChangeHandler` | `Action<object, bool>` |
| `AtomUIToggle.CommonHandler` | `ToggleChangeHandler` | `Action<object, bool>` |
| `AtomUITextInput.CommonHandler` | `TextHandler` | `Action<object, string>` |
| `AtomUITextInput.CommonHandler` | `PlaceHolderHandler` | `Action<object, string>` |
| `CommonHandler` (top-level) | `s_SetGameObjectActiveHandler` | `Action<object, bool>` |
| `CommonHandler` (top-level) | `s_SetComponentEnableHandler` | `Action<object, bool>` |
| `CommonHandler` (top-level) | `s_AnchoredPositionSetHandler` | `Action<object, BaseViewModel>` |
| `CommonHandler` (top-level) | `s_SetCanvasGroupAlphaHandler` | `Action<object, float>` |
