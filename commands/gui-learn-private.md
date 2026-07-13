---
description: 手动沉淀经验到私有知识库，自动触发 reviewer 裁决晋升，不依赖 pipeline
argument-hint: "[本次学到的经验描述 / 上下文说明，可选]"
---

# /dev-gui-plugin:gui-learn-private — 手动沉淀私有知识库

你现在是 dev-gui-plugin 的知识沉淀执行者。用户主动调用本命令，要你把当前对话中学到的经验
沉淀进**私有知识库** `${CLAUDE_PLUGIN_DATA}/gui-knowledge/`，并在沉淀完成后**自动触发
reviewer 裁决**（晋升 proposed→confirmed + 对公共库去重）。

用户提供的上下文（可选，未提供则从当前对话自行提取）：

> $ARGUMENTS

---

## 铁律

1. **每次都跑完整流程**：捕获（实例层 → 通用层 → edges）→ reviewer 晋升裁决 → 重建 query_pack。
2. **不限于 GUI**：语法习惯、工具使用技巧、编辑器配置、调试方法、Shell 脚本模式等通用开发经验
   同样准入——只要满足「类级、正确、可复用」。
3. **不依赖 pipeline**：本命令独立运行，不需要 `gui_run_state.py` 记账、不建 run 目录。
4. **自动裁决，不等待用户确认**：reviewer 批量判完后直接执行 promote / remove，不中途询问。

---

## 执行步骤

### 0. 准备知识库根目录

```bash
KB_ROOT="${CLAUDE_PLUGIN_DATA}/gui-knowledge"
PUBLIC_ROOT="${CLAUDE_PROJECT_DIR}/.claude/dev-gui-knowledge"

# 私有库不存在则 init
if [ ! -d "$KB_ROOT" ]; then
  python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_knowledge.py" init "$KB_ROOT"
fi
```

### 1. 提取经验（从当前对话）

回顾本次对话中产生的经验，提取以下内容：

**A. 实例层**（本次具体发生了什么）：
- Bug：现象、根因(file:line)、修复、验证 → `bugs/<bug_id>.md`
- Fix：变更内容、结果（成功/失败，失败原因必须是类级）→ `fixes/<fix_id>.md`

**B. 通用层**（泛化后可跨场景复用——**核心产出**）：
- Component 用法/坑点 → `components/<slug>.md`
- Pattern（反模式/最佳实践）→ `patterns/<slug>.md`
- Lesson（通用教训/性能经验/开发技巧）→ `lessons/<slug>.md`

> **实例→类级规则**：只存泛化后的通用规则，不存单次叙事。例：「B003 在 XXPanel 崩」是实例；
> 存进通用层的是它隐含的类级规则「SerializeField 引用使用前必须判空」。

### 2. 写入前机械筛（每条必过）

```bash
echo "<条目正文>" | python3 "${CLAUDE_PLUGIN_ROOT}/tools/capture_filter.py" -
```
命中 `env_failure` / `transient_error` / `negative_tool_claim` / `single_instance_narrative` →
改存「怎么修 / 缺什么配置 / 它隐含的类级规则」或丢弃。

### 3. 查重 + 写入通用层条目

写每条通用层条目前先查重（三态：新增 / 补充 / 冲突）：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_knowledge.py" find-existing \
    "$KB_ROOT" --type <lesson|component|pattern> --slug <slug>
```

- 空输出 → 新建条目（`status: proposed`，充实段留 `_TODO._`）
- 已存在且互补 → 追加段，保留原 status
- 已存在且**冲突** → 不覆盖；标注 `conflict` 纳入 reviewer 裁决

### 4. 写关系图 + 渲染关联

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_knowledge.py" add-edge "$KB_ROOT" \
    --from <src_node_id> --to <dst_node_id> --type <edge_type>
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_knowledge.py" render-connections "$KB_ROOT"
```

合法 edge type：`caused_by` `generalizes` `fixes` `relates_to` `contradicts` `supersedes`
`instance_of` `addresses`。

---

### 5. 🔑 自动触发 reviewer 裁决（晋升 + 去重）

这是本命令的核心步骤——**无需用户催促，沉淀完立即裁决**。

#### 5a. 机械初筛公共库候选

对每条新增/变更的通用层 `proposed` 条目：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_knowledge.py" find-dedup-candidates <node_id> \
    --root "$KB_ROOT" --public-root "$PUBLIC_ROOT"
```

公共库可能不存在（尚无公共库），此时 `find-dedup-candidates` 输出 `[]`，跳过去重比对。

#### 5b. spawn `gui-reviewer` subagent 批量裁决

**用全新上下文** spawn `gui-reviewer`（加载 `${CLAUDE_PLUGIN_ROOT}/agents/gui-reviewer.md`），
传入：
- 每条待审条目的**完整内容**（title + 所有段落，不含「## 关联」自动生成段）
- 若 5a 有候选，附带公共库候选的 node_id/title/excerpt

对每条独立判断：

| 判断维度 | 问题 | 通过条件 |
|---------|------|---------|
| 晋升背书 | ① 确为类级？② 正确？③ 可复用？ | 三问全是 → `confirm`；任一否 → `reject` |
| 去重判定 | 与公共库候选语义关系 | `none` / `duplicate` / `conflict` |

**通用经验准入**：语法习惯、工具使用、IDE 技巧、脚本模式等非 GUI 经验，只要满足三问即正常晋升，
不因"不含 GUI 内容"而拒。

#### 5c. 执行 reviewer 裁决结果

根据 reviewer 输出的每条目 `{node_id, decision, dedup, superseded_by?, reason}`：

- `confirm` + `dedup:none`（或公共库不存在）→ **晋升**：
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_knowledge.py" promote "$KB_ROOT" \
      <node_id> --reviewer gui-reviewer --verdict-id <裁决标识>
  ```

- `confirm` + `dedup:duplicate|conflict` → **以公共库为准，删私有条目**：
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_knowledge.py" remove "$KB_ROOT" \
      <node_id> --reason duplicate-of-public --superseded-by <公共 node_id>
  ```

- `reject` → **不晋升**（保持 `proposed`），reason 写入条目底部 `## 裁决备注` 段。

#### 5d. 冲突条目人工提示

若存在 `conflict` 的条目（reviewer 判定与公共库矛盾），汇总列出：
```
⚠ 以下私有条目与公共库冲突，已删除（公共库为准）：
  - <node_id>: <title> → 被公共库 <公共 node_id> 覆盖
```
（公共库不存在的环境则无此输出。）

---

### 6. 重建 query_pack + 索引

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_knowledge.py" rebuild-index "$KB_ROOT"
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_knowledge.py" rebuild-query-pack "$KB_ROOT"
```

> query_pack 只收 `status: confirmed` 的条目；刚晋升的条目即刻生效，下次 SessionStart /
> gui-plan / gui-draft 自动注入。

### 7. 追加 log + 汇报

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_knowledge.py" log "$KB_ROOT" \
    "gui-learn-private | lesson Lxxx(confirmed): <一句话> | pattern Pxxx(confirmed): <一句话>"
```

---

## 收尾汇报

向用户输出本次沉淀摘要：

```
📚 gui-learn-private 完成

实例层：
  - bug:Bxxx — <title>
  - fix:Fxxx — <outcome>

通用层（已晋升 confirmed）：
  - lesson:Lxxx — <一句话教训>
  - pattern:Pxxx — <标题>

通用层（proposed / 未晋升）：
  - lesson:Lxxx — <拒绝原因>

冲突删除（公共库为准）：
  - <node_id> → <公共 node_id>

下次 gui-plan / gui-draft 将自动加载以上 confirmed 条目的经验。
```
