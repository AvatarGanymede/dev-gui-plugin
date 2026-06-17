# World-to-Screen Position Tracking Pattern

For UI elements that must follow a 3D world position (e.g., HUD markers, name plates, scan indicators), project `WorldPos` onto the UI canvas each frame in the **parent View's `LateUpdate`**.

**Key dependencies:**
- `GameCameraModeManager.Instance.MainCamera` — the main 3D camera
- `GameUIManager.Instance.UICamera` — the UI overlay camera
- `RectTransformUtility.ScreenPointToLocalPointInRectangle` — converts screen coords to UI local coords
- `Vector3ViewModel` — auto-generated ViewModel for `Vector3`, supports implicit cast to `Vector3`

## CRITICAL: Update Logic Must Live in Parent View, NOT in ItemView

**Problem:** When an item goes off-screen, its GameObject is deactivated via `SetActive(false)`. Once a GameObject is inactive, Unity **stops calling all MonoBehaviour callbacks** (`Update`, `LateUpdate`, etc.) on it. This means the item can never detect that it should become visible again — it is permanently hidden after going off-screen for even a single frame.

**Solution:** The parent View (which always remains active) must drive the screen-position update loop for all child items. The ItemView only exposes a public `UpdateScreenPosition()` method; it does NOT have its own `LateUpdate`.

## Item View (No LateUpdate — position driven by parent)

```csharp
using Atom.UI.Runtime.Components;
using AtomGUI.Runtime;
using Game.CameraControl;
using Game.UI.ViewModel;
using UnityEngine;

public class WorldTrackedItemView : BaseView
{
    [SerializeField] private AtomUIText m_NameText;

    private MyItemViewModel m_VM;
    private RectTransform m_RectTransform;

    public void UpdateView(MyItemViewModel vm, int index)
    {
        m_VM = vm;
        m_NameText.SetText(vm.ItemName);

        if (m_RectTransform == null)
        {
            m_RectTransform = transform as RectTransform;
        }

        UpdateScreenPosition();
    }

    // Called by parent View's LateUpdate — NOT by this object's own LateUpdate
    public void UpdateScreenPosition()
    {
        if (m_VM == null || m_VM.WorldPos == null)
        {
            return;
        }

        var mainCamera = GameCameraModeManager.Instance.MainCamera;
        if (mainCamera == null)
        {
            return;
        }

        // Vector3ViewModel has implicit cast to Vector3
        Vector3 worldPos = m_VM.WorldPos;

        // Hide if behind camera
        var viewportPos = mainCamera.WorldToViewportPoint(worldPos);
        if (viewportPos.z < 0)
        {
            gameObject.SetActive(false);
            return;
        }

        gameObject.SetActive(true);

        // Project world position to screen, then to UI local coordinates
        var screenPoint = mainCamera.WorldToScreenPoint(worldPos);
        var parentRect = m_RectTransform.parent as RectTransform;
        if (parentRect != null)
        {
            RectTransformUtility.ScreenPointToLocalPointInRectangle(
                parentRect, screenPoint, GameUIManager.Instance.UICamera, out var localPoint);
            m_RectTransform.localPosition = localPoint;
        }
    }
}
```

## Parent View (Drives position updates for all items)

```csharp
public class WorldTrackedParentView : BaseView
{
    [SerializeField] private MyItemList m_ItemList;

    private MyParentViewModel m_VM;

    public override void Initialize(BaseViewModel viewModel)
    {
        if (viewModel is not MyParentViewModel vm) return;
        m_VM = vm;

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

    // Parent drives screen-position updates for ALL items every frame
    private void LateUpdate()
    {
        foreach (var view in m_ItemList.Views)
        {
            view.UpdateScreenPosition();
        }
    }
}
```

## Conversion Pipeline

```
World Position (Vector3)
    │
    ▼  MainCamera.WorldToViewportPoint()
Viewport Position (z < 0 = behind camera → hide)
    │
    ▼  MainCamera.WorldToScreenPoint()
Screen Position (pixels)
    │
    ▼  RectTransformUtility.ScreenPointToLocalPointInRectangle(parentRect, screenPos, UICamera)
UI Local Position → assign to RectTransform.localPosition
```

## Important Notes

- **Position update logic must be in the parent View's `LateUpdate`**, not in the ItemView — because `SetActive(false)` disables all MonoBehaviour callbacks on the item, making it permanently invisible if the item drives its own updates
- **Use `LateUpdate`**, not `Update`, to ensure camera has finished moving before projecting
- **Null-check `WorldPos`** — the sub-ViewModel may not be bound yet on the first frame
- **Null-check `MainCamera`** — camera may not exist during scene transitions
- **Behind-camera check** (`viewportPos.z < 0`) — without this, objects behind the camera appear mirrored on screen
- `Vector3ViewModel` supports implicit cast to `Vector3`, `Vector2`, and `Vector4`
