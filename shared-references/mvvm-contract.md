# MVVM 一致性契约（AtomGUI）

> Atom Game 的 AtomGUI 是一套**轻量 MVVM-like** 框架，刻意与标准 MVVM 有差异。
> `gui-draft` 生成代码、`gui-review`（Type-B 审查 + Type-A 机械验证）均以本契约为基准。
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
- 核心不变式：**Panel 写的每个 ViewModel 属性，View 中必须有对应读取/绑定**；反之 View 读的属性，Panel（或配置）必须有来源。这是 `gui-review` Type-B「MVVM 一致性」维度与 Type-A 车道的检查点。

## 1.1 子 View / 子 Panel 拆分（复杂界面）

一个界面含**多页签、多个高内聚低耦合的模块、阶段流转、或独立浮层**时，拆成 Root + 子模块；单一
职责的小界面不拆（root 单 View 即可）。**拆分设计（要不要拆、怎么划分、VM 归属）由 gui-plan 在
`GUI_PLAN.md` 定死**，gui-draft 照此实现，不自行决定拆分。

- **子 View（C#）**是独立 class，两种形态：
  - **固定子区块**（常驻的信息块/列表区）：继承 `BaseView`，Root 用 `[SerializeField]` 持有，调
    `Initialize` **前先传 `BelongedPanelId`**——完整实现见 `patterns/subview-pattern.md`。
  - **页签/阶段切换**：子 View 继承 `TabSheetView`，Root 用容器 `TabView` 统一管理切换；可多级嵌套
    （页签内再开 `TabView`）。
- **子 Panel / 子 lib（Lua）**：
  - 页签式：Root Panel 用 `TableLib` 持有子 View 列表，子 View 继承 `TableSheetLib`、经 `belongedPanel`
    反向引用 Root Panel（子 VM 用 `belongedPanel:createViewModel()` 创建）。
  - **独立浮层/模态**（tips、说明弹窗）：拆成**独立子 Panel**（单独 `*_panel.lua` + 独立 PanelId），
    由子 View 经 `SendUIMessage` 触发，**不塞进 root**。
- **ViewModel 树形归属**：Root VM 持子 VM 列表（LIST，如 `Sheets`），每个子 View 绑自己的子 VM；item
  用 `createCustomViewModelList` 预声明为 LIST。§1 数据流铁律（只有 Lua 写、C# 只读）逐层同样适用。
- **命名对称 + 目录**：Lua `xxx_yyy_view.lua` ↔ C# `XxxYyyView.cs`；类名 `<Panel><模块>View`；子功能
  放子目录（Lua `grand_event/` ↔ C# `GrandEvents/`）。
- **样例**（页签式 + 多级嵌套的良好拆分）：
  `code/LuaScripts/client/ui/street/street_handbook/street_handbook_panel.lua` 与
  `client/Assets/Scripts/Game/UI/View/Street/StreetDevelopment/StreetHandbookView.cs`。

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

## 3. 变更流程（新增/改 ViewModel 属性时）——显式 4 步

ViewModel 属性的**设计（字段名/类型/是否 list/子 VM）由 gui-plan 在 `GUI_PLAN.md` 定死**；
gui-draft **照抄该契约写 ViewModelDes，不自行设计属性**。生成文件**优先用工具导出、不优先手改**。
**csharp-tool 独立于 Unity Editor，GenerateViewModel 不要求前置 Unity 编译**——整个变更按下面 4 步走：

```
S1 写 ViewModelDes ─ S2 csharp-tool 导出 ─ S3 写 View+Panel ─ S4 编译（能连 Unity Editor 时）
```

### 前置：判断 Unity Editor 运行状态（编译前必做）

Unity **C# 编译**有**两条路径**，涉及编译时先判断 Editor 是否正在运行。
**GenerateViewModel 与 `.meta` 文件生成统一走 csharp-tool**（`${CLAUDE_PROJECT_DIR}\tools\csharp-tool\`），
独立于 Unity Editor，不在此两路径内。详见 `shared-references/csharp-tool.md`。

1. **先通过 unity-cli 判断 Unity Editor 是否正在运行**（unity-cli 需要与运行中的 Editor 通信）。
2. **Editor 正在运行（unity-cli 可用）**：
   - 编译：通过 unity-cli 触发 C# 编译/刷新
   - **触发编译前先查 PlayMode 状态**；若处于 PlayMode 且需退出，**先征求用户确认**
   - **不要**凭记忆猜 unity-cli 语法，先看 `cs.py exec -h` 确认
3. **Editor 未运行（unity-cli 不可用）**：
   - 使用 **Unity Batch Mode** 命令行执行：
     - `./unity/WindowsEditor/Unity.exe -projectPath ./client/ -batchmode -quit <args>`
   - Batch Mode **能做**：C# 编译
   - Batch Mode **不能做**：编辑 Prefab、在 Inspector 中绑定 `[SerializeField]`（这些需运行中的 Editor）
   - 编译失败 → 按报错修代码再重编
4. **既无 unity-cli（Editor 未开）也无法跑 Batch Mode（无 Unity.exe）** → 编译判 `BLOCKED` 记入 `HUMAN_REVIEW.md`，管线不阻塞。
5. **csharp-tool（独立于 Editor）**：
   - **`.meta` 文件生成**：新增 C# 文件后通过 csharp-tool 生成 `.meta`，不依赖 Unity 编译
   - **GenerateViewModel**：通过 csharp-tool 执行 generator，不依赖 Unity Editor 运行状态，**不要求前置编译**
   - csharp-tool 不可用 → GenerateViewModel / `.meta` 均判 `BLOCKED` 记入清单

- **S1**：按 `GUI_PLAN.md` 的 ViewModel 契约编辑 `ViewModelDes/*.cs` 增/删/改字段。
  **此阶段不碰任何其他文件。**
- **S2**：通过 **csharp-tool** 导出 ViewModel（独立于 Editor，不要求前置 Unity 编译）。
  csharp-tool 不可用 → 判 `BLOCKED`，降级手改补齐（见下方硬规则）。
  - generator 入口（项目本地）：`Game.UI.ViewModelDes.CodeGen.ViewModelCodeGenerator.GenerateViewModel();`
    （文件 `client/PackageRepo/com.jngame.atom-gui/Editor/CodeGen/ViewModelCodeGenerator.cs`）。
  - 生成产物：C# `*ViewModel.cs`（常量）、Lua `*_viewmodel.lua`（属性名→ID 映射）、
    `AtomViewModelFactory.cs`、`ui_viewmodel_define.lua`。
  - **reconcile 路径推算**：从 `[ViewModel("group","lua_filename")]` 推出
    `code/LuaScripts/client/ui/{group}/{lua_filename}.lua` 与 `.../ViewModel/{ClassName}ViewModel.cs`，
    全局文件 `AtomViewModelFactory.cs`、`ui_viewmodel_define.lua` 每次必更新。记录这些路径供 reconcile 用。
- **S3**：编辑 C# View（引用 `MyViewModel.NEWPROP`）+ Lua Panel（设 `self.rootViewModel.NewProp`）。
  csharp-tool 已生成产物（或已在 S2 降级手改补齐），**此时即可直接引用新常量、写 View/Panel 逻辑**。
- **S4 编译**：**触发 Unity C# 编译**，让 ViewModelDes + 新生成的 `*ViewModel.cs` + View.cs 全部进程序集，
  验证整体编译通过。按前置规则判断 Editor 状态后走对应路径（unity-cli 或 Batch Mode）；两路径均不可用 →
  判 `BLOCKED` 记入 `HUMAN_REVIEW.md`。编译报错 → 按报错修代码再重编。

> 纯 Lua 改动（不涉及 ViewModelDes/新常量）**不触发** C# 编译。编译只在本 4 步（有 ViewModel 属性增改 /
> 新增 C# View）时涉及。

> **硬规则：优先工具导出，导出失败才手改。**
> 1. **首选**：用 csharp-tool 执行 generator 正式导出生成 ViewModel 文件。能用工具就**不要**手改。
> 2. **csharp-tool 不可用 / 导出失败 → 允许手改补齐**
>    （**不卡管线、不优先**）：按上面的 reconcile 路径推算，手写本应由 generator 产出的内容——`*ViewModel.cs`
>    常量、`*_viewmodel.lua` 属性名→ID 映射，并在 `AtomViewModelFactory.cs`、`ui_viewmodel_define.lua` 补对应
>    条目（仿照同文件里现有条目的写法）。每处加 `// TODO(模拟导出): 工具导出失败手改，待工具正式重新导出覆盖`
>    （Lua 用 `--`），并汇总进 `HUMAN_REVIEW.md`。手改补齐后即可进入 S3 写 View/Panel；实在写不出
>    （如无法定位现有条目格式）才将本步 `skipped` 并记 TODO。
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
| gui-review | Type-B：MVVM 一致性 / 生命周期 / 空安全 / 性能反模式；Type-A：未改生成文件、绑定数量匹配、交互逻辑对应 |
