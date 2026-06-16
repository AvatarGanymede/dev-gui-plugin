# gui-knowledge 种子模板（只读）

这是 **gui-knowledge 知识库的种子骨架**，随插件分发，**只读**。

## 用途

首次运行时，若持久化知识库目录
`${CLAUDE_PLUGIN_DATA}/gui-knowledge/` 尚不存在，`gui-plan` / `gui-learn`
会把本目录（`gui-knowledge-seed/`）复制过去作为初始化骨架，然后所有运行期写入都落到
`${CLAUDE_PLUGIN_DATA}/gui-knowledge/`。

> ⚠ **运行期严禁回写本 seed 目录。**
> 插件本体（`${CLAUDE_PLUGIN_ROOT}`）每次更新即被替换，官方明确「不要在此写状态」。
> 真实知识库（bugs / fixes / components / patterns / lessons / query_pack / edges）
> 一律写持久化目录 `${CLAUDE_PLUGIN_DATA}/gui-knowledge/`，跨版本存活、不进 git、不团队共享。

## 初始化等价命令

种子复制后（或直接对持久化目录），运行：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/gui_knowledge.py" init "${CLAUDE_PLUGIN_DATA}/gui-knowledge"
```

会建出实例层 `bugs/` `fixes/`、通用层 `components/` `patterns/` `lessons/`、
`graph/edges.jsonl`，以及 `index.md` `log.md` `query_pack.md`。

## 知识条目 schema

见 `shared-references/knowledge-schema.md`（条目字段定义）与 plan §四。
