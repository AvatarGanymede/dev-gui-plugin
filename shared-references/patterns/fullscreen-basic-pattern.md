# FullscreenBasic Pattern

Use this pattern when a page already embeds `FullscreenBasicView` on the C# side and `FullscreenBasicLib` on the Lua side.

## When to use

- Fullscreen page only needs the common top bar / close behavior
- Close action does not carry extra page-specific business logic
- The page still needs its own business buttons, but not its own close pipeline

## Core rule

If fullscreen shell already owns plain close behavior, do not keep a duplicate local close path in the page View / Panel.

- C# View should not keep an extra `m_CloseButton`
- `UIMessageId` should not keep `OnCloseClick`
- Lua `panelMessageHandler` should not map a second close event

This avoids two sources of truth for closing the same page.

## Example

```csharp
private enum UIMessageId
{
    OnShareClick = 1,
}

[SerializeField, Required] private FullscreenBasicView m_FullscreenBasic;
[SerializeField, Required] private AtomUIButton m_ShareButton;

public override void Initialize(BaseViewModel viewModel)
{
    if (!viewModel.TryCastTo(out m_ViewModel))
    {
        return;
    }

    base.Initialize(viewModel);
    m_FullscreenBasic.Initialize(m_ViewModel, this);
    m_ShareButton.OnClick = OnShareClick;
}

private void OnShareClick()
{
    SendUIMessage((int)UIMessageId.OnShareClick);
}
```

```lua
local UIMessageId = enum "UIMessageId" {
    "OnShareClick",
}

local panelMessageHandler = {
    [UIMessageId.OnShareClick] = "onShareClick",
}

function DivinationResultPanel:getPanelMessageHandler()
    return panelMessageHandler
end
```

## Keep a local close event only when

- Close button needs extra confirmation, analytics, or business checks
- The page has a second close entrance that is not owned by `FullscreenBasic`

If so, make that business meaning explicit instead of treating it as the default close path.
