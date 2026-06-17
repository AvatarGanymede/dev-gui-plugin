# SubView Pattern

For reusable UI components (nested panels, fixed sub-sections, etc.):

1. Create ViewModel for the SubView
2. Create View class inheriting from `BaseView`
3. **Use SubView as serialized field in parent View (drag in Inspector)**
4. Parent View manages SubView lifecycle and initialization
5. **Parent propagates `BelongedPanelId` before calling Initialize**

```csharp
public class ParentView : BaseView
{
    // SubView as serialized field - drag the child GameObject with SubView attached
    [SerializeField] private PlayerInfoSubView m_PlayerInfoSubView;
    [SerializeField] private ItemListSubView m_ItemListSubView;

    private ParentViewModel m_ViewModel;

    public override void Initialize(BaseViewModel viewModel)
    {
        if (viewModel.TryCastTo(out m_ViewModel))
        {
            InitializeView();
            InitializeEvents();
        }
    }

    private void InitializeView()
    {
        // Propagate BelongedPanelId BEFORE calling Initialize
        m_PlayerInfoSubView.BelongedPanelId = BelongedPanelId;
        m_PlayerInfoSubView.Initialize(m_ViewModel.PlayerInfo);

        m_ItemListSubView.BelongedPanelId = BelongedPanelId;
        m_ItemListSubView.Initialize(m_ViewModel.ItemList);
    }

    private void InitializeEvents()
    {
        // Listen for SubViewModel changes to re-initialize SubView
        m_ViewModel.RegisterPropertyChangeHandler<BaseViewModel>(
            ParentViewModel.PLAYERINFO, OnPlayerInfoChange);
    }

    private void OnPlayerInfoChange(BaseViewModel newVM)
    {
        // Re-initialize SubView when SubViewModel is replaced
        m_PlayerInfoSubView.BelongedPanelId = BelongedPanelId;
        m_PlayerInfoSubView.Initialize(newVM);
    }

    public override void Destroy()
    {
        m_PlayerInfoSubView.Destroy();
        m_ItemListSubView.Destroy();
        base.Destroy();
    }
}
```

```csharp
// SubView class
public class PlayerInfoSubView : BaseView
{
    private const int BTN_EDIT_CLICK = 1;

    [SerializeField] private AtomUIText m_PlayerNameText;
    [SerializeField] private AtomUIText m_LevelText;
    [SerializeField] private AtomUIButton m_BtnEdit;

    private PlayerInfoViewModel m_ViewModel;

    // Standard Initialize - BelongedPanelId is already set by parent
    public override void Initialize(BaseViewModel viewModel)
    {
        if (viewModel.TryCastTo(out m_ViewModel))
        {
            m_PlayerNameText.SetText(m_ViewModel.PlayerName);
            m_LevelText.SetText(m_ViewModel.Level.ToString());

            m_BtnEdit.OnClick = OnBtnEditClick;
        }
    }

    private void OnBtnEditClick()
    {
        // SubView sends message directly to Lua Panel via its BelongedPanelId
        SendUIMessage(BTN_EDIT_CLICK, m_ViewModel.PlayerName);
    }
}
```

**Prefab Structure:**
```
ParentView (GameObject)
├── ParentView.cs (attached)
├── PlayerInfoPanel (child GameObject)
│   └── PlayerInfoSubView.cs (attached, dragged to ParentView.m_PlayerInfoSubView)
└── ItemListPanel (child GameObject)
    └── ItemListSubView.cs (attached, dragged to ParentView.m_ItemListSubView)
```

**Key points:**
- `BelongedPanelId` is a **public field** on `BaseView` (`[NonSerialized] public int BelongedPanelId`)
- Parent must set `childView.BelongedPanelId = BelongedPanelId` **before** calling `Initialize`
- Without propagation, SubView's `SendUIMessage` routes to panel ID 0 (incorrect)
- Parent must call `Destroy()` on SubViews in its own `Destroy()` override
- SubView lifecycle is managed by parent View, not by the framework
