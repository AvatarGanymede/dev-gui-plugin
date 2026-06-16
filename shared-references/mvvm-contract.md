# MVVM 一致性契约

> Atom Game GUI 的 MVVM 数据流规范。`gui-draft` 生成代码、`gui-review` 审查、`gui-verify`
> 验证均以本契约为基准。**本文是「示意契约」——生命周期方法名与基类 API 以运行期真实
> `UIPanelBase` / `UIViewBase` 为准**，动手前先读真实基类确认。

## 1. 数据流方向（单向）

```
Panel (Lua)  ──写──>  ViewModel  ──读──>  View (C#)
   逻辑层               数据契约层           表现层
```

- **Panel（Lua）**：业务逻辑，**只写** ViewModel 属性，不直接操作 UI 节点。
- **ViewModel**：Panel 与 View 之间的数据契约；属性是双方约定的字段。
- **View（C#）**：表现层，**只读** ViewModel，把数据绑定到 Prefab 节点；处理 UI 事件回调。

> 核心不变式：**Panel 写的每个 ViewModel 属性，View 中必须有对应的读取/绑定**；
> 反之 View 读的属性，Panel（或配置）必须有来源。这是 `gui-review` 的「MVVM 一致性」维度
> 和 `gui-verify` Type-A 的检查点。

## 2. 命名约定

| 角色 | 文件名 | 基类 |
|------|--------|------|
| Panel | `<PanelName>Panel.lua` | `UIPanelBase` |
| View | `<PanelName>View.cs` | `UIViewBase` |
| ViewModel (Lua) | `<panelname>_viewmodel.lua` | 自动生成 |
| ViewModel (C#) | `<PanelName>ViewModel.cs` | 自动生成 |

- ViewModel 属性：跟随项目既有命名惯例（动手前先看同目录现有 panel）。
- View 字段：`[SerializeField] private <Type> _<camelCase>;`（前缀下划线，按项目惯例确认）。

## 3. 3-Phase 变更流程（新增/改 ViewModel 属性时）

需要新增或修改 ViewModel 属性，**不能手改生成文件**，须走三步：

1. **ViewModelDes**：在 ViewModel 描述/定义源（项目约定的 des 源）声明属性。
2. **生成**：跑项目的 ViewModel 生成流程，产出 `*_viewmodel.lua` / `*ViewModel.cs`。
3. **View/Panel**：在 Panel 中写属性、在 View 中读/绑定属性。

> 若运行环境未加载相应生成能力 → 在 `HUMAN_REVIEW.md` 标注「需手工跑 ViewModel 生成」，
> 不在管线中途停顿。

## 4. 禁止事项

- ❌ **禁止手改自动生成文件**：`*_viewmodel.lua`、`*ViewModel.cs`。
  - 例外说明：`*_data.lua`（配表导出产物）**不是** MVVM 生成文件，`gui-config` 阶段
    故意镜像写入（模拟导表），见 `verification-gates.md` 与 plan §四。
- ❌ Panel 直接操作 Prefab 节点 / 持有 View 的 UI 引用。
- ❌ View 反向写 ViewModel（破坏单向数据流）。
- ❌ 在 View 的 `Update` 中做 `GetComponent` / 字符串拼接 / 重复查找（性能反模式，见 patterns）。

## 5. 生命周期配对（以真实基类为准）

- `On*Create*` 中订阅事件 / 绑定监听 ↔ `On*Destroy*` 中退订 / 移除监听，**必须配对**。
- `[SerializeField]` 引用在首次使用前应判空（空安全，见 `prefab-binding-contract.md`）。
- 真实方法名形如 `OnInstanceMethodIsEmpty` / `OnContentRefresh` 等，**与通用 Unity 命名不同**，
  动手前务必读基类。

## 6. 与各阶段的映射

| 阶段 | 用本契约做什么 |
|------|---------------|
| gui-draft | 按 §1–§5 生成 Panel/View，保证写↔读匹配 |
| gui-review | 审查「MVVM 一致性」「生命周期正确性」「空安全」维度 |
| gui-verify | Type-A：未改生成文件、绑定数量匹配；Type-B：交互逻辑 |
