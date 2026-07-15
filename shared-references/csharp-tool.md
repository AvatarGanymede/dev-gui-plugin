# csharp-tool 依赖契约

> `csharp-tool` 是项目本地的 C# 辅助工具，负责**生成 `.meta` 文件**与**执行
> `GenerateViewModel()`**。基于 .NET 8.0 + Roslyn（`Microsoft.CodeAnalysis.CSharp`），
> **从源码直接解析 ViewModelDes，不依赖 Unity 反射**——因此不需要前置 Unity 编译。
> 自本契约生效起，`.meta` 生成与 GenerateViewModel **不再通过 unity-cli 或
> Batch Mode 执行**——统一走 csharp-tool。

## 1. 位置

- **项目内路径**：`${CLAUDE_PROJECT_DIR}\tools\csharp-tool\`
- **源路径**：`d:\workflow\Project-Atom-Game-beilin-trunk\tools\csharp-tool\`
- **前置依赖**：.NET 8.0 SDK（`dotnet` 命令可用）

## 2. 架构与原理

| 特性 | 说明 |
|------|------|
| 运行时 | .NET 8.0 console app |
| 源码解析 | Roslyn（`Microsoft.CodeAnalysis.CSharp` 4.8）——直接从 `.cs` 源文件解析 ViewModelDes |
| 独立性 | 不依赖 Unity Editor、不需要 Unity 编译、不需要反射已编译程序集 |
| 配置 | `config.json`（相对于 csharp-tool 目录的路径） |
| 工程根检测 | 自动：从 csharp-tool 目录上溯两级（`tools/csharp-tool/` → `tools/` → 工程根） |

### config.json（默认值，相对于 csharp-tool 目录）

```json
{
  "templateDir": "../../client/PackageRepo/com.jngame.atom-gui/Editor/CodeGen",
  "viewModelDesDir": "../../client/Assets/Scripts/Game/UI/ViewModelDes",
  "viewModelOutDir": "../../client/Assets/Scripts/Game/UI/ViewModel",
  "luaOutRoot": "../../code/LuaScripts"
}
```

> 所有路径参数均可通过 CLI 选项覆盖（`--des-dir` / `--out-dir` / `--lua-dir`），
> 一般不覆盖，使用 config.json 默认值即可。

## 3. 两个子命令

### 3.1 `meta` — 生成 `.meta` 文件

为指定目录下所有**缺少 `.meta`** 的 `.cs` 文件生成 Unity `.meta` 文件。
**非破坏性**：已有 `.meta` 的不覆盖（保留 Unity 分配的 GUID）。

| 项目 | 说明 |
|------|------|
| GUID 算法 | MD5(asset path relative to Assets/) → 32 位 hex |
| 默认扫描目录 | `client/Assets/Scripts/Game/UI/ViewModel` |
| 文件格式 | Unity `.meta` v2（MonoImporter） |

**调用方式**（工作目录 = `tools\csharp-tool\`）：

```bash
# 使用默认目录（ViewModel 输出目录）
./generateMeta.sh

# 指定其他目录
./generateMeta.sh --dir ./client/Assets/Scripts/Game/UI/View/
# 或
./generateMeta.sh -d ./client/Assets/Scripts/Game/UI/View/

# 等同直接调用
dotnet run -c Release -- meta
dotnet run -c Release -- meta --dir <path>
```

### 3.2 `genvm` — 生成 ViewModel

从 ViewModelDes 源文件生成：
- C# `*ViewModel.cs`（常量类，如 `MyViewModel.NEWPROP`）
- Lua `*_viewmodel.lua`（属性名→ID 映射）
- `AtomViewModelFactory.cs`（全局工厂，每次必更新）
- `ui_viewmodel_define.lua`（全局 define，每次必更新）

**关键**：通过 Roslyn 直接解析 ViewModelDes 源码，**不经过 Unity 反射**——
这就是为什么 S2 不需要前置编译。

**调用方式**（工作目录 = `tools\csharp-tool\`）：

```bash
# 使用 config.json 默认路径（最常用）
./generateViewModel.sh

# 指定工程根（当自动检测不对时）
./generateViewModel.sh --project-root /path/to/project
# 或
./generateViewModel.sh -p /path/to/project

# 覆盖输出目录（极少用，默认走 config.json）
./generateViewModel.sh --des-dir <path> --out-dir <path> --lua-dir <path>

# 等同直接调用
dotnet run -c Release -- genvm
dotnet run -c Release -- genvm --project-root <path>
```

**CLI 选项一览**：

| 选项 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `--project-root` | `-p` | 工程根目录 | 自动检测（上溯两级） |
| `--des-dir` | `-d` | ViewModelDes 源文件目录 | config.json `viewModelDesDir` |
| `--out-dir` | `-o` | ViewModel C# 输出目录 | config.json `viewModelOutDir` |
| `--lua-dir` | `-l` | Lua 脚本根目录 | config.json `luaOutRoot` |
| `--unity-dll-dir` | `-u` | 额外 DLL 目录（可选） | 无 |
| `--help` | `-h` | 打印帮助 | — |

## 4. 在 MVVM 4 步流程中的位置

csharp-tool 在两个场景被调用：

1. **S2 工具导出**：写完 ViewModelDes 后，直接 `./generateViewModel.sh`（不要求前置编译）。
   产物就绪后即可进入 S3 写 View/Panel。
2. **新增 C# 文件之后**：`./generateMeta.sh` 为缺少 `.meta` 的新文件生成 `.meta`。

完整流程：`S1 写 ViewModelDes → S2 csharp-tool 导出 → S3 写 View/Panel → S4 编译`

## 5. 与 unity-cli 的分工

| 能力 | 工具 | 备注 |
|------|------|------|
| 判断 Unity Editor 是否运行 | unity-cli | 仅 unity-cli 能与运行中的 Editor 通信 |
| C# 编译（Editor 运行中） | unity-cli | 触发 Editor 内编译/刷新 |
| C# 编译（Editor 未运行） | Batch Mode（Unity.exe） | `-batchmode -quit` |
| 生成 `.meta` 文件 | **csharp-tool** | 不再走 unity-cli / Batch Mode |
| `GenerateViewModel()` | **csharp-tool** | 不再走 unity-cli / Batch Mode |
| Prefab 编辑（挂脚本、绑定 SerializeField） | unity-cli（Editor 运行中） | Batch Mode 无法编辑 Prefab |
| 读 Editor Console | unity-cli | gui-review Type-A 编译验证用 |

## 6. 不可用时的降级

- csharp-tool 不可用 → GenerateViewModel 与 `.meta` 生成均判 `BLOCKED`，记入
  `HUMAN_REVIEW.md`「待人工用 csharp-tool 生成 .meta 与 ViewModel 导出」。
- 降级手改补齐规则同 mvvm-contract §3：手写产物 + `TODO(模拟导出)` 标记，
  手改补齐后即可进入 S3 写 View/Panel。

## 7. 相关文档

- `mvvm-contract.md` — MVVM 4 步变更流程（§3），csharp-tool 在 S2 调用
- `gui-draft/SKILL.md` — 第 2 阶段，5b 步调用 csharp-tool 导出 ViewModel
- `gui-prefab/SKILL.md` — 第 3 阶段，.meta 由 csharp-tool 生成
