# AtomGUI 进阶模式库

> `gui-draft` 生成代码、`gui-review` 审查时**按需深读**的模式文档。
> 基础数据流 / 生命周期 / 绑定见 `shared-references/mvvm-contract.md`；本目录只放进阶场景。

## 模式选择决策树

```
需要列表 / 集合？
├── 多项需滚动 → AtomScrollRect（虚拟化、对象池）   → scroll-rect-pattern.md
├── 少量全显示不滚动 → ListModule                  → listmodule-pattern.md
└── 不是列表 → 往下看

需要可复用组件？
├── 跨多个 Panel 复用 → UILib（Lua+C#，框架级事件路由） → uilib-pattern.md
├── 仅同 Panel 内复用 → SubView（纯 C#，父 View 管生命周期） → subview-pattern.md
└── 不复用 → 直接内联进 View

需要世界坐标跟踪（HUD 标记）？
└── 是 → World-tracking（父 View 在 LateUpdate 驱动）    → world-tracking-pattern.md

对接全屏页面？
└── 是 → FullscreenBasicView/Lib（壳层管通用关闭）       → fullscreen-basic-pattern.md

需要互斥显隐态？
└── 是 → StylesModule<TEnum>（别散落成多处 SetActive）   → stylesmodule-pattern.md

部分动态文本但要保留 prefab 样式 / 富文本？
└── 先决定 format 来源（prefab vs Excel/配表）           → static-format-text-pattern.md
```

## 文档清单

| 文档 | 用途 | 关键约束 |
|------|------|---------|
| `scroll-rect-pattern.md` | 大型可滚动虚拟化列表 | cell 池化，只有可见 cell 在内存 |
| `listmodule-pattern.md` | 小型非滚动动态列表 | Template 必须 inactive |
| `uilib-pattern.md` | 跨 Panel 复用组件（Lua+C#） | eventId ∈ [0,255]；创建者必 `dispose()` |
| `subview-pattern.md` | 同 Panel 内 C# 复用组件 | 父 View 须在自身 `Destroy()` 调 SubView `Destroy()` |
| `world-tracking-pattern.md` | 世界坐标→屏幕跟踪 HUD | 更新逻辑必须在**父 View 的 LateUpdate**，禁放 ItemView |
| `fullscreen-basic-pattern.md` | 全屏壳层落地 | 纯关闭交给壳层，勿重复接本地 close |
| `stylesmodule-pattern.md` | 互斥显隐态切换 | prefab 默认 `m_SelectedIndex` 与默认激活态一致 |
| `static-format-text-pattern.md` | prefab 持有 format 模板 | 用户确认来源后再用，勿默认写死代码 |
| `data-binding-patterns.md` | 绑定进阶 / 自定义事件 / CommonHandler | — |
