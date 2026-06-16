# Prefab 绑定完整性契约

> `gui-prefab` 编辑、`gui-review`（Prefab 绑定维度）、`gui-verify`（Type-A：Prefab 节点存在 /
> 绑定数量匹配）的基准。**运行时若未加载 Prefab 读写能力（如 unity-prefab MCP），相关检查
> 判 `NOT_APPLICABLE` / `BLOCKED`，转人工，禁止凭推测报 CRITICAL。**

## 1. `[SerializeField]` 绑定检查清单

View.cs 中每个 `[SerializeField]` 字段，在 Prefab 中都必须有对应绑定节点：

- [ ] 把 `<PanelName>View.cs` 挂到 Prefab **根节点**。
- [ ] 每个 `Button` / `TextMeshProUGUI` / `Image` / `RawImage` / 列表容器字段都已拖入对应节点。
- [ ] 字段类型与节点组件类型匹配（Button↔Button、文本↔TMP 等）。
- [ ] 没有「孤儿绑定」：Prefab 上挂了引用但 View 已删除该字段。
- [ ] 没有「悬空字段」：View 有 `[SerializeField]` 但 Prefab 未绑定（=空引用崩溃源）。

> **数量不变式**：View 中 `[SerializeField]` 字段数 == Prefab 中实际绑定数。
> 这是 `gui-verify` Type-A「绑定数量匹配」门。

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

## 4. 静态文本

- 静态格式文本保留在 **Prefab 文本节点**，不要硬编码进 C#/Lua（便于本地化与美术调整）。
- 动态文本走 ViewModel 属性 → View 写入。

## 5. 常见绑定遗漏场景

| 场景 | 后果 | 检查 |
|------|------|------|
| 新增 `[SerializeField]` 忘了拖节点 | 运行期 NullReference | §1 悬空字段 |
| StylesModule 未设默认 index | 首帧空指针 | §3 |
| ListModule Template 是 active | 多一个静态空项 | §3 |
| 删字段没解绑 Prefab | 残留引用、误导 | §1 孤儿绑定 |
| 类型不匹配（拖错组件） | 转换异常 / 行为错误 | §1 类型匹配 |

## 6. 工具自适应

- 运行时**已加载** unity-prefab 等 Prefab 能力 → 读 Prefab hierarchy 核实 §1–§5。
- **未加载** → `gui-verify` 对应 Type-A 门判 `BLOCKED`，并写入 `HUMAN_REVIEW.md`
  「需在 Unity 中人工核对 Prefab 绑定」，管线继续。
