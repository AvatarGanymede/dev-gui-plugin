# gui-knowledge 知识条目 schema

> `gui-learn` 写条目、`gui_knowledge.py` 索引/装配的字段定义。两层：
> **实例层** `bug` / `fix`（带 panelId，记录发生了什么） · **通用层** `component` / `pattern` /
> `lesson`（脱离 panel 可复用，是 query_pack 优先加载、后续任务真正参考的部分）。

## 两个知识库（双库模型）

同一套 schema 与机械机制（`gui_knowledge.py`，root 参数化）服务**两个独立共存**的知识库：

| 库 | 路径 | 性质 | 由谁写 | 创建 |
|----|------|------|--------|------|
| **私有库** | `${CLAUDE_PLUGIN_DATA}/gui-knowledge/` | 个人、跨版本、不进 git | `gui-learn`（含 pipeline 第 7 阶段） | gui-plan 首次运行自动 init |
| **公共库** | `${CLAUDE_PROJECT_DIR}/.claude/dev-gui-knowledge/` | 项目共享、团队维护、走 **p4** | `gui-learn-public` command（仅手动调用） | **仅** gui-learn-public 显式写入时 init |

- **两库都被读**：SessionStart hook 注入、gui-plan、gui-draft 同时加载两库 query_pack。
  **公共库为权威**：两库内容若矛盾，以公共库为准（注入时公共库在前并标注）。
- 公共库的 status 语义与私有库相同（`proposed|confirmed`，仅 `confirmed` 进各自 query_pack）。
- **私有库去重职责**（公共库永远不对私有库去重）。机械初筛同主题候选用
  `gui_knowledge.py find-dedup-candidates`（单条 / `--all` 全量；同 type + slug-token 相似），
  再由 `gui-reviewer` 做语义裁决（`none|duplicate|conflict`）；`duplicate`/`conflict` → **以公共库为准，
  `gui_knowledge.py remove` 硬删私有条目**（记 `superseded-by`）。两个触发时机：
  - **点查**：`gui-learn` 在私有库条目 **promote / demote** 时，对该条查公共库。
  - **全量 sweep**：`gui-learn-public` 沉淀进公共库后，对私有库**全量**（`--all`）查一次——
    公共库刚增长，私有库里被它覆盖/矛盾的旧条目即时收敛删除。
- **p4**：写公共库的工具只动文件系统，**不自动调 p4**；`gui-learn-public` command 收尾提醒用户手动
  `p4 edit/add/delete` + submit。

## 全局约定（借鉴 ARIS，plan §十）

- (a) 各条目「## 关联」段由 `graph/edges.jsonl` **自动渲染**（`gui_knowledge.py render-connections`），
  **禁止手编**（⑤）。
- (b) 通用层条目按 **scaffold→enrich 两遍式**写：捕获遍留 `_TODO._`，充实遍填（②）。
- (c) 通用层条目带 `status: proposed|confirmed`，仅 `confirmed` 进 query_pack（⑥）；
  晋升须经独立 reviewer 背书（`gui_knowledge.py promote`）；降级 `gui_knowledge.py demote`
  撤销 load-bearing（属「拒」，无需背书）。

## node_id 约定

| 类型 | node_id | 例 |
|------|---------|----|
| bug | `bug:<bug_id>` | `bug:B001` |
| fix | `fix:<fix_id>` | `fix:F001` |
| lesson | `lesson:<lesson_id>` | `lesson:L002` |
| component | `component:<slug>` | `component:styles-module` |
| pattern | `pattern:<slug>` | `pattern:missing-null-check` |

edges.jsonl 行示例：
```
{"from":"bug:B001","to":"component:styles-module","type":"caused_by"}
{"from":"lesson:L002","to":"pattern:missing-null-check","type":"generalizes"}
```
合法 edge type：`caused_by` `generalizes` `fixes` `relates_to` `contradicts` `supersedes`
`instance_of` `addresses`。

---

## Bug 条目（实例层）

文件：`bugs/<bug_id>.md`

```yaml
---
type: bug
bug_id: "B001"
title: "StylesModule 未初始化导致空指针"
severity: CRITICAL | MAJOR | MINOR
component: "component:styles-module"      # 可选
pattern: "pattern:missing-null-check"     # 可选
panel_ids: ["xxx", "yyy"]                 # 受影响的界面
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

## Fix 条目（实例层）

文件：`fixes/<fix_id>.md`

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
[成功/失败 + 原因。失败原因必须是**类级**（如「每帧重建子节点」），
 不是操作噪音（如「MCP 当时挂了」）——后者被 capture_filter 拦截。]
```

> `outcome: failure` 的 fix，其「## 结果」一句话类级原因会进 query_pack「失败的修复」段（反重复）。

---

## Component 条目（通用层）

文件：`components/<slug>.md`

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

## Pattern 条目（通用层）

文件：`patterns/<slug>.md`

```yaml
---
type: pattern
slug: "missing-null-check"
category: anti-pattern | best-practice
severity: CRITICAL | MAJOR | MINOR
status: proposed | confirmed          # confirmed 才进 query_pack
---
# <一句话标题>

## 描述
[反模式或最佳实践的描述]

## 案例
- [[bug:B001]]
- [[bug:B007]]

## 正确做法
[代码对比]

## 关联（自动生成，勿手编）
_由 graph/edges.jsonl 渲染_
```

## Lesson 条目（通用层核心 —— 通用教训 / 性能经验 / 开发技巧）

文件：`lessons/<slug>.md`。段落用 scaffold 风格：捕获遍留 `_TODO._`，充实遍填成 1–3 句。

**准入范围不限于 GUI**：语法习惯、工具使用技巧、编辑器配置、调试方法、Shell 脚本模式等
通用开发经验均可作为 lesson 条目入库，只要满足「类级、正确、可复用」三标准。

```yaml
---
type: lesson
lesson_id: "L001"
slug: "list-reuse-over-rebuild"
category: general | performance | interaction-design | process | syntax | tooling | debugging | shell
severity: high | medium | low
source: bug | requirement | review       # 这条教训从哪来
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

> query_pack 从 confirmed lesson 抽「一句话教训（H1）+ 类级规则首句」。`# 一句话教训` 这行 H1
> 是被装配的关键，务必填实（非 `_TODO._`）。
