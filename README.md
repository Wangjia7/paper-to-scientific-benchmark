# paper-to-scientific-benchmark

把学术论文改造成科研 Agent 的标准化 benchmark / 想法设计 / 任务配置；**第一步先筛选是否值得出题，不值得时明确拒绝并停止，不为凑任务而制造假科研判断。** 默认检验 **科学决策性、至少三个独立判断、唯一客观评分、可复现及五小时内运行**。

## 在 Codex 使用

此压缩包包含一个顶层目录 `paper-to-scientific-benchmark/`，目录内有且只有一个 `SKILL.md`，以及 `references/`、`assets/`、`scripts/`。该结构遵循 OpenAI Skills 的标准形式。

将目录放在你的 Codex skill 搜索路径中。例如，若本地使用 `$CODEX_HOME/skills`（未自定义时通常是 `~/.codex/skills`）：

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R paper-to-scientific-benchmark "${CODEX_HOME:-$HOME/.codex}/skills/"
```

使用前先运行论文价值筛选：

```text
使用 $paper-to-scientific-benchmark 先审核这篇论文是否适合改造成科学 Agent 任务。
必须给出 GO、REJECT 或 INSUFFICIENT_EVIDENCE；如果不值得出题，直接指出论文依据与拒绝原因并停止，
不要硬凑三个判断、不要生成数据或评分器。只有 GO 才继续设计。
```

从新会话（或重载技能列表）使用：

```text
使用 $paper-to-scientific-benchmark，阅读这篇论文，把核心推导转化为一个需要至少三个独立科学判断、可自动验收、5 小时内可运行的科研 Agent 任务。先给出三问独立性矩阵及评分草案，通过质量门后再生成数据。
```

当收到评审拒绝意见：

```text
使用 $paper-to-scientific-benchmark，依据评审意见修订我的 benchmark。先判断是科研判断、独立性、评分唯一性，还是工程可复现性问题；只修改必要层，保证题面、数据、README 和评分器一致。
```

## 新增：明确拒绝不适合的论文

使用 `references/00-value-screening.md` 的五条必要条件评估，填写 `assets/paper-screening-template.md`；无科研判断、独立证据不足、真值不可识别或平台限制不可满足时输出 `REJECT`。证据缺失但可补时用 `INSUFFICIENT_EVIDENCE` 暂停，而不是臆断论文不值得研究。`REJECT` 的含义是当前平台**转题价值不足**，不是论文科研价值为零。

## 结构预检与评分样例

Python 3.9+，全部脚本仅依赖标准库（不会访问网络）。

```bash
python3 paper-to-scientific-benchmark/scripts/self_test.py
python3 paper-to-scientific-benchmark/scripts/preflight.py \
  --manifest paper-to-scientific-benchmark/assets/benchmark_manifest.example.json \
  --root paper-to-scientific-benchmark
```

示例 manifest 为设计样稿，真实数据文件不存在；`--final` 用于**已完成**的数据项目，必须提供私有真值 CSV。仅凭预检通过不能证明科研判断独立性，这必须有人审查科学定义。

## 与通过案例的关系

`references/06-fp-lensing-case.md` 追踪 Xu et al., arXiv:2609.09151v1 的四次设计迭代与最终三问结构。该 Skill **不附带**以前生成的 75 MB 合成观测数据及隐藏答案，以避免将一次实验的科学设置误当通用方法；如需复用原数据包，使用本次对话中的 V4 文件。

## 检查的性质

`preflight.py` 和 `score.py` 是**可复用的工具模板**，而不是平台官方评审程序。它们自动检查明确可程序化的结构规则，不会自动证明隐藏物理目标可识别、基线没有数据泄漏，或用户的实际 Agent 能在五小时内完成。

## 真实案例兼容性验证

开发时另用本对话的 V4 私有真值和参考预测，对 `scripts/score.py` 做了独立集成测试：得到 `A=38.2`、`B=27.0`、`C=30.0`，总分 `95.2` 且 `passed=true`，与 V4 原评分器一致。这个检查只验证**评分程序的可复算性**，不是证明任意新题目有足够科学难度。
