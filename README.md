# dev-gui-plugin

> Atom Game GUI 开发全流程 Claude Code Plugin —— 从需求到交付的 **7 阶段 pipeline**，含
> 长期记忆知识库、subagent 审查与 Type-A/B 验证门体系。

借鉴 [ARIS](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep) 的知识库持久化、
6 态裁决、Bias Guard 与拒/纳不对称机制，适配到 Unity MVVM GUI 场景。设计与决策详见
[`plan/plan.md`](./plan/plan.md)。

## 安装

本仓库同时是一个 **Claude Code 插件市场（marketplace）**，插件本体位于仓库根目录。

```bash
# 1. 添加市场（GitHub owner/repo 简写）
claude plugin marketplace add AvatarGanymede/dev-gui-plugin
# 或在 Claude Code 会话内：/plugin marketplace add AvatarGanymede/dev-gui-plugin

# 2. 安装插件
claude plugin install dev-gui-plugin@dev-gui-marketplace
# 或在会话内：/plugin install dev-gui-plugin@dev-gui-marketplace
```

调试期可临时挂载本地目录：

```bash
claude --plugin-dir /path/to/dev-gui-plugin
# 或先 add 本地路径：claude plugin marketplace add ./dev-gui-plugin
```

## 7 阶段 Pipeline

| 阶段 | Skill | 职责 | 控制的漂移 |
|------|-------|------|-----------|
| 1 | `gui-plan` | plan mode 交互确认需求 + 人类审批 → 精炼 `GUI_PLAN.md` 契约 | 需求理解 |
| 2 | `gui-draft` | MVVM 代码生成（Panel.lua + View.cs） | 代码实现 |
| 3 | `gui-prefab` | Prefab 编辑 + `[SerializeField]` 绑定 | Prefab 绑定 |
| 4 | `gui-config` | 配置表编辑（Excel 源表 + 镜像 `*_data.lua`，可跳过） | 配置数据 |
| 5 | `gui-review` | **唯一验证门·并行两车道**：Type-B 独立 subagent 审查（Bias Guard）∥ Type-A 机械门（编译/LSP/prefab/配置）→ `GUI_REVIEW.md` + 6 态裁决 `GUI_VERDICT.json` + `HUMAN_REVIEW.md` | 逻辑质量 + 机器验证 |
| 6 | `gui-improve` | 合并 CRITICAL 迭代修复（最多 2 轮，每轮重跑 gui-review 两车道） | — |
| 7 | `gui-learn`（内部） | 知识沉淀回写 `gui-knowledge`（两遍式 + 晋升 + query_pack），`user-invocable: false`，pipeline 自动调用，用户不可手动触发 | — |

### 调用

```
# ★ 一键全自动（显式编排，推荐）：gui-plan 先进 plan mode 确认需求 + 人类审批，
#   审批通过后从 gui-draft 起不停顿跑完余下阶段；缺必要信息时占位实现 + 留 TODO 注释，
#   统一收口到 HUMAN_REVIEW.md
/dev-gui-plugin:run BagPanel 新增批量出售按钮，prefab=Assets/UI/Bag.prefab

# 完整 pipeline（从入口 skill 起，靠各阶段「→ 进入下一阶段」软串联）
/dev-gui-plugin:gui-plan
  → gui-draft → gui-prefab → gui-config
  → gui-review → gui-improve → gui-learn

# 单独使用（仍对用户可见的入口）
/dev-gui-plugin:gui-plan             # 手动从头跑 pipeline（软串联）
/dev-gui-plugin:gui-review           # 仅审查已有 GUI 代码
/dev-gui-plugin:gui-learn-private    # 沉淀知识到【私有库】（自动触发 reviewer 裁决晋升）
/dev-gui-plugin:gui-learn-public     # 沉淀知识到【项目公共库】（团队共享/走 p4），并对私有库做去重 sweep
```

> **表现层隐藏**：`gui-draft` / `gui-prefab` / `gui-config` / `gui-improve` / `gui-learn`
> 这 5 个纯中间阶段在 frontmatter 设了 `user-invocable: false` —— **不出现在 `/` 菜单、用户无法手动调用**，
> 但 Claude 仍可在 pipeline 中自动调用（其 description 始终在上下文里）。
> 用户可见入口收敛为：`/dev-gui-plugin:run`（全自动 command）、`gui-plan`（skill）、`gui-review`（skill）、
> `gui-learn-private`（command）、`gui-learn-public`（command）。

> **命名空间**：插件命令的前缀是插件名，故命令实际为 `/dev-gui-plugin:run`。
> 若想用更短的 `/dev-gui:run`，需把插件改名为 `dev-gui`（`plugin.json` + `marketplace.json` 的 `name`）。

#### 全自动是怎么「保证」串联的

`/dev-gui-plugin:run` 做两件事把串联从「靠 skill 描述暗示」升级为「确定性编排」：

1. **显式编排 prompt**：命令本体写死「依次执行全部 7 阶段、阶段间不得停顿询问、缺信息占位+TODO」，
   并在开始时写一个自动驱动哨兵 `.autorun.json` 到本次 run 目录。
2. **Stop hook 调度器**（`hooks-handlers/on_stop_continue.py`）：每当 agent 想停下，调度器读
   `run_state.json`，若本次 run 带哨兵且还有阶段未推进（状态非 `done/accepted/skipped`），就
   `decision:block` 把 agent 拉回，指明**下一阶段**并要求继续；直到 gui-learn 完成才放行并清哨兵。
   - 仅对带哨兵的 run 生效 → **单独跑某个 skill 的手动用法完全不受影响**。
   - **会话隔离（严格）**：哨兵记录开启 autorun 的 `session_id`（由 `/run` 命令写入，`session_id`
     经 SessionStart hook 通过 `CLAUDE_ENV_FILE` 注入），调度器**只**驱动 `session_id` 与当前停止会话
     **完全匹配**的哨兵 → 同一项目下其它无关会话停止时**绝不会被误拉进流水线**。无 `session_id` 的
     哨兵（插件升级前的残留、或 `session_id` 捕获失败）一律**不驱动并就地退役（删除）**，避免老数据继续
     劫持旁观会话；归属其它存活会话的哨兵则原样保留，交由其自己的会话驱动。
   - 带 `nudges/max_nudges`（默认 30）计数上限，超限自动脱离并写 `.autorun.log`，避免无进展死循环。
   - 它是**驱动器**（保证向前串联）；跨 run 的「有没有卡住」健康巡检仍用 `tools/watchdog.py`。

## 关键设计

- **自包含**：MVVM/Prefab/配表指引内聚在 `shared-references/`（契约 + `patterns/` 进阶模式库），
  不依赖外部 `edit-prefab` / `edit-excel` skill。
- **不硬绑定 MCP**：Prefab/Excel/Unity 编译等能力运行时按已加载环境自选；缺能力则降级标注
  `NOT_APPLICABLE`/`BLOCKED`，转人工，绝不臆测报缺陷。
- **无中途暂停**：所有需人确认项统一收口到 `HUMAN_REVIEW.md`，管线跑完才收尾。
- **Bias Guard**：每轮审查用全新 subagent，不传实现细节，只从代码本身判断。
- **拒/纳不对称**：机械筛（`capture_filter`）只能拒；通用层条目进 query_pack 需独立 reviewer 背书。
- **done vs accepted**：执行者可自报 `done`，但 `accepted` 必须来自独立 reviewer / 确定性验证
  （`gui_run_state.py`）。

## 目录与产物

| 位置 | 内容 | 生命周期 |
|------|------|---------|
| `${CLAUDE_PLUGIN_ROOT}/` | 插件本体（skills/agents/hooks/tools/shared-references/seed） | 更新即替换（只读/易失） |
| `${CLAUDE_PLUGIN_DATA}/gui-knowledge/` | **私有**长期知识库（bugs/fixes/components/patterns/lessons/graph/query_pack） | 跨版本存活、个人、不进 git |
| `${CLAUDE_PROJECT_DIR}/.claude/dev-gui-knowledge/` | **公共**长期知识库（同结构）；团队共享、走 p4 | 仅 `gui-learn-public` 写入时创建 |
| `${CLAUDE_PROJECT_DIR}/.claude/dev-gui-runs/<panelId>/` | per-run 产物（PRD/REVIEW/VERDICT/IMPROVEMENT_LOG/HUMAN_REVIEW/run_state） | 一次性、项目本地、gitignored |

> 建议在项目 `.gitignore` 加入 `/.claude/dev-gui-runs/`。

## 目录结构

```
dev-gui-plugin/
├── .claude-plugin/
│   ├── plugin.json         # 插件清单
│   └── marketplace.json    # 市场清单（本仓库即 marketplace）
├── commands/                # 3 个 command（run / gui-learn-private / gui-learn-public）
├── skills/                 # 8 个 skill（gui-plan … gui-learn）
├── agents/gui-reviewer.md  # 审查 / 晋升背书 subagent
├── hooks/hooks.json        # SessionStart 注入 query_pack；PreToolUse(Write|Edit) 跑 capture_filter；Stop 驱动 pipeline 串联
├── hooks-handlers/         # on_session_start.py · pre_write_filter.py · on_stop_continue.py（统一 Python）
├── gui-knowledge-seed/     # 知识库只读种子（首次复制初始化）
├── shared-references/      # 5 份契约文档 + patterns/（AtomGUI 进阶模式库）
├── tools/                  # gui_knowledge.py · gui_run_state.py · capture_filter.py
│                           #   · threat_scan.py · watchdog.py · lint_skills_helpers.sh
├── plan/plan.md            # 设计与实现计划
├── LICENSE · .gitignore
└── README.md
```

## tools/

| 工具 | 用途 |
|------|------|
| `gui_knowledge.py` | 知识库引擎：init / add-edge / render-connections / rebuild-query-pack / rebuild-index / find-existing / promote / demote / find-dedup-candidates / remove / stats / log |
| `gui_run_state.py` | Pipeline 状态机：7 阶段、done vs accepted、resume、原子写入 + 文件锁 |
| `capture_filter.py` | 写入前机械筛：env / transient / negative-tool / single-instance 四类 |
| `threat_scan.py` | query_pack 装配后注入扫描（命中加 DATA 横幅） |
| `watchdog.py` | （可选）pipeline 健康监控：扫 run_state、标 STALLED/FAILED |
| `lint_skills_helpers.sh` | 检查 SKILL.md 是否走 `${CLAUDE_PLUGIN_ROOT}/tools/` 解析链 |

## License

MIT
