# MVVM 一致性契约（AtomGUI）

> Atom Game 的 AtomGUI 是一套**轻量 MVVM-like** 框架，刻意与标准 MVVM 有差异。
> `gui-draft` 生成代码、`gui-review` 审查、`gui-verify` 验证均以本契约为基准。
> 动手前仍建议读目标目录下**同类现有 panel** 对齐项目最新惯例。

## 1. 架构与数据流（单向）

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    View     │◄────│  ViewModel  │◄────│    Model    │
│   (C#)      │     │ (C# + Lua)  │     │   (Lua)     │
│  BaseView   │     │ SharedArray │     │ UIBasePanel │
└─────────────┘     └─────────────┘     └─────────────┘
     读                  数据契约                写
```

- **Panel（Lua / Model）**：业务逻辑，**只写** ViewModel，不直接操作 UI 节点。
- **ViewModel**：Panel 与 View 的数据契约；通过**共享内存 SharedArray** 共享，不是消息传递。
- **View（C#）**：表现层，**只读** ViewModel，绑定到 Prefab 节点；通过 `SendUIMessage` 上报 UI 事件。

**四条铁律：**
- **只有 Lua Model 能改 ViewModel，C# View 只读。**
- 每个 Panel 是**单例** —— 不能同时打开两个相同 PanelId 的 panel。
- Panel ≠ View：Panel = Lua 逻辑，View = C# 表现。一个 Panel 对应一个 RootView + 一个 root ViewModel。
- 核心不变式：**Panel 写的每个 ViewModel 属性，View 中必须有对应读取/绑定**；反之 View 读的属性，Panel（或配置）必须有来源。这是 `gui-review`「MVVM 一致性」维度与 `gui-verify` Type-A 的检查点。

## 2. 命名约定与目录

| 角色 | 文件名 | 基类 | 位置 |
|------|--------|------|------|
| ViewModelDes | 程序员定义 | — | `client/Assets/Scripts/Game/UI/ViewModelDes/` |
| ViewModel (C#) | `<Name>ViewModel.cs` | 自动生成 | `client/Assets/Scripts/Game/UI/ViewModel/` |
| ViewModel (Lua) | `<name>_viewmodel.lua` | 自动生成 | `code/LuaScripts/client/ui/{module}/` |
| Panel (Lua) | `<PanelName>Panel.lua` | **`UIBasePanel`** | `code/LuaScripts/client/ui/{module}/` |
| View (C#) | `<PanelName>View.cs` | **`BaseView`** | `client/Assets/Scripts/Game/UI/View/` |

- ViewModel 属性命名跟随项目既有惯例（先看同目录现有 panel）。
- 生成的 ViewModel 常量为**全大写**：`MyViewModel.CURRENTHP`、`MyViewModel.PLAYERINFO`。
- View 字段惯例：`[SerializeField] private AtomUIText m_HpText;`（`m_` 前缀，按项目惯例确认）。

## 3. 3-Phase 变更流程（新增/改 ViewModel 属性时）

需要新增/修改 ViewModel 属性时，生成文件**优先用工具导出、不优先手改**，须走严格三阶段（顺序门，不可跳过/乱序）：

```
Phase 1: 仅改 ViewModelDes ──⛔GATE──> Phase 2: 生成 ──⛔GATE──> Phase 3: View+Panel
```

- **Phase 1**：编辑 `ViewModelDes/*.cs` 增/删/改字段。**此阶段不碰任何其他文件。**
- **Phase 2（硬门）**：用 unity-cli 生成 ViewModel。
  - 生成/刷新前**先查 PlayMode 状态**，不要猜。若处于 PlayMode 且需退出，**先征求用户确认**再退出。
  - 仅当 Unity 需导入改动的 `.cs` 时才 refresh；纯 Lua 改动**不需要** refresh。
  - generator 入口（项目本地）：`Game.UI.ViewModelDes.CodeGen.ViewModelCodeGenerator.GenerateViewModel();`
    （文件 `client/PackageRepo/com.jngame.atom-gui/Editor/CodeGen/ViewModelCodeGenerator.cs`）。
  - **不要**凭记忆猜 Unity CLI `exec` 语法，先看 `cs.py exec -h` 确认。
  - 生成产物：C# `*ViewModel.cs`（常量）、Lua `*_viewmodel.lua`（属性名→ID 映射）、`AtomViewModelFactory.cs`、`ui_viewmodel_define.lua`。
  - **生成产物就绪前禁止进入 Phase 3**（C# 常量与 Lua 映射此前不存在，提前写会编译错误 / Lua 静默失败）；
    无论是工具导出成功、还是导出失败后改用手改补齐（见下方例外），产物齐全后方可进 Phase 3。
  - **reconcile 路径推算**：从 `[ViewModel("group","lua_filename")]` 推出
    `code/LuaScripts/client/ui/{group}/{lua_filename}.lua` 与 `.../ViewModel/{ClassName}ViewModel.cs`，
    全局文件 `AtomViewModelFactory.cs`、`ui_viewmodel_define.lua` 每次必更新。记录这些路径供 reconcile 用。
- **Phase 3**：编辑 C# View（引用 `MyViewModel.NEWPROP`）+ Lua Panel（设 `self.rootViewModel.NewProp`）。

> **硬规则：优先工具导出，导出失败才手改。**
> 1. **首选**：用工具（unity-cli / generator 等）正式导出生成 ViewModel 文件。能用工具就**不要**手改。
> 2. **导出失败 / 工具不可用 / 不能退 PlayMode → 允许手改补齐**（**不卡管线、不优先**）：按上面的 reconcile
>    路径推算，手写本应由 generator 产出的内容——`*ViewModel.cs` 常量、`*_viewmodel.lua` 属性名→ID 映射，
>    并在 `AtomViewModelFactory.cs`、`ui_viewmodel_define.lua` 补对应条目（仿照同文件里现有条目的写法）。
>    每处加 `// TODO(模拟导出): 工具导出失败手改，待工具正式重新导出覆盖`（Lua 用 `--`），并汇总进 `HUMAN_REVIEW.md`。
>    手改补齐后**可继续 Phase 3**；实在写不出（如无法定位现有条目格式）才将本步 `skipped` 并记 TODO。
> 3. 手改是**降级兜底**，不是常态：手改产物视为待复核，正式工具重新导出会覆盖它（记入 `HUMAN_REVIEW.md`）。

## 4. 在 Panel 中创建 ViewModel

**始终用 UIBasePanel 方法，禁用 factory 直建（会内存泄漏）：**

```lua
-- 正确：被框架追踪、自动销毁
self.rootViewModel.SubVM     = self:createViewModel(uiViewModelDefine.PlayerInfo)
self.rootViewModel.StringList = self:createViewModel(uiViewModelDefine.StringList)  -- 基础类型 list
self.rootViewModel.VMList    = self:createCustomViewModelList(uiViewModelDefine.PlayerInfo)

-- 错误：内存泄漏
self.rootViewModel.SubVM = bd.uiManager.vmFactory:createViewModel(modelDef)
```

- 基础类型 list defines（`ui_viewmodel_define.lua`）：`IntList`/`StringList`/`BoolList`/`FloatList`/`LongList`/`DoubleList`。
- **list 改动后必调 `update()`**：`add()`/`remove()`/`removeAt()`/`clear()` 之后 `list:update()` 才会通知 C# View。
- **禁止给 ViewModel 实例加自定义字段**（VM 只应含 ViewModelDes 定义的字段）。自定义数据存 Panel 自身字段（如 `self.itemLibs`）。

## 5. 事件与数据绑定

**事件 ID 用 enum 在 C#/Lua 双边同步（均从 1 开始，必须完全一致）：**

```csharp
private enum UIMessageId { OnSettingBtnClick = 1, OnInputSubmit }
SendUIMessage((int)UIMessageId.OnSettingBtnClick);   // 支持 0-5 个泛型参数
```
```lua
UIMessageId = enum "UIMessageId" { "OnSettingBtnClick", "OnInputSubmit" }
local panelMessageHandler = { [UIMessageId.OnSettingBtnClick] = "onSettingBtnClick" }
function XxxPanel:getPanelMessageHandler() return panelMessageHandler end
```

**属性变化绑定（三种写法，按场景选）：**

```csharp
// ① 非静态实例方法（最简，首选）
m_VM.RegisterPropertyChangeHandler<string>(MyViewModel.NAME, UpdateName);
// ② CommonHandler（标准文本/显隐）
m_VM.RegisterPropertyChangeHandler(MyViewModel.NAME, m_NameText, AtomUIText.CommonHandler.TextChangeHandler);
// ③ 静态委托（性能敏感）
m_VM.RegisterPropertyChangeHandler(MyViewModel.HP, this, s_HpHandler);
```

- **Register vs Set**：`RegisterPropertyChangeHandler` 同 id 重复注册会抛异常；可能多次调用的 `UpdateView` 用 `SetPropertyChangeHandler`（静默覆盖）。
- 绑定是**可选**的：永不变化的属性可只在 `InitializeView()` 读一次，不必绑定。
- 普通 View **无需**手动 `UnRegisterPropertyChangeHandler`，框架在 View 销毁时自动清理。

## 6. 组件选型与文本样式

- **优先公共组件，避免裸 UGUI**（`Button`/`Text`/`Image`）。来源：
  `PackageRepo/com.jngame.atom-gui/Runtime/`、`client/Assets/Scripts/Game/UI/Components/`、`.../UI/View/`。
  常用：`AtomUIText`/`AtomUIImage`/`AtomUIButton`。仅当无合适公共组件时才用裸 UGUI。
- 文本强调默认只包强调片段：`<style="Highlight">...</style>`。
- 仅这两类语义色用 `<color>`：警示 `<color=#fa3f81>`、货币数字 `<color=#ee9900>`。
- 混合静态/动态文本：先决定来源属于 Excel/配表还是 prefab format 串（见 `patterns/static-format-text-pattern.md`）。

## 7. 生命周期配对（真实钩子）

**Panel 生命周期钩子**（基类均为空，按需 override；**禁 override `ctor()`/`dispose()`**）：

| 钩子 | 时机 | 典型用途 |
|------|------|---------|
| `onPanelCreate(panelData)` | 首次创建 | 一次性 setup |
| `prepareViewModel(panelData)` | View 加载前 | 初始化 ViewModel 数据 |
| `initialize()` | prepareViewModel 后、VM 激活后 | 注册事件、createLib |
| `onPanelOpen()` | View 显示后 | 启动 timer、addEventListener |
| `onPanelRefresh(newPanelData)` | 已开时再 openPanel | 用新数据更新 ViewModel |
| `modifyPanelDataOnClose(panelData)` | 关闭前（**仅全屏**） | 持久化数据供下次打开 |
| `onPanelClose()` | View 销毁前 | **取消 timer、移除监听、dispose 创建的 Lib** |

**View 生命周期**：`Initialize(BaseViewModel)`（类型校验后 `InitializeView()` + `InitializeEvents()`）；仅在需要调 SubView.Destroy / 清自定义资源时才 override `Destroy()`。

- **清理是你的责任**：`onPanelClose` 中 `bd.cancelTimer`、`bd.eventManager:removeEventListener`、对每个 `self:createLib` 创建的 Lib 调 `lib:dispose()`。框架只自动销毁 ViewModel。
- `[SerializeField]` 引用首次使用前应判空（空安全，见 `prefab-binding-contract.md`）；用 `[Required]` 标注必绑字段则可免判空。

## 8. 禁止事项

- ⚠ **不优先手改自动生成文件**：`*_viewmodel.lua`、`*ViewModel.cs`、`AtomViewModelFactory.cs`、`ui_viewmodel_define.lua`。
  改属性优先改 ViewModelDes 再用工具重新导出生成。
  - **允许手改的唯一前提**：工具导出失败 / 不可用时，作为降级兜底手改补齐（须加 `TODO(模拟导出)` 标记 + 记 `HUMAN_REVIEW.md`，待工具正式重新导出覆盖）。见 §3 硬规则。
  - `*_data.lua`（配表导出产物）**不是** MVVM 生成文件，同样**优先 GDE/工具导出，导出失败才由 `gui-config` 手改镜像写入**（模拟导表），见 `verification-gates.md`。
- ❌ C# View 反向写 ViewModel（破坏单向数据流）。
- ❌ Panel 用 `vmFactory:createViewModel()` 直建 ViewModel（内存泄漏）。
- ❌ list 改动后忘记 `update()`。
- ❌ 给 ViewModel 实例加自定义字段。
- ❌ `onPanelClose` 漏清 timer / 监听 / 子 Lib。
- ❌ 生成成功前就写引用新属性的 View/Panel 代码。
- ❌ 在 View 的 `Update`/`LateUpdate` 中 `GetComponent` / 字符串拼接 / 重复查找（性能反模式）。

## 9. 进阶模式

列表、可复用组件、世界坐标跟踪、全屏壳层、互斥显隐等场景见 `shared-references/patterns/`（按需深读）。
模式选择决策树见 `patterns/README.md`。

## 10. 与各阶段的映射

| 阶段 | 用本契约做什么 |
|------|---------------|
| gui-draft | 按 §1–§8 生成 Panel/View，保证写↔读匹配；进阶场景查 §9 |
| gui-review | 审查 MVVM 一致性 / 生命周期 / 空安全 / 性能反模式 |
| gui-verify | Type-A：未改生成文件、绑定数量匹配；Type-B：交互逻辑 |
