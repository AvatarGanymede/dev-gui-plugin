# dev-gui-plugin 设计与实现计划

> Atom Game GUI 开发全流程 Claude Code Plugin，含 7 阶段 pipeline、长期记忆知识库、subagent 审查和验证门体系。

## 参考来源

| 来源 | 借鉴的核心模式 |
|------|--------------|
| **ARIS** (wanshuiyin/Auto-claude-code-research-in-sleep) | Knowledge Base 持久化、Assurance Contract 6 态裁决、Acceptance Gate Type-A/B 分类、Auto-Improvement Loop + Bias Guard、fan-out 并行 |
| **UI Skill Lab** (Jason904/ui-skill-lab) | 7 阶段反漂移 pipeline、每阶段 quality gate (Pass/Conditional/Fail)、drift 分类控制、fix-tasks.json 结构化修复 |
| **Agent Tools** (sequenzia/agent-tools) | Filesystem-as-integration-contract、文件系统状态管理 |
| **1Password Design System Pipeline** | Skills over documentation、uncertainty surfacing、narrow scope per skill |
| **Claude Code Plugin 官方文档** | Plugin 目录结构、plugin.json schema、`${CLAUDE_PLUGIN_ROOT}` / `${CLAUDE_PLUGIN_DATA}` 约定 |

---

## 一、Plugin 目录结构

```
dev-gui-plugin/
│
├── .claude-plugin/
│   └── plugin.json                    # 插件清单（name/version/description；skills·agents·hooks 走默认目录自动发现）
│
├── skills/                            # 7 个命名空间 skill (/dev-gui-plugin:gui-xxx)
│   ├── gui-plan/SKILL.md              # Phase 1: plan mode 确认需求 + 人类审批
│   ├── gui-draft/SKILL.md             # Phase 2: MVVM 代码生成（自包含）
│   ├── gui-prefab/SKILL.md            # Phase 3: Prefab 编辑（自包含，不依赖 edit-prefab）
│   ├── gui-config/SKILL.md            # Phase 4: 配置表编辑（自包含，不依赖 edit-excel）
│   ├── gui-review/SKILL.md            # Phase 5: 唯一验证门（Type-B subagent ∥ Type-A 机械门）
│   ├── gui-improve/SKILL.md           # Phase 6: 迭代修复循环
│   └── gui-learn/SKILL.md             # Phase 7: 知识沉淀（回写 gui-knowledge）
│
├── agents/
│   └── gui-reviewer.md                # 审查 subagent 定义（独立上下文，Bias Guard）
│
├── hooks/
│   └── hooks.json                     # 命令统一走 python3（替换骨架默认的 bun handler）
├── hooks-handlers/
│   ├── on_session_start.py            # 读 ${CLAUDE_PLUGIN_DATA}/gui-knowledge/query_pack.md 注入上下文
│   └── pre_write_filter.py            # 调 capture_filter.py 拦截污染写入
│
├── gui-knowledge-seed/                # 知识库「种子模板」（随插件分发，只读）
│   ├── README.md                      #   首次运行时若 ${CLAUDE_PLUGIN_DATA}/gui-knowledge/
│   ├── index.md                       #   不存在，由 gui-plan/gui-learn 复制此目录初始化
│   └── graph/edges.jsonl              #   空骨架；运行期严禁回写 seed
│
├── shared-references/                 # 契约文档（内聚在 plugin 内，不依赖外部 skill）
│   ├── mvvm-contract.md               # MVVM 一致性规范（Panel→ViewModel→View 数据流）
│   ├── prefab-binding-contract.md     # Prefab 绑定完整性规范（[SerializeField] 检查清单）
│   ├── verification-gates.md          # 验证门定义（Type-A/B 分类 + 6 态裁决）
│   ├── knowledge-schema.md            # 知识条目 schema（bug/component/pattern/fix 字段定义）
│   ├── acceptance-gate.md             # 接受门分类（从 ARIS 迁移，适配 GUI 场景）
│   └── patterns/                      # AtomGUI 进阶模式库
│       ├── README.md                  #   模式选择决策树 + 文档索引
│       ├── listmodule-pattern.md  scroll-rect-pattern.md  uilib-pattern.md
│       ├── subview-pattern.md  world-tracking-pattern.md  fullscreen-basic-pattern.md
│       └── stylesmodule-pattern.md  static-format-text-pattern.md  data-binding-patterns.md
│
├── tools/                             # 辅助脚本（部分从 ARIS 迁移/适配，均为插件内 Python）
│   ├── gui_knowledge.py               # 知识库引擎：建条目 / edges / render-connections / rebuild-query-pack / 去重（适配自 research_wiki.py）
│   ├── gui_run_state.py               # Pipeline 状态机（适配自 ARIS run_state.py）
│   ├── capture_filter.py              # 写入前机械筛：env / transient / negative-tool / single-instance（适配自 ARIS）
│   ├── threat_scan.py                 # query_pack 注入扫描（取自 ARIS，仅留 scan_for_threats）
│   ├── watchdog.py                    # 从 ARIS 迁移，监控 pipeline 健康状态
│   └── lint_skills_helpers.sh         # 从 ARIS 迁移，检查 SKILL.md 中的硬编码路径
│
└── README.md                          # Plugin 说明文档
```

> **运行期真实知识库不在插件目录内**，而在持久化目录（跨版本存活、不进 git、不团队共享）：
> ```
> ${CLAUDE_PLUGIN_DATA}/gui-knowledge/   (= ~/.claude/plugins/data/dev-gui-plugin-<marketplace>/gui-knowledge/)
>   ├── index.md  log.md  query_pack.md
>   ├── bugs/  fixes/                       # 实例层（带 panelId：记录「发生了什么」）
>   ├── components/  patterns/  lessons/    # 通用层（跨 panel 复用：记录「下次怎么做」）
>   └── graph/edges.jsonl
> ```
> 插件本体（`${CLAUDE_PLUGIN_ROOT}`）每次更新即被替换，官方明确「不要在此写状态」，故只放只读 seed。

### 部署形态：marketplace 插件

本插件以 **marketplace 插件**形式分发与安装（不采用 `@skills-dir` 就地形态，也不依赖 `--plugin-dir` 持久挂载）。

- 开发期源码目录：独立插件仓库 / `tools/dev-gui-plugin/`（调试时可用 `claude --plugin-dir <dir>` 临时挂载）
- 正式安装：发布到 marketplace 后 `claude plugin install dev-gui-plugin@<marketplace>`
- 安装后插件本体位于插件缓存 `${CLAUDE_PLUGIN_ROOT}`（更新即替换，视为只读/易失）
- 知识库写 `${CLAUDE_PLUGIN_DATA}`（卸载时默认随之删除，`--keep-data` 可保留）

> ⚠ `${CLAUDE_PLUGIN_ROOT}` 在每次插件更新时路径变化、内容被替换——官方明确要求「不要在此写状态」。
> 因此所有运行期产物（bugs / fixes / query_pack / edges.jsonl）一律写 `${CLAUDE_PLUGIN_DATA}`。

### 单次运行产物位置

per-run 产物（`GUI_PLAN.md` / `GUI_REVIEW.md` / `GUI_VERDICT.json` / `GUI_IMPROVEMENT_LOG.md` / `HUMAN_REVIEW.md`）
与 `gui_run_state.py` 的状态文件，写 **项目内 run 目录**：
```
${CLAUDE_PROJECT_DIR}/.claude/dev-gui-runs/<panelId>/
  ├── GUI_PLAN.md  GUI_REVIEW.md  GUI_VERDICT.json  GUI_IMPROVEMENT_LOG.md  HUMAN_REVIEW.md
  └── run_state.json          # gui_run_state.py：phase / done / accepted / resume_point
```
- 与代码改动并排，便于开发者直接 review，支持跨会话 resume。
- 加入项目 `.gitignore`（`/.claude/dev-gui-runs/`），不进版本库。
- 与长期知识库（`${CLAUDE_PLUGIN_DATA}/gui-knowledge/`）**分离**：run 产物是一次性、项目本地的；知识库是跨版本、跨任务沉淀的。

---

## 二、plugin.json

```json
{
  "$schema": "https://anthropic.com/claude-code/plugin.schema.json",
  "name": "dev-gui-plugin",
  "version": "0.1.0",
  "description": "Atom Game GUI 开发全流程 pipeline — 从需求到交付的 7 阶段自动化工作流，含长期记忆知识库和 subagent 审查体系",
  "author": {
    "name": "北林"
  },
  "license": "MIT",
  "keywords": ["gui", "unity", "mvvm", "prefab", "atom-game"]
}
```

> `skills/` · `agents/` · `hooks/` 均按**默认目录自动发现**，无需在 manifest 显式声明。
> 官方规则：显式声明 `agents`/`commands` 是「**替换**」默认目录而非追加，留空更稳妥；
> `version` 设定后用户仅在 bump 时收到更新。
> （注意与已生成骨架的 `plugin.json` 对齐：骨架里的 `"skills": ["./"]` 会把插件根 SKILL.md
> 当成一个 skill，与本插件「7 个 skill 在 skills/ 下」的布局冲突，需删除该字段。）

---

## 三、7 阶段 Pipeline 详解

### 总览

```
用户需求（/dev-gui-plugin:gui-plan）
  │
  ▼
┌──────────────────────────────────────────────────────────┐
│ Phase 1: gui-plan    plan mode 确认需求 + 人类审批         │
│ 控制：需求理解漂移                                         │
│ 输入：用户原始需求                                         │
│ 输出：GUI_PLAN.md（审批过的需求契约）                       │
│ Gate：用户 ExitPlanMode 审批通过                            │
└────────────────────────┬─────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────┐
│ Phase 2: gui-draft   MVVM 代码生成                        │
│ 控制：代码实现漂移（vs 需求规格）                            │
│ 输入：GUI_PLAN.md + gui-knowledge/query_pack.md           │
│ 输出：Panel.lua + View.cs + ViewModel（如有新增）           │
│ Gate：MVVM 一致性（Panel 写 ↔ View 读 匹配）               │
└────────────────────────┬─────────────────────────────────┘
                         ▼
      ┌──────────────── Phase 3 ∥ Phase 4 并行组 ───────────────┐
      │  主 agent                        subagent（按需）        │
┌─────┴────────────────────────────┐  ┌────────────────────────┴──────┐
│ Phase 3: gui-prefab  Prefab 编辑  │  │ Phase 4: gui-config 配置表编辑 │
│ （主 agent）                       │  │ （subagent，涉及配置才 spawn） │
│ 控制：Prefab 绑定漂移              │  │ 控制：配置数据漂移             │
│ 前置：**先触发 C# 编译再改 prefab**│  │ 输入：功能涉及的配置数据需求    │
│ 输入：View.cs + prefab 路径        │  │ 输出：design/tables/*.xlsx     │
│ 输出：修改后的 .prefab             │  │       + 镜像 *_data.lua        │
│ Gate：编译门 + [SerializeField]绑定│  │ Gate：Excel ↔ *_data.lua 同步  │
└─────┬────────────────────────────┘  └────────────────────────┬──────┘
      │        两阶段都落定后 orchestrator 汇合（TaskOutput）    │
      └────────────────────────┬────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────┐
│ Phase 5: gui-review  唯一验证门（并行两车道）               │
│ 控制：逻辑质量漂移 + 机器可验证正确性                        │
│ 输入：Phase 2-4 的所有产出文件                              │
│                                                          │
│ Type-B 车道（独立 subagent，run_in_background，Bias Guard）: │
│  • 交互逻辑正确性 / 性能反模式 / MVVM 一致性 / 生命周期        │
│  • 输出 GUI_REVIEW.md（CRITICAL > MAJOR > MINOR + Score）  │
│ Type-A 车道（orchestrator 自跑，等 subagent 期间并行）:      │
│  • C# 编译 / Lua 语法 / Prefab 节点存在 / 绑定数量匹配        │
│  • 生成文件优先工具导出 / 配置 Excel↔data 同步               │
│                                                          │
│ 汇合 → 合并 CRITICAL 集合（编译/语法失败 ∪ Type-B CRITICAL）│
│ 输出：GUI_VERDICT.json + HUMAN_REVIEW.md(清单)            │
│ Gate：合并 CRITICAL 数 == 0                                │
└────────────────────────┬─────────────────────────────────┘
                         ▼
              ┌── 有合并 CRITICAL? ──┐
              │                      │
             否                      是
              │                      │
              │                      ▼
              │      ┌──────────────────────────────┐
              │      │ Phase 6: gui-improve          │
              │      │ 迭代修复循环（最多 2 轮）       │
              │      │  1. 读合并 CRITICAL 集合        │
              │      │  2. 按优先级修复（含编译/语法）  │
              │      │  3. 重跑 gui-review 两车道       │
              │      │  4. 输出 GUI_IMPROVEMENT_LOG  │
              │      │ 每轮 Bias Guard；2 轮后仍有     │
              │      │ CRITICAL → 记 HUMAN_REVIEW    │
              │      └──────────────┬───────────────┘
              │                     │
              └──────────┬──────────┘
                         ▼
┌──────────────────────────────────────────────────────────┐
│ Phase 7: gui-learn   知识沉淀（每次完成后自动触发）          │
│                                                          │
│ 实例层: bug+根因+修复 → bugs/ ; 修复尝试 → fixes/         │
│ 通用层(每次必做,泛化后跨 panel 复用):                       │
│   组件用法 → components/ ; 反模式/最佳实践 → patterns/      │
│   通用教训/性能经验 → lessons/                             │
│ 索引/晋升: edges→自动渲染关联 ; proposed→confirmed(reviewer 背书)        │
│ query_pack.md(仅 confirmed,确定性装配) ; capture_filter 机械筛 ; log.md  │
└──────────────────────────────────────────────────────────┘
```

---

### Phase 1: gui-plan — plan mode 确认需求 + 人类审批

**职责**：进入 plan mode，只读定位资源、向用户澄清需求、写计划并**等人类审批**；审批通过后产出
**高度精炼**的需求契约 `GUI_PLAN.md`。这是整条 pipeline 唯一的交互 + 人类审批关卡；本阶段**零写操作**，
所有写操作（run state / GUI_PLAN.md / 哨兵）都发生在审批之后。

**输入**：用户原始需求（可能不完整）

**处理流程**：
1. 进入 plan mode（`EnterPlanMode`；已在则跳过）—— 以下均为只读
2. 读 `code/LuaScripts/client/data/ui_data.lua` 定位 Prefab 路径、Panel 脚本路径、ViewModel 类型
3. 用 SessionStart hook 已注入上下文的 query_pack 历史坑点/组件技巧（**无需现场读文件或 init**）
4. 需求缺失/歧义 → `AskUserQuestion` 一次性向用户澄清（此阶段无 autorun 哨兵，可自由停顿）
5. 写计划（偏需求侧：要做什么 + 验收标准）→ `ExitPlanMode` 等人类审批；被拒则改后再审
6. 审批通过后（已退出 plan mode）→ 初始化 run state + 输出精炼 `GUI_PLAN.md`

**输出格式 `GUI_PLAN.md`（高度精炼，供 gui-review 独立审查者当契约）**：
```markdown
# GUI PLAN: <panelId>   （用户已审批）

- panelId / Prefab 路径 / Panel 脚本路径 / ViewModel 类型

## 需求
- [几行 bullet：这个界面要做什么]

## 验收标准
- [几行 bullet：review 据此判断是否达成]

## 相关历史坑点（可选，来自 query_pack）
- [涉及组件的已知坑点 / 类似界面曾出现的 bug]
```

**Gate**：panelId + 功能描述 必须齐全 → 进入 Phase 2

---

### Phase 2: gui-draft — MVVM 代码生成

**职责**：自包含的 MVVM 代码生成指引。

**核心规则（内嵌）**：
- Panel (Lua) 写 ViewModel，View (C#) 只读
- ViewModel 设计由 gui-plan 定死，gui-draft 照抄写 ViewModelDes、不自行设计
- 需要新增/改 ViewModel 属性 → 走 §3 的 5 步、含两道 C# 编译硬门：写 ViewModelDes → 编译① → 工具导出 → 编译② → 写 View/Panel（编译②前禁写 View/Panel）。每次编译前先判断 Unity Editor 运行状态：运行中→unity-cli；未运行→Batch Mode（`./unity/WindowsEditor/Unity.exe -projectPath ./client/ -batchmode -quit ...`）。两路径均不可用→BLOCKED。
- 生成文件 `*_viewmodel.lua` / `*ViewModel.cs` / `AtomViewModelFactory.cs` / `ui_viewmodel_define.lua`：
  **优先工具导出，不优先手改**；仅当工具导出失败/不可用时才允许降级手改补齐（加 `TODO(模拟导出)` + 记 `HUMAN_REVIEW.md`）
- Panel 文件名：`<PanelName>Panel.lua`，继承 `UIBasePanel`
- View 文件名：`<PanelName>View.cs`，继承 `BaseView`
- 优先 AtomUI* 公共组件，避免裸 UGUI

> 真实模板见 `skills/gui-draft/SKILL.md` 与 `shared-references/mvvm-contract.md`（已注入真实基类、
> 生命周期钩子 `prepareViewModel`/`onPanelClose`、事件 enum 同步、`RegisterPropertyChangeHandler` 等）。
> 进阶模式（ListModule/ScrollRect/UILib/SubView/世界跟踪等）见 `shared-references/patterns/`。

**输出**：Panel.lua + View.cs + ViewModel（如有新增）

**Gate**：
- Panel 写的 ViewModel 属性 → View 中有对应的读取/绑定
- 自动生成文件优先工具导出；如因导出失败手改，须带 `TODO(模拟导出)` 标记并记入 `HUMAN_REVIEW.md`

---

### Phase 3: gui-prefab — Prefab 编辑（主 agent，与 Phase 4 并行）

**职责**：自包含的 Prefab 编辑指引，不依赖外部 edit-prefab skill。**跑在主 agent**，
与 gui-config（Phase 4，涉及配置时 spawn 到 subagent）**并行**；两阶段都落定后才进 gui-review。

**前置 C# 编译（硬门，改 prefab 之前必做）**：先判断 Unity Editor 运行状态——**Editor 运行中**：
通过 unity-cli 触发 C# 编译（先查 PlayMode 状态），编译通过后才能挂脚本+绑定 `[SerializeField]`；
**Editor 未运行**：可通过 Batch Mode 编译（`./unity/WindowsEditor/Unity.exe -projectPath ./client/ -batchmode -quit ...`），
生成 `.meta`、让 View/ViewModel 进程序集，但 **Batch Mode 无法编辑 Prefab**——Prefab 编辑本身判 `BLOCKED`
记入 `HUMAN_REVIEW.md`「需在 Unity Editor 中人工挂脚本/绑定」；两路径均不可用 → 编译门 + Prefab 编辑均
`BLOCKED`。编译通过后才进入下面的编辑。

**编辑内容**：
- 把 View.cs 脚本挂到 Prefab 根节点
- 绑定 `[SerializeField]` 引用（按钮、文本、图片、列表节点）
- `StylesModule<TEnum>` 分组节点 + 默认 `m_SelectedIndex`
- `ListModule` Template 节点保持 inactive
- 静态格式文本保留在 Prefab 文本节点

**工具使用**：不在插件内硬绑定 MCP。运行时若已加载 `unity-prefab` 等 Prefab 能力则选用；未加载则交人工编辑。

**Gate**：① 改 prefab 前 C# 已编译通过（Editor 未运行→Batch Mode 编过但 Prefab 编辑 BLOCKED；两路径均不可用→BLOCKED）；② View.cs 中每个 `[SerializeField]` 在 Prefab 中都有对应的绑定节点。

---

### Phase 4: gui-config — 配置表编辑（subagent，与 Phase 3 并行）

**职责**：自包含的配置表编辑指引，不依赖外部 edit-excel skill。**由 orchestrator 在涉及配置时 spawn 到 subagent**，
与主 agent 的 gui-prefab（Phase 3）**并行**；subagent 只做配表编辑并把结果（`edited`/`skipped`/`blocked` + 改动文件）
**结构化返回 orchestrator**，**run_state 由 orchestrator（主 agent）统一记账**（subagent 不自行写状态，避免缺 session env）。

**规则（优先工具导表，导出失败才手改镜像；零人工中断）**：
- 改 `design/tables/` 下的 **Excel 源表**（真正的真相源）。
- `*_data.lua` **优先用工具正式导出**（GDE CLI / excel-config 等）；**工具不可用/导出失败时，才降级手改镜像写入**，
  模拟「导表成功导出」，使运行期与后续阶段立即可见新配置，全程不中断。手改镜像须严格对齐 GDE 导出格式
  （按行定位、同字段同值），加 `TODO(模拟导出)` 并记 `HUMAN_REVIEW.md`。
- 区分两类「生成文件」，勿混淆——两者都**优先工具导出、导出失败才手改**：
  - `*_data.lua`（配表导出产物）—— 导出失败时手改镜像写入，不是禁区。
  - `*_viewmodel.lua` / `*ViewModel.cs`（MVVM 代码生成）—— 同理优先工具导出，失败才手改（见 Phase 2）。

**工具使用**：不在插件内硬绑定具体 MCP/skill。运行时由模型根据**当前已加载**的能力自行选择
（如已加载 `excel-config`/`excel-mcp` 则用之；未加载则在最终人工清单中标出需手工配表）。

**Gate**：Excel 源表与对应 `*_data.lua` 改动**一致**（同字段、同值），运行期可读到新配置。

> 正式导表仍需人工：手写的 `*_data.lua` 是**模拟产物**，正式 GDE 导表会覆盖它。
> 故「确认 Excel 配置正确并正式导表」列入**最终人工检查清单 `HUMAN_REVIEW.md`**（见 Phase 5 末），
> 但**绝不在管线中途停顿**——agent 先把能做的全做完，需人确认的统一收口到最后。

---

### Phase 5: gui-review — 唯一验证门（并行两车道）

**职责**：一个阶段、两条**并行**车道汇合成合并 CRITICAL 门，输出 6 态裁决。原独立的 gui-verify
（Type-A/B 分两阶段跑两遍 reviewer）已并入本阶段——Type-B 交独立 subagent、Type-A 由 orchestrator
在等 subagent 期间就地跑，两者只读不写、无竞态。

**Type-B 车道 — Bias Guard 规则**（从 ARIS 迁移）：
- 用 **全新 subagent**（`run_in_background: true`，不传之前的 thread/context）
- 审查 prompt 中**不包含**"我们改了什么"、"上一轮提到"等实现细节
- 只传递：当前代码文件 + GUI_PLAN.md + 相关契约文档
- 审查者只能从代码本身判断质量（**只做品味维度**，机械核实归 Type-A）

**Type-B 审查维度（品味）**：

| 维度 | 检查内容 |
|------|---------|
| MVVM 一致性 | Panel 写 ↔ View 读 是否匹配 |
| 生命周期正确性 | OnCreate/OnDestroy 配对、事件订阅/退订 |
| 空安全 | [SerializeField] 是否判空、回调是否判空 |
| 性能反模式 | Update 中 GetComponent、字符串拼接、重复查找 |
| 代码规范 | 命名是否符合项目惯例、文件组织 |

**审查 subagent 定义** (`agents/gui-reviewer.md`)：
```markdown
---
name: gui-reviewer
description: Atom Game GUI 代码审查 agent，独立上下文审查 MVVM 代码、生命周期、性能反模式等品味维度
tools: Read, Grep, Glob, LSP
---

# GUI Code Reviewer

你是 Atom Game 项目的 GUI 代码审查者（gui-review 的 Type-B 车道）。你获得的是当前代码的
**最终状态**，不知道实现过程。只从代码本身做品味判断。

## 职责边界（只做品味判断）
- 「Prefab 绑定数量」「配置同步」「编译/语法」等机械可验证项归 orchestrator 的 Type-A 车道，
  **不在本 agent 职责内**，不要因缺 prefab/Excel 上下文而报这些维度的 CRITICAL。

## 校验基准以运行期真实代码为准
- 本插件模板/契约是「示意」，可能与项目最新基类不一致。
- 判定前先读**真实基类**（`UIBasePanel` / `BaseView` 等）确认其生命周期与 API。

## 审查维度
[详细审查规则...]
```

**Type-B 输出 `GUI_REVIEW.md`**：
```markdown
# GUI Review: <panelId>

## Overall Score: X/10

## Critical Issues
1. [CRITICAL] <描述> @ <file>:<line> — 修复建议: ...

## Major Issues / Minor Issues
...
```

#### Type-A 车道（orchestrator 自跑，等 subagent 期间并行）

> ⚠ 全程**无中途 HUMAN_CHECKPOINT**：agent 把能机器验证的全做完，凡需人确认的项
> （运行期打开 panel 截图、Excel 配置正确性、未解决的 CRITICAL 等）一律**汇总进
> `HUMAN_REVIEW.md`**（见本节末），管线继续跑完、不停顿。下表为静态/离线可验证项；
> 涉及 Unity 编译的项若环境未就绪 → 判 `BLOCKED` 并记入 `HUMAN_REVIEW.md`，不阻塞后续。

机器可验证，不需要品味/判断：

| 检查项 | 验证方式 |
|--------|---------|
| C# 编译通过 | 运行时若已加载 Unity 编译/刷新能力则读 Console / 触发 refresh；否则判 `BLOCKED` 记入清单 |
| Lua 语法正确 | `luac -p` 或热更无报错 |
| Prefab 节点存在 | 读 Prefab hierarchy，检查 View 中 SerializeField 名称对应的节点 |
| 绑定数量匹配 | View 中 SerializeField 数量 vs Prefab 中实际绑定数量 |
| 生成文件优先工具导出 | 检查 `*_viewmodel.lua` / `*ViewModel.cs` 的 diff；带 `TODO(模拟导出)` 标记的手改（工具导出失败兜底）判 `BLOCKED` 待重新导出、不判 failed；无标记手改仍判 failed（`*_data.lua` 例外：导出失败时镜像写入） |
| 配置 Excel↔data 同步 | Excel 源表与对应 `*_data.lua` 改动一致（模拟导表已正确镜像） |

> Type-B 车道的检查项即上文品味维度（交互逻辑正确性 / 性能反模式 / UI 布局合理性等），由
> `gui-reviewer` subagent 与本 Type-A 车道**并行**跑出。

#### 汇合 → 合并 CRITICAL 集合

两车道回来后，orchestrator 合并 CRITICAL：
`{Type-A 编译失败}` ∪ `{Type-A Lua 语法错误}` ∪ `{Type-B 报的 CRITICAL}`。编译/语法失败**升为
CRITICAL**（补上原设计漏洞：编译错误也能触发修复循环）；机械门的 `BLOCKED`/`NOT_APPLICABLE`
（缺能力/不适用）**不进** CRITICAL 集合，只记 `HUMAN_REVIEW.md`。

#### 6 态裁决（从 ARIS assurance-contract 迁移）

```json
{
  "panel_id": "xxx",
  "verdict": "PASS|WARN|FAIL|NOT_APPLICABLE|BLOCKED|ERROR",
  "type_a_gates": { "...": "passed|failed|skipped" },
  "type_b_gates": { "...": "passed|failed|skipped" },
  "summary": "...",
  "timestamp": "2026-06-16T..."
}
```

| Verdict | 含义 | 需人工签字? |
|---------|------|----------|
| PASS | 全部通过 | 否 |
| WARN | 有 MAJOR/MINOR 但无 CRITICAL | 否 |
| FAIL | 有 CRITICAL 未修复 | **需人工签字** |
| NOT_APPLICABLE | 某项检查不适用（如无配置变更则跳过 config gate） | 否 |
| BLOCKED | 检查条件不满足（如 Unity 未开、Prefab 不存在） | **需人工签字** |
| ERROR | 检查执行出错（超时、工具异常） | **需人工签字** |

> 「需人工签字」= 合入/上线前需人确认，**不等于管线停顿**。FAIL/BLOCKED/ERROR 项不停管线，
> 而是写进 `HUMAN_REVIEW.md` 并继续跑到 gui-learn——agent 先把能做的全做完。

**输出**：`GUI_VERDICT.json` + `HUMAN_REVIEW.md`

#### HUMAN_REVIEW.md — 最终统一人工检查清单
管线末尾一次性产出，把所有「agent 做不了 / 需人确认」的项集中，**不在中途打断**：
- [ ] **Excel 配置正确性**：源表字段/数值是否符合需求；**正式 GDE 导表**覆盖模拟写入的 `*_data.lua`
- [ ] **运行期效果**：启动客户端打开该 panel，截图核对交互与布局
- [ ] **未解决 CRITICAL**（如 2 轮修复后仍有）：逐条列出 file:line + 原因
- [ ] **BLOCKED / 降级项**：因环境缺失（Unity 未开、缺对应 MCP 等）未能自动验证的项

---

### Phase 6: gui-improve — 迭代修复循环

**职责**：对合并 CRITICAL（Type-A 编译/语法失败 + Type-B CRITICAL）修复 → 重跑 gui-review
两车道，最多 2 轮。

**流程**（从 ARIS auto-paper-improvement-loop 迁移）：
```
Round 1:
  1. 读 GUI_REVIEW.md 的 CRITICAL + MAJOR 问题
  2. 按优先级修复（CRITICAL → MAJOR）
  3. 重新 spawn subagent 审查（全新上下文，Bias Guard）
  4. 对比新旧审查结果
  5. 记录 GUI_IMPROVEMENT_LOG.md

Round 2（如仍有 CRITICAL）:
  1. 读最新 GUI_REVIEW.md
  2. 修复剩余 CRITICAL
  3. 重新审查 + 验证
  4. 记录日志

2 轮后仍有 CRITICAL:
  → 把未解决项写入 HUMAN_REVIEW.md（逐条 file:line + 原因），不暂停
  → 继续跑完 gui-review 重跑 + gui-learn，由最终人工清单统一收口
```

**Bias Guard 实现**：
```
每轮 gui-review：
  agent_type: "claude"（或项目配置的审查 agent）
  isolation: "worktree" （可选，视需要）
  不在 prompt 中包含：
    - 上一轮的审查结果
    - "我们已修复了 XXX"
    - 之前 subagent 的 threadId
  只传递：
    - 当前代码文件
    - GUI_PLAN.md
    - 相关 shared-references
```

**输出**：`GUI_IMPROVEMENT_LOG.md`
```markdown
# GUI Improvement Log: <panelId>

| Round | Score Before | Score After | Key Changes |
|-------|-------------|------------|-------------|
| 1 | 5/10 | 7/10 | 修复空指针、补充事件退订 |
| 2 | 7/10 | 8/10 | 优化列表滚动性能 |

## Round 1
### Issues Fixed
1. [CRITICAL] ...
### Review After Fix
[新审查结果摘要]

## Round 2
...
```

---

### Phase 7: gui-learn — 知识沉淀

**职责**：从本次开发（修 bug 或做需求）中提取经验，回写知识库。**核心是「泛化」**——
不只记录「这个 panel 发生了什么」，更要从 bug 现象 / 用户需求描述里抽出**可跨 panel 复用**的
通用教训、组件用法、性能优化经验，供后续任意任务参考。

> 所有写入目标均为 **`${CLAUDE_PLUGIN_DATA}/gui-knowledge/`**（跨插件版本存活，不进 git）。
> 下文出现的 `gui-knowledge/...` 路径一律指该持久化目录，**不是**插件内的只读 seed。
> 首次写入前若目录不存在，先从插件内 `gui-knowledge-seed/` 初始化；
> 写入前经 `pre-write-filter`（capture_filter.py）过滤环境噪音/瞬态错误，防污染固化为「知识」。

**触发条件**：**每次修 bug 或做需求完成**（PASS 或 2 轮 improve 结束）。即使本次没有 panel 级
产物（如纯逻辑/性能修复），只要从中学到可复用的东西，也必须沉淀到通用层。

**处理流程**：

> **两遍式（借鉴 ARIS `ingest`→`wiki-enrich`，详见 §十.2）**
> - **捕获遍**（每次必跑，便宜）：建实例条目 + 给通用层条目写**骨架**（`_TODO._` 占位）。
> - **充实遍**（可延迟，`/dev-gui-plugin:gui-learn enrich`）：把通用层骨架的 `_TODO._` 段填成 1–3 句结论，受 `--max` 上限约束、不动已填段。
>
> 知识分两层：**实例层**（`bugs/` `fixes/`，带 panelId，记录「发生了什么」）与
> **通用层**（`components/` `patterns/` `lessons/`，可跨 panel 复用，记录「下次怎么做」）。
> 每条实例都要追问「**这条经验脱离本 panel 后如何复用？**」，把泛化结果写进通用层。

**0. 写入前机械筛（capture_filter，§十.4）**
   任何条目持久化前先过 `python3 ${CLAUDE_PLUGIN_ROOT}/tools/capture_filter.py -`：命中
   `env_failure` / `transient_error` / `negative_tool_claim` / `single_instance_narrative` →
   **不存原文**，改存「怎么修 / 缺什么配置 / 它隐含的类级规则」或丢弃。

**A. 实例层（本次发生的事，带 panelId）**

1. **记录 Bug** → `gui-knowledge/bugs/<bug_id>.md` —— 现象 + 根因（file:line）+ 修复 + 验证；写 edges 关联到 component/pattern/lesson
2. **归档修复** → `gui-knowledge/fixes/<fix_id>.md` —— 成功/失败、变更、影响；失败也记并标**类级原因**（不是「某 MCP 当时挂了」这类操作噪音）

**B. 通用层（泛化后可跨 panel 复用 —— 每次必做）**

> ① **实例→类级规则**（ARIS capture-antipatterns 的核心变换）：
> 「B003 在 XXPanel 因未判空 SerializeField 崩」是**实例**；要存进通用层的是它隐含的**类级规则**
> 「SerializeField 引用在 OnXxx 使用前必须判空」。只存后者。

3. **组件用法** → `components/<slug>.md` —— 用法/坑点/性能特征；与已有条目 diff（新增 vs 补充 vs 冲突，去重见 §十.7）
4. **模式** → `patterns/<slug>.md` —— 新反模式建条目 / 印证已知追加案例 / 最佳实践同样收录
5. **通用教训·性能经验** → `lessons/<slug>.md` —— 结构化段（一句话教训 / 类级规则 / 可复用成分 / 适用场景 / 失败模式，schema 见 §四）；
   即使本次无 bug，只要用户描述或实现过程暴露可复用经验也要记

**C. 索引、晋升与摘要（确定性脚本，零 LLM）**

6. **写关系图 + 渲染关联** → 追加 `graph/edges.jsonl`，随后跑 `gui_knowledge.py render-connections`
   自动重渲染各页「## 关联」段（⑤：图是真相源，页内关联只读、禁手编）
   ```
   {"from":"bug:B001","to":"component:styles-module","type":"caused_by"}
   {"from":"lesson:L002","to":"pattern:missing-null-check","type":"generalizes"}
   ```
7. **晋升 load-bearing**（⑥ 拒/纳不对称，§十.6）：通用层条目默认 `status: proposed`；
   要进 query_pack（即被当规则加载）必须经**独立 reviewer（Bias Guard，全新上下文）批量确认**其
   「确为类级、正确、可复用」→ 置 `status: confirmed`。机械筛只能「拒」，「纳」需 reviewer 背书。
8. **重建 query_pack.md** → `gui_knowledge.py rebuild-query-pack`（确定性，§十.3）：
   只收 `status: confirmed` 通用层 + 反重复项；分段定额、每条抽一句话、截断回退换行、装配后注入扫描加 DATA 横幅。
9. **追加 log.md**
   ```
   ## 2026-06-16T15:30:00Z | panelId=XXX | verdict=PASS
   - 通用教训: 列表界面优先 ListModule 复用，避免每帧重建子节点（性能）
   - 实例 bug: B003 空指针-未判空 SerializeField → 晋升类级规则 L004(confirmed)
   ```

---

## 四、gui-knowledge 知识库 schema

### 知识条目字段定义 (`shared-references/knowledge-schema.md`)

> 两层:**实例层** `bug` / `fix`（带 panelId，记录发生了什么） · **通用层** `component` / `pattern` /
> `lesson`（脱离 panel 可复用，是 query_pack 优先加载、后续任务真正参考的部分）。
>
> **两个全局约定（借鉴 ARIS，§十）**：
> (a) 各条目的「## 关联」段一律由 `graph/edges.jsonl` **自动渲染**，禁止手编（⑤）；
> (b) 通用层条目按 scaffold→enrich 两遍式写：捕获遍留 `_TODO._`，充实遍填（②，§十.2）；
> (c) 通用层条目带 `status: proposed|confirmed`，仅 `confirmed` 进 query_pack（⑥，§十.6）。

#### Bug 条目
```yaml
---
type: bug
bug_id: "B001"
title: "StylesModule 未初始化导致空指针"
severity: CRITICAL | MAJOR | MINOR
component: "component:styles-module"
pattern: "pattern:missing-null-check"  # 可选
panel_ids: ["xxx", "yyy"]              # 受影响的界面
discovered: "2026-06-16T15:30:00Z"
status: resolved | unresolved
---
# <title>

## 现象
[用户可见的问题]

## 根因
[代码层面的原因，含 file:line]

## 修复
[变更内容]

## 验证
[如何确认修复有效]
```

#### Component 条目
```yaml
---
type: component
slug: "styles-module"
display_name: "StylesModule<TEnum>"
category: layout | input | display | navigation
status: proposed | confirmed          # confirmed 才进 query_pack
file_paths: ["client/.../StylesModule.cs"]
---
# <display_name>

## 基本用法
[代码示例]

## 已知坑点
1. [坑点描述 + 正确做法]

## 性能特征
[内存/CPU 注意事项]

## 关联（自动生成，勿手编）
_由 graph/edges.jsonl 渲染_
```

#### Pattern 条目
```yaml
---
type: pattern
slug: "missing-null-check"
category: anti-pattern | best-practice
severity: CRITICAL
status: proposed | confirmed          # confirmed 才进 query_pack
---
# <title>

## 描述
[反模式或最佳实践的描述]

## 案例
- [[bug:B001]]
- [[bug:B007]]

## 正确做法
[代码对比]
```

#### Fix 条目
```yaml
---
type: fix
fix_id: "F001"
bug_id: "B001"
outcome: success | failure
timestamp: "2026-06-16T16:00:00Z"
---
# Fix: <描述>

## 变更
[具体改动]

## 结果
[成功/失败 + 原因]
```

#### Lesson 条目（通用教训 / 性能经验 —— 通用层核心）

> 段落用 ARIS scaffold 风格：捕获遍留 `_TODO._`，充实遍（`gui-learn enrich`）填成 1–3 句。
```yaml
---
type: lesson
lesson_id: "L001"
slug: "list-reuse-over-rebuild"
category: general | performance | interaction-design | process
severity: high | medium | low
source: bug | requirement | review       # 这条教训从哪来：bug 根因 / 用户需求 / 审查
status: proposed | confirmed             # confirmed 才进 query_pack（⑥ 需 reviewer 背书）
panel_ids: ["xxx"]                        # 触发它的实例（溯源用，不限定适用范围）
---
# <一句话教训>

## 类级规则
[脱离 panel 的通用结论 —— 实例→类级泛化的结果]

## 可复用成分
[下次能直接拿来用的做法 / 代码骨架 / checklist 项]   _TODO._

## 适用场景
[什么情况下该想起这条]   _TODO._

## 失败模式 / 边界
[不适用或会反噬的情况]   _TODO._

## 关联（自动生成，勿手编）
_由 graph/edges.jsonl 渲染_
```

---

## 五、shared-references 契约文档

### 1. mvvm-contract.md
- Panel → ViewModel → View 数据流规范
- 属性命名约定
- 3-Phase 变更流程
- 生成文件「优先工具导出，导出失败才手改」硬规则 + 其它禁止事项

### 2. prefab-binding-contract.md
- [SerializeField] 绑定检查清单
- 节点命名约定
- StylesModule / ListModule 配置规范
- 常见绑定遗漏场景

### 3. verification-gates.md
- Type-A 门列表 + 验证脚本/命令
- Type-B 门列表 + subagent 调用方式
- 6 态裁决定义
- 门失败时的处理策略

### 4. knowledge-schema.md
- 上文第四节定义的 schema

### 5. acceptance-gate.md
- Type-A/B 分类决策树
- "一个 loop 可以 DRIVE，不能 ACQUIT" 原则
- Fan-out 同模型 breadth ≠ 跨模型 jury
- 与本 plugin 具体门的映射表
- **拒/纳不对称在知识沉淀的应用**：capture_filter（机械筛）可同模型「拒」；
  通用层条目晋升为 load-bearing（进 query_pack）需独立 reviewer 背书才能「纳」（§十.6）。
  无跨模型时以 Bias Guard 独立 subagent 替代 jury（较弱但优于自纳，如实标注）。

---

## 六、与现有 skill 体系的关系

### 隔离原则

| 外部 Skill | 本 Plugin 对应 | 关系 |
|-----------|---------------|------|
| `edit-prefab` | `gui-prefab` | **不依赖** — gui-prefab 自包含 Prefab 编辑指引 |
| `edit-excel` | `gui-config` | **不依赖** — gui-config 自包含配置表编辑指引 |
| `dev-gui` | `dev-gui-plugin` | **替代关系** — plugin 是新体系，旧 dev-gui 逐步迁移 |
| `bug-fix` | `gui-improve` | **互补** — gui-improve 专注 GUI 层面迭代，不替代 bug-fix |

### 运行时能力自选原则（不硬绑定）

本插件**不在内部硬编码任何外部 MCP 或 skill 依赖**。Prefab 编辑、Excel 配表、Unity 编译/运行期
检查等具体能力，由模型在运行时根据**当前会话已加载的 MCP/skill** 自行选择：
- 已加载对应能力 → 直接使用；
- 未加载 → 降级为静态判断并标注 `NOT_APPLICABLE`/`BLOCKED`，转人工，**不臆测报缺陷**。

好处：插件可独立演化、可在未装这些 MCP 的环境中降级运行；代价：具体能力的可用性由环境决定，
故验证门用 6 态裁决显式区分「没查 / 查不了」。

### 调用方式

```
# 完整 pipeline（由 orchestrator 串联）
/dev-gui-plugin:gui-plan
  → gui-draft → gui-prefab → gui-config
  → gui-review → gui-improve → gui-learn

# 单独使用某个阶段
/dev-gui-plugin:gui-review          # 仅审查已有 GUI 代码
/dev-gui-plugin:gui-learn           # 沉淀知识（捕获遍：建条目 + 通用层骨架）
/dev-gui-plugin:gui-learn enrich    # 充实遍：填通用层 _TODO_ 段（--max N 限批量）
```

> 知识晋升说明：`gui-learn` 写入的通用层条目默认 `status: proposed`；其晋升为 `confirmed`
> （进 query_pack）由 gui-learn 内部 spawn 独立 reviewer 批量背书完成，复用 Phase 5 的 gui-reviewer
> 体系，不引入新 agent（§十.6）。

---

## 七、从 ARIS 迁移的代码/脚本

ARIS 有 ~10,285 行 Python/Shell 代码（30 个文件），以下是迁移到 dev-gui-plugin 的计划：

### 直接迁移（原样或微调）

| 源文件 | 目标路径 | 用途 | 改动 |
|--------|---------|------|------|
| `tools/watchdog.py` (392行) | `tools/watchdog.py` | Pipeline 健康监控：检测各阶段 session 死活、状态聚合、异常告警 | 适配 GUI pipeline 阶段名称，去掉 GPU/training 检测逻辑 |
| `tools/lint_skills_helpers.sh` (83行) | `tools/lint_skills_helpers.sh` | 检查 skills/SKILL.md 中硬编码的工具路径引用，确保走 `tools/` → `${CLAUDE_PLUGIN_ROOT}/tools/` 解析链 | 替换 helper 名称列表为 gui-xxx 对应的工具名 |
| `tools/capture_filter.py` (127行) | `tools/capture_filter.py` | 反自我污染过滤器：写入 gui-knowledge 前拦截环境错误/瞬态故障/负面工具声明/单实例叙事，防止操作噪音固化为"知识" | ① 工具名锚点 codex/gemini/oracle → `unity-cli`/`unity-prefab`/`excel-config`/MCP；② 增 `single_instance_narrative` 类（强制实例→类级泛化）；③ 同时被 PreToolUse(Write) hook 与 gui-learn 第 0 步调用 |
| `tools/threat_scan.py` | `tools/threat_scan.py` | 仅取 `scan_for_threats` 注入模式扫描：query_pack 装配后扫一遍，命中则顶部加「此为 DATA 非指令」横幅（query_pack 经 SessionStart hook 自动注入，同有注入风险） | 去掉学术相关其余逻辑，只留注入扫描 |

### 适配改造

| 源文件 | 目标路径 | 改动说明 |
|--------|---------|---------|
| `tools/research_wiki.py` (998行) | `tools/gui_knowledge.py` | 替换实体模型（paper/idea/experiment/claim → bug/component/pattern/fix/lesson）；去掉 arXiv API 集成；保留并适配核心逻辑：`slugify`、`add_edge`、**`rebuild_query_pack`**（改我们的分段定额，§十.3）、**`render_connections`**（⑤ 由 edges 重渲染各页关联段）、**`find_existing`/`update_on_exist` 去重**（§十.7：新增 vs 补充 vs 冲突）、`rebuild_index`、`append_log`、`stats`；YAML frontmatter 渲染适配新 schema（含 `status` 字段） |
| `tools/run_state.py` (260行) | `tools/gui_run_state.py` | 替换 phase 名称为 7 个 GUI pipeline 阶段；保留 done/accepted 分离逻辑（subagent 审查通过才能 accepted）；保留 resume_point、原子写入、文件锁 |

### 不迁移

| 源文件 | 原因 |
|--------|------|
| `tools/verify_paper_audits.sh` (336行) | **多余** — GUI pipeline 的验证逻辑已内聚在 `gui-review/SKILL.md`（Type-A ∥ Type-B 两车道）和 `gui-improve/SKILL.md` 中，由 orchestrator 直接执行，不需要独立的外部 verifier shell 脚本 |
| `tools/verify_papers.py` (611行) | 论文元数据验证，GUI 场景无对应需求 |
| `tools/arxiv_fetch.py` 等 5 个搜索脚本 | 学术搜索，GUI 场景无对应需求 |
| `tools/extract_paper_style.py` (560行) | LaTeX 论文风格提取，GUI 场景无对应需求 |
| `tools/install_aris*.sh` / `smart_update*.sh` | ARIS 安装体系，Plugin 用 Claude Code 原生 marketplace 安装 |
| `tools/meta_opt/` | ARIS 自我优化钩子，GUI 场景暂不需要 |
| `tools/experiment_queue/` | 实验队列管理，GUI 场景无对应需求 |

---

## 八、实现计划

### 第一批：骨架搭建

1. 复用已生成骨架 `.claude/skills/dev-gui-plugin/`，最终迁/发布为 marketplace 插件
2. 编写 `.claude-plugin/plugin.json`（删除骨架里的 `"skills": ["./"]`，加 `$schema`，靠默认目录自动发现）
3. 创建 `README.md`
4. 创建 7 个 skill 目录 + SKILL.md 骨架（含标题和 description frontmatter）
5. 创建 `agents/gui-reviewer.md` 骨架
6. 创建 `gui-knowledge-seed/` 只读种子（README + index + 空 edges.jsonl）；运行期库写 `${CLAUDE_PLUGIN_DATA}`
7. 创建 `hooks/hooks.json` + handlers（**统一 Python**：`python3 ${CLAUDE_PLUGIN_ROOT}/hooks-handlers/...`，
   替换骨架默认的 `bun on-session-start.ts`；SessionStart 注入 query_pack、PreToolUse(Write) 跑 capture_filter）
8. 创建 `shared-references/` 5 个文档骨架
9. 从 ARIS 迁移落地 `tools/`（见 §七）：`gui_knowledge.py`（知识库引擎）、`capture_filter.py`、
   `threat_scan.py`、`gui_run_state.py`、`watchdog.py`、`lint_skills_helpers.sh`
   —— hooks 与 gui-learn 依赖它们，须在第二批 skill 填充前可用

### 第二批：核心 skill 填充

10. 完成 `gui-plan/SKILL.md` — plan mode 确认需求 + 人类审批逻辑
11. 完成 `gui-draft/SKILL.md` — 自包含 MVVM 代码生成指引
12. 完成 `gui-review/SKILL.md` — Subagent 审查流程 + Bias Guard
13. 完成 `gui-learn/SKILL.md` — 知识沉淀流程（两遍式 + 机械筛 + 晋升 + query_pack，§十）

### 第三批：验证与修复体系

14. 完成 `gui-review/SKILL.md` — 并行两车道（Type-B subagent ∥ Type-A 机械门）+ 合并 CRITICAL + 6 态裁决
15. 完成 `gui-improve/SKILL.md` — 迭代修复循环
16. 完成 `gui-prefab/SKILL.md` — Prefab 编辑指引
17. 完成 `gui-config/SKILL.md` — 配置表编辑指引
18. 完成 `agents/gui-reviewer.md` — 审查 subagent 完整定义（兼审查与通用层晋升背书）

### 第四批：契约文档

19. 完成 `shared-references/mvvm-contract.md`
20. 完成 `shared-references/prefab-binding-contract.md`
21. 完成 `shared-references/verification-gates.md`
22. 完成 `shared-references/knowledge-schema.md`
23. 完成 `shared-references/acceptance-gate.md`

### 第五批：验证

24. 用真实 GUI 开发任务跑通完整 pipeline
25. 验证 gui-knowledge 正确积累（实例层 + 通用层晋升 + query_pack 装配）
26. 验证 subagent 审查与晋升背书有效性
27. 根据反馈调整

---

## 九、关键设计决策记录

| 决策 | 理由 |
|------|------|
| 自包含 vs 引用外部 skill | 用户要求"不要耦合非 plugin 的 skill"。内容有少量重复，但换来完全独立演化和内聚 |
| Subagent 审查 vs 跨模型 | 当前阶段不需要 GPT 审查 Claude；用独立 subagent + Bias Guard 即可实现类似效果 |
| gui-knowledge 放 `${CLAUDE_PLUGIN_DATA}` | 用户决定。marketplace 分发下 `${CLAUDE_PLUGIN_ROOT}` 更新即替换、官方禁止写状态；故运行期知识库放持久化目录，**跨版本存活、不进 git、不团队共享**。插件仅内置只读 `gui-knowledge-seed/` 供首次初始化 |
| 7 阶段 vs 更多/更少 | UI Skill Lab 用 7 阶段控制 7 种漂移；对应 Unity GUI 的 4 种产出物（代码/Prefab/配置/知识）需各自审查+验证。原独立的 gui-verify 已并入 gui-review——其 Type-B 与 gui-review 是同一个 reviewer 跑两遍的重复劳动，合并为「一个验证阶段、并行两车道」后由 8 阶段收敛为 7 |
| gui-prefab ∥ gui-config 并行 + prefab 前置编译 | 用户决定。两阶段改的文件互不相交（`.prefab` vs Excel/`*_data.lua`），串行浪费墙钟——改为**并行组**：gui-prefab 跑主 agent、gui-config（涉及配置时）`run_in_background` spawn 到 subagent，orchestrator 在同一回合内用 `TaskOutput` 汇合并统一记两阶段状态，都落定后才进 gui-review。gui-prefab **改 prefab 前必须先触发 C# 编译**（View/ViewModel 进程序集、MonoScript GUID 就绪，才能挂脚本+绑 SerializeField），缺编译能力则 BLOCKED 不阻塞。状态机 `gui_run_state.py` 的 phase 顺序/语义/resume **不变**——并行是编排层行为；回合原子性保证 Stop 钩子看不到「prefab done 但 config pending」的中间态 |
| 6 态裁决 vs 3 态 | ARIS 的 6 态能区分"没查"(NOT_APPLICABLE)和"查不了"(BLOCKED)和"查出错"(ERROR)，避免静默跳过 |
| Pipeline 而非单体 | 参考前端 pipeline 最佳实践：每阶段控制一种漂移，Gate 失败时精确定位问题阶段，不必全流程重跑 |
| 不迁移 verify_paper_audits.sh | 多余 — ARIS 用它是因为 paper-writing 需要外部非 LLM 进程做 SHA256 新鲜度/裁决校验。GUI pipeline 中验证逻辑已内聚在 gui-review（Type-A ∥ Type-B 两车道）和 gui-improve 两个 skill 中，由 orchestrator 直接并行 Type-A self-check + Type-B subagent judge，不需要额外 shell 包装 |
| 迁移 watchdog.py | 复用它 session 存活检测和状态聚合模式，适配为 GUI pipeline 阶段监控（检测各阶段是否卡死/超时） |
| 迁移 lint_skills_helpers.sh | 复用它的硬编码路径检测逻辑，确保 plugin 内所有 SKILL.md 走统一的 `${CLAUDE_PLUGIN_ROOT}/tools/` 解析链 |
| 迁移 capture_filter.py | 复用反自我污染机械筛（env / transient / negative-tool / single-instance），保护 gui-knowledge 不写入操作噪音、强制实例→类级；经 PreToolUse(Write) hook + gui-learn 第 0 步触发 |
| 迁移 threat_scan.py | 注入扫描与反污染分工：capture_filter 管写入噪音，threat_scan 管 query_pack 装配后的注入横幅（query_pack 走 SessionStart 自动注入，有注入风险） |
| marketplace 分发形态 | 用户决定。放弃 `@skills-dir` 就地形态与 `--plugin-dir` 持久挂载，统一走 marketplace 安装/更新 |
| 导出产物「优先工具导出，导出失败才手改」 | 用户决定。所有导出/生成文件（MVVM 生成文件 `*_viewmodel.lua`/`*ViewModel.cs`/`AtomViewModelFactory.cs`/`ui_viewmodel_define.lua`，以及配表 `*_data.lua`）的硬规则：**优先用工具正式导出，不优先手改**；仅当工具导出失败/不可用时，才作为降级兜底手改补齐（加 `TODO(模拟导出)` 标记 + 记 `HUMAN_REVIEW.md`，待工具正式重新导出覆盖）。替代原「ViewModel 生成文件禁止手改」硬规则——禁止的是「能用工具却手改」，导出失败的兜底手改是允许的，保证管线不卡死 |
| 配置 *_data.lua 导出失败才镜像写入 | 用户决定。gui-config 改 Excel 源表后，`*_data.lua` 优先用工具导表；**工具不可用/导出失败时**才镜像手写（模拟导表），使运行期立即可见、管线零中断；正式 GDE 导表由人工在最终复核时执行（会覆盖模拟产物）。与上一行统一在「优先工具导出」硬规则下 |
| 无中途 HUMAN_CHECKPOINT，末尾统一复核 | 用户决定。agent 先把能做的全做完，所有需人确认项（Excel 正确性、运行期截图、未解决 CRITICAL、BLOCKED 项）汇总进 `HUMAN_REVIEW.md`，管线不停顿、跑到 gui-learn 才收口 |
| 不硬绑定 MCP/skill | 用户决定。具体能力运行时按已加载环境自选，插件保持自包含且可降级 |
| 接入 hooks/monitors | query_pack 注入用 SessionStart hook；知识写入过滤用 PreToolUse(Write) hook；watchdog（可选）对应 monitor 组件——复用插件原生机制而非裸脚本 |
| hooks-handlers 统一 Python | 用户决定。handler 与迁移脚本（capture_filter.py 等）同为 Python，hooks.json 用 `python3 ...` 调用，替换骨架默认的 bun handler，少装一个 runtime |
| run 产物放项目内 run 目录 | 用户决定。`${CLAUDE_PROJECT_DIR}/.claude/dev-gui-runs/<panelId>/`（gitignored）。与代码改动并排便于 review 与跨会话 resume；与 `${CLAUDE_PLUGIN_DATA}` 知识库分离（一次性·项目本地 vs 长期·跨任务） |
| 知识沉淀借鉴 ARIS Karpathy-Wiki | 用户决定，6 机制整合见 §十：两遍式 scaffold→enrich、实例→类级规则、确定性 query_pack、capture_filter 四类、关联自动渲染、通用层晋升需 reviewer。全部与 PLUGIN_DATA/不耦合外部 MCP/无跨模型/Python hook 兼容 |
| query_pack 装配确定性、零 LLM | 借 `research_wiki.rebuild_query_pack`：分段定额、抽一句话、回退换行、装配后注入扫描。内容由 LLM 写(捕获/充实)，摘要由脚本装(可重复、便宜) |
| 通用层 status: proposed→confirmed | ⑥ 拒/纳不对称：机械筛只能拒；进 query_pack(load-bearing)需独立 reviewer 背书。无跨模型时用 Bias Guard subagent 替代 jury，如实标注其较弱 |
| 双库共存（私有 + 项目公共） | 用户决定。私有库 `${CLAUDE_PLUGIN_DATA}/gui-knowledge`（个人、不进 git）+ 公共库 `${CLAUDE_PROJECT_DIR}/.claude/dev-gui-knowledge`（团队共享、走 p4）。两库共读、公共库为权威。**两个 skill**：`gui-learn` 写私有库（pipeline 默认）、`gui-learn-public` 写公共库（手动）。私有库对公共库语义去重（reviewer 判 duplicate/conflict → 公共库为准删私有条目）：gui-learn 在 promote/demote 点查、gui-learn-public 沉淀后对私有库 `--all` 全量 sweep。工具不自动调 p4（仅提醒）。详见 §十.9 |

---

## 十、知识沉淀机制（借鉴 ARIS Karpathy-Wiki，整合落地）

> 北极星（Karpathy LLM-Wiki）：知识**一次编译、持续更新、查询时不再重推**；乏味的是记账不是思考，
> 让模型一次性维护多文件交叉引用。下列 6 个机制把这条落到本插件，**全部与既有决策
> （PLUGIN_DATA / 不耦合外部 MCP / 无跨模型 / hook 统一 Python）兼容**。

### 十.1 总体数据流
```
修 bug / 做需求完成
  → gui-learn 捕获遍: capture_filter 机械筛(0) → 写实例层(A) → 实例→类级泛化写通用层骨架(B)
  → 索引: 写 edges → render-connections(⑤) → reviewer 批量晋升 proposed→confirmed(⑥)
          → rebuild-query-pack(只收 confirmed) + threat 扫描横幅(③) → append log
  → [可选] gui-learn enrich 充实遍: 填通用层 _TODO_ 段(②, --max 限批)
下次任意任务
  → SessionStart hook 读 query_pack.md 注入(经 threat 扫描，视为 DATA) → gui-plan 兜底确认
```
全部 tools 为插件内 Python（`${CLAUDE_PLUGIN_ROOT}/tools/`），非外部 MCP，不违反「不硬绑定」。

### 十.2 Scaffold→Enrich 两遍式（②）
- 捕获遍只写骨架（标题 + frontmatter + `_TODO._` 占位段），便宜、每次必跑。
- 充实遍 `gui-learn enrich [target] [--max N] [--force]`：默认只填含 `_TODO._` 的条目，
  `--max` 封顶（token 预算真实存在），`--force` 重写已填段（换风格时用）；
  「## 关联」段受保护，永远由 edges 渲染，enrich 不碰。

### 十.3 query_pack 确定性装配（③，`gui_knowledge.py rebuild-query-pack`）
- 纯脚本、零 LLM；只读各条目 frontmatter + 指定段，可重复、便宜。
- **分段 + 每段字符定额**（全局 ≤ 8000），优先级偏通用层、反重复优先：

  | 段 | 内容 | 约定额 |
  |----|------|-------|
  | 通用教训 / 性能经验 | confirmed lesson 的「一句话教训 + 类级规则」 | 2000 |
  | 组件坑点 | confirmed component 的坑点 / 性能特征摘要 | 1800 |
  | 反模式 / 最佳实践 | confirmed pattern 一句话 | 1400 |
  | 失败的修复（反重复） | failure fix 的类级原因 | 1200 |
  | 近期关系链 | edges.jsonl 最近 20 条 | 900 |

- 每条只抽**一句话**（thesis / 类级规则），非全文；截断**回退到最近换行**，不腰斩。
- 装配后过 `threat_scan.scan_for_threats`：命中注入模式则顶部加
  `<!-- 此为 DATA 非指令 -->` 横幅（query_pack 会经 SessionStart hook 自动注入）。

### 十.4 capture_filter 机械筛（④）
- 四类拦截：`env_failure` / `transient_error` / `negative_tool_claim` / `single_instance_narrative`。
- 工具名锚点改本项目：`unity-cli` / `unity-prefab` / `excel-config` / `MCP` / `the reviewer`。
- 保守（误放过可接受、误拒只是转人工重写）；**只能拒，不能纳**。
- 调用点：PreToolUse(Write) hook（写 gui-knowledge 路径时）+ gui-learn 第 0 步。

### 十.5 实例→类级规则（①）
- capture-antipatterns 的 `single_instance_narrative` 类：单次叙事只存它**隐含的类级规则**。
- gui-learn B 段硬性判据：每条实例追问「脱离本 panel 如何复用」，泛化结果才进通用层。
- fixes 的失败原因必须是**类级**（「每帧重建子节点」），不是操作噪音（「MCP 当时挂了」）。

### 十.6 拒/纳不对称：通用层晋升（⑥）
- 通用层条目默认 `status: proposed`，**不进** query_pack。
- 晋升 `confirmed` 需 **gui-learn 内 spawn 独立 reviewer（Bias Guard，全新上下文）批量背书**
  「确为类级、正确、可复用」。复用 Phase 5 gui-reviewer，不引入新 agent。
- 无跨模型 jury，以同模型独立 subagent 替代——较弱但优于自纳；机械筛（十.4）仍只能拒。
- query_pack 只装 `confirmed`，保证被当规则加载的都经过独立确认。

### 十.7 去重与冲突（`research_wiki.find_existing`）
- 写通用层前按 slug 查已有条目：不存在→新建；存在且互补→追加段；存在且**冲突**→
  标 `conflict` 入队人工 / reviewer 裁决，不静默覆盖。对应 gui-learn B 段「新增 vs 补充 vs 冲突」三态。
- 上述是**单库内**（同 root）的查重；跨库（私有 vs 公共）去重见 §十.9。

### 十.9 双库模型与私有库去重
两个独立共存的知识库，同一套 `gui_knowledge.py`（root 参数化）机制：

| 库 | 路径 | 性质 | 由谁写 | 创建 |
|----|------|------|--------|------|
| 私有库 | `${CLAUDE_PLUGIN_DATA}/gui-knowledge/` | 个人、跨版本、不进 git | `gui-learn`（含 pipeline 第 7 阶段） | gui-plan 首次运行自动 init |
| 公共库 | `${CLAUDE_PROJECT_DIR}/.claude/dev-gui-knowledge/` | 项目共享、团队维护、走 p4 | `gui-learn-public`（仅手动） | 仅 gui-learn-public 显式写入时 init |

- **共读**：SessionStart 注入、gui-plan、gui-draft 同时加载两库 query_pack；**公共库为权威**，矛盾以公共库为准。
- **两个沉淀 skill**：`gui-learn` 写私有库（pipeline 默认）；`gui-learn-public` 写公共库（用户主动声明时手动调）。
- **私有库去重**（仅私有库；公共库不被去重）：`find-dedup-candidates` 机械初筛公共库同主题候选
  （同 type + slug-token 相似，确定性零 LLM）→ `gui-reviewer` 语义裁决 `none|duplicate|conflict`
  → `duplicate`/`conflict` 以公共库为准、`remove` 硬删私有条目（记 superseded-by）。两个时机：
  - **点查**：gui-learn 私有条目 `promote`/`demote` 时。
  - **全量 sweep**：gui-learn-public 沉淀后，对私有库 `find-dedup-candidates --all` 收敛一次。
- **新增命令**：`demote`（confirmed→proposed，属「拒」无需背书）、`find-dedup-candidates`（机械初筛，支持
  单条 / `--all`）、`remove`（删条目+剔边+记 log）。
- **p4**：工具不自动调 p4，写公共库后由 gui-learn-public 收尾提醒用户手动 check out + submit。
- **反自毒筛**：PreToolUse(Write) hook 覆盖两库路径（`gui-knowledge/` 与 `dev-gui-knowledge/`）。

### 十.8 ARIS 出处对照
| 机制 | ARIS 出处 |
|------|----------|
| 两遍式 + scaffold 段名（Reusable Ingredients / Failure Modes） | `wiki-enrich/SKILL.md`、`ingest_paper` |
| query_pack 分段定额 / 一句话 / 回退换行 / 注入横幅 | `research_wiki.py:194-375 rebuild_query_pack` |
| capture_filter 四类 + 工具锚点 | `capture_filter.py`、`shared-references/capture-antipatterns.md` |
| 实例→类级规则 | `capture-antipatterns.md` single-instance-narrative |
| 关联自动渲染、图为真相源 | `research_wiki.py rebuild_index` + 各页 `## Connections` |
| 拒/纳不对称 | `shared-references/acceptance-gate.md` |
| 去重 find_existing | `research_wiki.py:_find_existing_page_by_arxiv` |
