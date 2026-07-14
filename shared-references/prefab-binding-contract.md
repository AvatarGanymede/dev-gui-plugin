# Prefab 绑定完整性契约

> `gui-prefab` 编辑、`gui-review` 的 **Type-A 车道**（orchestrator 核实：Prefab 节点存在 /
> 绑定数量匹配）的基准。**运行时若未加载 Prefab 读写能力，相关检查判
> `NOT_APPLICABLE` / `BLOCKED`，转人工，禁止凭推测报 CRITICAL。**

## 1. `[SerializeField]` 绑定检查清单

View.cs 中每个 `[SerializeField]` 字段，在 Prefab 中都必须有对应绑定节点：

- [ ] 把 `<PanelName>View.cs` 挂到 Prefab **根节点**。
- [ ] 每个 `Button` / `TextMeshProUGUI` / `Image` / `RawImage` / 列表容器字段都已拖入对应节点。
- [ ] 字段类型与节点组件类型匹配（Button↔Button、文本↔TMP 等）。
- [ ] 没有「孤儿绑定」：Prefab 上挂了引用但 View 已删除该字段。
- [ ] 没有「悬空字段」：View 有 `[SerializeField]` 但 Prefab 未绑定（=空引用崩溃源）。

> **数量不变式**：View 中 `[SerializeField]` 字段数 == Prefab 中实际绑定数。
> 这是 `gui-review` Type-A 车道「绑定数量匹配」门。

## 2. 节点命名约定

- 节点名跟随项目既有惯例（动手前看同类 Prefab）。
- 字段 `_btnConfirm` 一般对应节点 `BtnConfirm` / `btn_confirm` 等 —— 以项目惯例为准。

## 3. StylesModule / ListModule 配置规范

### StylesModule<TEnum>

- [ ] 分组节点齐全，覆盖 `TEnum` 的每个枚举值。
- [ ] 设置默认 `m_SelectedIndex`（否则运行期可能空指针，见 patterns）。
- [ ] 枚举值与分组节点一一对应，无遗漏/错位。

### ListModule

- [ ] Template 节点保持 **inactive**（运行期由 ListModule 实例化，激活态会多出一个静态项）。
- [ ] Template 子节点的绑定字段齐全。
- [ ] 列表数据源来自 ViewModel（单向数据流）。

## 4. 绑定方式约定（AtomGUI）

- **固定 UI 控件用 `[SerializeField]` 引用，在 prefab 上绑定** —— **禁止** `transform.Find(...)` 或路径查找。
  路径查找仅对真正运行期动态生成的节点可接受。
- 必绑字段用 `[Required]`（Sirenix.OdinInspector）标注，可免运行期判空；仅 `[Optional]` 字段需判空。
- 语义上独立、含 2-4 个固定绑定节点的区域，可低优先级用 `[Serializable] struct` 聚合
  （如「奖励摘要区」=图标+数量+说明）；节点只有 1 个或边界不稳定时直接用普通 `[SerializeField]`。

> **Claude 禁读写 prefab 资源**：不打开/检查/编辑任何 `*.prefab`。需要序列化绑定或层级信息时，
> 让程序员/用户提供字段名或手动处理 prefab 侧（见 §7 工具自适应）。

## 5. 静态文本

- 静态格式文本保留在 **Prefab 文本节点**，不要硬编码进 C#/Lua（便于本地化与美术调整）。
- 动态文本走 ViewModel 属性 → View 写入。
- 混合静态/动态：先决定 format 来源（prefab 模板 vs Excel/配表），见 `patterns/static-format-text-pattern.md`。

## 6. 常见绑定遗漏场景

| 场景 | 后果 | 检查 |
|------|------|------|
| 新增 `[SerializeField]` 忘了拖节点 | 运行期 NullReference | §1 悬空字段 |
| StylesModule 未设默认 index | 首帧空指针 | §3 |
| ListModule Template 是 active | 多一个静态空项 | §3 |
| 删字段没解绑 Prefab | 残留引用、误导 | §1 孤儿绑定 |
| 类型不匹配（拖错组件） | 转换异常 / 行为错误 | §1 类型匹配 |
| 用 `transform.Find` 找固定控件 | 重构脆弱、隐藏依赖 | §4 用 `[SerializeField]` |

## 7. 工具自适应

- 运行时**已加载** Prefab 读写能力 → 读 Prefab hierarchy 核实 §1–§6。
- **未加载** → `gui-review` 对应 Type-A 门判 `BLOCKED`，并写入 `HUMAN_REVIEW.md`
  「需在 Unity 中人工核对 Prefab 绑定」，管线继续。
