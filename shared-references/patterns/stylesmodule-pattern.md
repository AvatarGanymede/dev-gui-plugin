# StylesModule<TEnum> Pattern

Use `StylesModule<TEnum>` when the page needs a small number of mutually exclusive UI states and each state maps to a stable group of GameObjects.

## When to use

- Self / Shared page title variants
- Locked / Unlocked blocks
- Empty / Non-empty placeholders
- Any state where grouped node visibility is clearer than scattered `SetActive`

## Core rules

1. Add a dedicated enum for semantic states, not raw integers.
2. Each enum value maps to one prefab group in `m_Groups`.
3. `SwitchTo(...)` returns early when the target index equals `m_SelectedIndex`.
4. Because of rule 3, prefab default active state must already match the default selected index.

## Example

```csharp
private enum TitleState
{
    SelfResult,
    SharedResult,
}

[Serializable]
private class TitleStateStyles : StylesModule<TitleState> {}

[SerializeField, Required] private TitleStateStyles m_TitleStyles;

private void InitializeView()
{
    m_TitleStyles.SwitchTo(string.IsNullOrEmpty(m_ViewModel.OwnerName)
        ? TitleState.SelfResult
        : TitleState.SharedResult);
}
```

Prefab handoff:

- `SelfResult`: `TextTitle`, `NodeButtonShare`
- `SharedResult`: `TextTitleShare`
- default `m_SelectedIndex = 0`
- default active state must already be:
  - `TextTitle` visible
  - `NodeButtonShare` visible
  - `TextTitleShare` hidden

## Initialization-only state

If the state is decided once when opening the page and does not change later, switch once in `InitializeView()` and do not subscribe to property changes just for symmetry.

## Handoff requirement

If Claude cannot edit prefab in the current task, it must still hand off:

- enum name and state meaning
- group membership for each state
- required default selected index
- required default active state
