# Static Format Text Pattern

Use this pattern when a text block contains a stable visual template owned by the prefab, while only part of the content is dynamic at runtime.

Typical examples:

- `{0}的占卜结果`
- `"{0}"`
- `“{0}”`
- rich text wrappers such as `<style="Highlight">{0}</style>`

## Decision first

Before implementing, confirm with the user which system should own the text format:

- `Excel / text config` when content should be managed by config, localization, or planning workflows
- `Prefab static format` when UI / interaction roles need to adjust punctuation, wrappers, or rich text style directly in the prefab

Do not silently choose between these two owners for the user.

## When to use prefab-owned format

Choose this pattern when:

- the dynamic part is small and the surrounding format is stable
- the wrapper punctuation or style may be tuned by UI roles
- the prefab already contains the intended visual text template
- the page is not expecting runtime language switching through config in this task

## Core rules

1. Keep the full template text in the prefab, including punctuation and rich text tags.
2. In C#, cache the initial `text` into a hidden `Format` field from `OnEnable()`.
3. Set `ForceStatic = true` in `OnValidate()` for each `AtomUIText` using this pattern.
4. Update runtime content with `string.Format(format, dynamicValue)` instead of overwriting the whole text with plain content.
5. If multiple text nodes use this pattern, give each one its own format cache field.

## Example

```csharp
[SerializeField, Required] private AtomUIText m_TitleShare;
[SerializeField, HideInInspector] private string m_TitleShareFormat = "";

[SerializeField, Required] private AtomUIText m_ResultText;
[SerializeField, HideInInspector] private string m_ResultTextFormat = "";

#if UNITY_EDITOR
private void OnValidate()
{
    if (m_TitleShare)
    {
        m_TitleShare.ForceStatic = true;
    }

    if (m_ResultText)
    {
        m_ResultText.ForceStatic = true;
    }
}
#endif

private void OnEnable()
{
    // Must run after AtomUIText.Awake
    if (string.IsNullOrEmpty(m_TitleShareFormat))
    {
        m_TitleShareFormat = m_TitleShare.text;
    }

    if (string.IsNullOrEmpty(m_ResultTextFormat))
    {
        m_ResultTextFormat = m_ResultText.text;
    }
}

private void InitializeView()
{
    m_TitleShare.text = string.Format(m_TitleShareFormat, m_ViewModel.OwnerName);
    m_ResultText.text = string.Format(m_ResultTextFormat, m_ViewModel.Result);
}
```

## Prefab requirements

- The prefab text must already contain the intended format string such as `{0}的占卜结果`
- The serialized `AtomUIText` reference must point to the text node that owns that format
- `ForceStatic` should be persisted on the prefab, not only set temporarily in code

## Handoff requirement

If Claude cannot edit the prefab in the current task, it must still hand off:

- which text nodes use this pattern
- what each prefab-side format string should be
- which serialized fields need to bind to those nodes
- that `ForceStatic` must be enabled for those `AtomUIText` components
