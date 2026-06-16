# 接受门（acceptance-gate）

> 从 ARIS `acceptance-gate.md` 迁移，适配 GUI 场景。本插件「自报完成」与「被接受」分离、
> 「拒/纳不对称」的总纲。被 `gui-verify`（6 态裁决）、`gui-improve`（Bias Guard）、
> `gui-learn`（通用层晋升）、`gui_run_state.py`（done vs accepted）共同引用。

## 1. 核心原则：一个 loop 可以 DRIVE，不能 ACQUIT

- **DRIVE**：一个执行 loop（orchestrator / 修复循环）可以推进工作、自报「我做完了」(`done`)、
  驱动 resume。这是安全的**同模型自报执行完成**。
- **ACQUIT**：判定「做对了 / 可接受」(`accepted`) **不能由执行者自己下**。必须来自一个
  **独立判定源**：独立 reviewer subagent（Bias Guard，全新上下文）或确定性验证（编译通过、
  门 exit 0）。

落地：`gui_run_state.py` 的 `set` 只能写 `done`；`accept` 必须带 `--reviewer` + `--verdict-id`，
且阶段须先 `done`。执行者对自己的产出调 `accept` = 自我背书，工具会告警。

## 2. Type-A vs Type-B 分类决策树

```
这个检查需要「品味 / 领域判断」吗？
├─ 否 → Type-A（self-check）：机器可验证，orchestrator 自行判断
│        例：编译通过、Prefab 节点存在、绑定数量匹配、生成文件未被改
└─ 是 → Type-B（subagent judge）：交给独立 reviewer subagent
         例：交互逻辑正确性、性能反模式、布局合理性
```

- Type-A 可同模型自判（机械、低风险）。
- Type-B 必须独立 subagent（避免执行者为自己的实现辩护）。

## 3. Fan-out 同模型 breadth ≠ 跨模型 jury

- 多开几个同模型 subagent 并行审查 = **广度**（breadth），能多覆盖一些角度。
- 它**不等于**跨模型陪审团（jury）的独立性 —— 同模型有相同盲点。
- 本插件当前**无跨模型**：以 **Bias Guard 独立 subagent** 替代 jury —— 较弱，但优于自纳。
  **如实标注其较弱**，不要把同模型 breadth 当成跨模型独立性宣称。

## 4. 拒/纳不对称在知识沉淀的应用（⑥）

| 动作 | 谁可以做 | 机制 |
|------|---------|------|
| **拒**一条捕获 | 同模型即可（机械安全筛，低风险） | `capture_filter.py`（env/transient/negative-tool/single-instance 四类） |
| **纳**为 load-bearing（进 query_pack） | 需**独立 reviewer 背书** | `gui_knowledge.py promote`（带 reviewer + verdict） |

- 通用层条目默认 `status: proposed`，**不进** query_pack。
- 晋升 `confirmed` 由 `gui-learn` 内 spawn 独立 reviewer（复用 `gui-reviewer`，全新上下文）
  批量确认「确为类级、正确、可复用」后，调 `promote` 完成。
- 机械筛只能拒；纳必须经独立确认。query_pack 只装 `confirmed`，保证被当规则加载的都经独立背书。

## 5. 与本插件具体门的映射

| 概念 | 本插件落地 |
|------|-----------|
| done（自报执行完成） | `gui_run_state.py set ... done` |
| accepted（独立判定通过） | `gui_run_state.py accept ...`（reviewer + verdict） |
| Type-A self-check | `gui-verify` Type-A 门 |
| Type-B judge | `gui-verify` Type-B → `gui-reviewer` subagent |
| Bias Guard | `gui-review` / `gui-improve`：全新 subagent，不传实现细节 |
| 6 态裁决 | `GUI_VERDICT.json`（见 `verification-gates.md`） |
| 知识「拒」 | `capture_filter.py`（PreToolUse hook + gui-learn 第 0 步） |
| 知识「纳」 | `gui_knowledge.py promote`（reviewer 背书） |

## 6. resume 的接受语义

`gui_run_state.py` 的 resume **向前解析到第一个非终态（≠ {accepted, skipped}）阶段**——
不是第一个非 `done`。一个执行者自认 `done` 但崩在独立审查前的阶段，resume 时会被**重新验证**，
绝不静默跳过。这是「loop 可 DRIVE 不可 ACQUIT」在 resume 上的体现。
