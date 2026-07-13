---
description: 手动沉淀经验到项目公共知识库（团队共享、走 p4），自动触发 reviewer 裁决晋升，收尾对私有库全量去重 sweep
argument-hint: "[本次学到的经验描述 / 上下文说明，可选]"
---

# /dev-gui-plugin:gui-learn-public — 沉淀项目公共知识库

你现在是 dev-gui-plugin 的公共知识沉淀执行者。用户主动调用本命令，要你把当前对话中学到的经验
沉淀进**项目公共知识库** `${CLAUDE_PROJECT_DIR}/.claude/dev-gui-knowledge/`（团队共享、共同维护、
走 p4），沉淀完成后**自动触发 reviewer 裁决**，并**对私有库做全量去重 sweep**。

用户提供的上下文（可选，未提供则从当前对话自行提取）：

> $ARGUMENTS

---

## 铁律

1. **写入目标为公共库**：所有 `gui_knowledge.py` 命令 root = `${CLAUDE_PROJECT_DIR}/.claude/dev-gui-knowledge`。
2. **公共库是权威源**：只对私有库做去重，永不对公共库反向去重。
3. **收尾必做两件事**：① p4 提醒；② 私有库全量去重 sweep。
4. **不限于 GUI**：语法习惯、工具使用技巧、编辑器配置、调试方法等通用开发经验同样准入。

---

## 写入目标

```bash
KB_ROOT="${CLAUDE_PROJECT_DIR}/.claude/dev-gui-knowledge"   # 公共库：团队共享、走 p4
```

公共库**仅在显式写入时创建**：若目录不存在先 init（私有库不受影响）：
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_knowledge.py" init "$KB_ROOT"
```

> Schema 见 `${CLAUDE_PLUGIN_ROOT}/shared-references/knowledge-schema.md`；双库模型见同文件「两个知识库」段。

---

## 执行步骤

### 1. 提取经验（从当前对话）

回顾本次对话中产生的经验，提取以下内容：

**A. 实例层**：
- Bug：现象、根因(file:line)、修复、验证 → `bugs/<bug_id>.md`
- Fix：变更内容、结果（成功/失败，失败原因必须是类级）→ `fixes/<fix_id>.md`

**B. 通用层**（泛化后可跨场景复用——**核心产出**）：
- Component 用法/坑点 → `components/<slug>.md`
- Pattern（反模式/最佳实践）→ `patterns/<slug>.md`
- Lesson（通用教训/性能经验/开发技巧）→ `lessons/<slug>.md`

> **实例→类级规则**：只存泛化后的通用规则，不存单次叙事。

### 2. 写入前机械筛

```bash
echo "<条目正文>" | python3 "${CLAUDE_PLUGIN_ROOT}/tools/capture_filter.py" -
```

### 3. 查重 + 写入通用层

写每条通用层条目前先查重（三态：新增 / 补充 / 冲突）：
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_knowledge.py" find-existing \
    "$KB_ROOT" --type <lesson|component|pattern> --slug <slug>
```
- 空输出 → 新建（`status: proposed`，充实段留 `_TODO._`）
- 已存在且互补 → 追加段
- 已存在且**冲突** → 不覆盖，标注 `conflict` 纳入 reviewer 裁决

### 4. 写 edges + 渲染关联

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_knowledge.py" add-edge "$KB_ROOT" \
    --from <src_node_id> --to <dst_node_id> --type <edge_type>
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_knowledge.py" render-connections "$KB_ROOT"
```

---

### 5. 🔑 自动触发 reviewer 裁决（晋升）

spawn `gui-reviewer` subagent（全新上下文，加载 `${CLAUDE_PLUGIN_ROOT}/agents/gui-reviewer.md`），
对每条 `proposed` 条目判三问：确为类级？正确？可复用？

- `confirm` → 晋升：
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_knowledge.py" promote "$KB_ROOT" \
      <node_id> --reviewer gui-reviewer --verdict-id <裁决标识>
  ```
- `reject` → 不晋升（保持 `proposed`），reason 记入条目底部 `## 裁决备注` 段。

> 公共库**不对任何库做反向去重**——它就是权威源；去重只发生在第三步（私有库对公共库）。

### 6. 重建 query_pack + 索引

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_knowledge.py" rebuild-index "$KB_ROOT"
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_knowledge.py" rebuild-query-pack "$KB_ROOT"
```

### 7. 追加 log

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_knowledge.py" log "$KB_ROOT" \
    "gui-learn-public | lesson Lxxx(confirmed): <一句话> | component xxx(confirmed): <标题>"
```

---

## 收尾

### ① p4 提醒（不自动调 p4）

列出本次在 `${CLAUDE_PROJECT_DIR}/.claude/dev-gui-knowledge/` 下新增/改动/删除的文件，提醒用户：
```
本次已写入项目公共知识库（走 p4，未自动 check out）。请手动：
  p4 edit   <改动的文件...>
  p4 add    <新增的文件...>
  p4 delete <删除的文件...>
然后 p4 submit。
```

### ② 个人库 → 公共库 去重 sweep（必跑）

公共库刚长出新条目，私有库里可能已存在重复或矛盾的旧条目——两库一起注入会互相打架。

**2a. 机械初筛全量候选**：
```bash
PRIV="${CLAUDE_PLUGIN_DATA}/gui-knowledge"
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_knowledge.py" find-dedup-candidates --all \
    --root "$PRIV" --public-root "$KB_ROOT"
```
输出 `[]` → 无需 sweep，结束。

**2b. spawn `gui-reviewer` 批量语义裁决**：对清单每条私有条目 vs 候选判 `none | duplicate | conflict`。

**2c. 执行**：
```bash
# duplicate / conflict → 删私有条目（公共库为准）
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_knowledge.py" remove "$PRIV" \
    <私有 node_id> --reason swept-by-public --superseded-by <公共 node_id>

# none → 保留私有条目
```

**2d. 重建私有库索引**：
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_knowledge.py" rebuild-index "$PRIV"
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_knowledge.py" rebuild-query-pack "$PRIV"
```

---

## 汇报摘要

```
📚 gui-learn-public 完成

公共库新增（已晋升 confirmed）：
  - lesson:Lxxx — <一句话教训>
  - pattern:Pxxx — <标题>

公共库 proposed（未晋升）：
  - lesson:Lxxx — <拒绝原因>

私有库去重 sweep：
  - 删除 N 条（公共库已覆盖）
  - 保留 M 条（无冲突）

⚠ p4 提醒：请手动 check out 并 submit 公共库变更文件。
```
