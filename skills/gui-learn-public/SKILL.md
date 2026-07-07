---
name: gui-learn-public
description: >-
  把本次开发提取的经验沉淀进**项目公共知识库** ${CLAUDE_PROJECT_DIR}/.claude/dev-gui-knowledge/
  （团队共享、共同维护、走 p4）。流程与 gui-learn 相同，但写入目标是公共库：建实例层 bug/fix、
  泛化通用层 component/pattern/lesson、写 edges、独立 reviewer 晋升 proposed→confirmed、重建 query_pack。
  收尾两件事：① 提醒用户手动 p4 check out / submit（本 skill 不自动调 p4）；
  ② 触发一次「个人库 → 公共库」去重 sweep，把私有库里已被公共库覆盖/矛盾的条目删掉（公共库为准）。
  用户主动声明「沉淀进公共库 / 项目库」时调用；pipeline 自动流程仍用 gui-learn（写私有库）。
---

# gui-learn-public — 沉淀进项目公共知识库

**职责**：与 `gui-learn` 同样从本次开发提取经验、泛化、晋升、装配 query_pack，**唯一区别是写入目标
是公共知识库**。**仅在用户主动声明**（如「把这条经验沉淀进公共库 / 项目库」）时调用；
`/dev-gui-plugin:run` 流水线第 7 阶段仍调 `gui-learn`（写私有库）。

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

## 第一部分：沉淀进公共库（流程同 gui-learn 模式 A，root = 公共库）

完全复用 `gui-learn` 的捕获遍流程（机械筛 → 实例层 → 通用层 → edges → 晋升 → 重建），
**把所有 `gui_knowledge.py` 命令的 root 换成上面的 `"$KB_ROOT"`**。要点：

1. **写入前机械筛**（capture_filter）；PreToolUse hook 也会兜底拦截写 `dev-gui-knowledge` 路径的噪声。
2. **实例层** bugs/ fixes/，**通用层** components/ patterns/ lessons/（先 `find-existing "$KB_ROOT"` 同库查重，
   三态：新增 / 补充 / 冲突）。
3. **写 edges + render-connections**（root = `"$KB_ROOT"`）。
4. **晋升**：通用层默认 `proposed`，spawn `gui-reviewer` 背书「确为类级、正确、可复用」→ `promote "$KB_ROOT" ...`。
   > 公共库**不对任何库做反向去重**——它就是权威源；去重只发生在第三部分（私有库对公共库）。
5. **重建 query_pack + 索引**（`rebuild-index` / `rebuild-query-pack`，root = `"$KB_ROOT"`）+ 追加 `log`。

充实遍（填 `_TODO._`）同 `gui-learn enrich`，root 换成公共库。

---

## 第二部分：p4 提醒（本 skill 不自动调 p4）

公共库走 p4。写完后**列出本次在 `${CLAUDE_PROJECT_DIR}/.claude/dev-gui-knowledge/` 下新增/改动/删除的
文件**，提醒用户手动 check out 并 submit（check out / submit 的决定权留给人）：
```
本次已写入项目公共知识库（走 p4，未自动 check out）。请手动：
  p4 edit   <改动的文件...>
  p4 add    <新增的文件...>
  p4 delete <删除的文件...>
然后 p4 submit。
```

---

## 第三部分：个人库 → 公共库 去重 sweep（沉淀后必跑）

公共库刚长出新条目，私有库里可能已存在与之**重复或矛盾**的旧条目——两库一起注入会互相打架。
因此沉淀完立即对**私有库**做一次全量查重，**公共库为准**：

1. **机械初筛全量候选**（确定性、零 LLM）：
   ```bash
   PRIV="${CLAUDE_PLUGIN_DATA}/gui-knowledge"
   python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_knowledge.py" find-dedup-candidates --all \
       --root "$PRIV" --public-root "$KB_ROOT"
   ```
   输出私有库里**有公共库同主题候选**的条目工作清单 `[{node_id, title, candidates:[...]}]`；
   `[]` 表示无需 sweep，结束。

2. **spawn `gui-reviewer` 批量语义裁决**（全新上下文）：对清单每条私有条目 vs 其候选判
   `none | duplicate | conflict`。

3. **`duplicate` / `conflict` → 删私有条目**（公共库为准）：
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_knowledge.py" remove "$PRIV" \
       <私有 node_id> --reason swept-by-public --superseded-by <公共 node_id>
   ```
   `none` → 私有条目保留（与公共库不是一回事）。

4. **重建私有库索引与 query_pack**（删除即生效）：
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_knowledge.py" rebuild-index "$PRIV"
   python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_knowledge.py" rebuild-query-pack "$PRIV"
   ```

> 这一步只动**私有库**（删冗余），不改公共库；与 `gui-learn` 在 promote/demote 时机的去重互补：
> 那个是「私有库状态变更时」的点查，本 sweep 是「公共库刚增长后」的全量收敛。
