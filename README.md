# paper-to-scientific-benchmark (v2.4.0)

用论文中的真正科研问题构建可复现、可客观评分的 Agent 科研 benchmark，支持**强制价值否决（GO / REJECT / INSUFFICIENT_EVIDENCE）**。先审查可证伪性和模型/机制判断，再考虑数据与评分实现；无转题价值直接拒绝，**绝不人为凑难度或实验数**。

## 关键修正：三项科学判断 ≠ 三套实验

- 当前对话目标平台曾要求**三个有独立评分后果的科学判断**；但平台最初的通用说明要求的是“多个客观 checkpoint”，不是通用“三实验”门槛。数量应根据**实际评审**确定。
- 一个统一研究项目**可以只有一套模拟、一组观测数据、同一套校准/对照**，并由这些证据支持多个不同的物理结论。
- **科学独立性**：需要分别提出可证伪的命题、找到有区分作用的证据、设计彼此不自动替代的扣分结果；不等价于三个数据集/真值文件/输出文件。
- **内部关联性**：每项判断必须对同一总体研究问题有必要贡献，而不是为了凑三个额外创造不相关对象。
- 三个**单独的监督式数值预测**也未必构成足够的科学判断深度。详见 `references/07-elbers-revision-lessons.md`。

## 本次新增：Günther 两轮质检失效防护

除了科学判断独立性，本版要求逐一确认**不可补偿的科学必要结果**，并在真实私有评分器上用极端有限浮点、Unicode ID 别名和畸形 CSV 进行负对照。评分器接受正确答案只是开始，必须证明关键错误不会得到假高分。私有评阅包、仅 public 参考路线、固定数据再生及实际日志是发布前强制证据。详见 `references/08-gunther-qc-lessons.md` 和 `references/09-grader-quality-assurance.md`。

## v2.4.0 新增：返修成功/失败分层与 B05 科学预算冲突红队

- **BAO**：三个不同拟合对象仍可能只是常规数值恢复，必须实际跑 `Scientific Difficulty Pilot`。
- **FP V4**：题目设计合格不代表旧 V1 ZIP 可以交付；强制发行锁（`scripts/release_lock.py`），并从平台实际附件回读。
- **Günther B01–B04**：必要科学门不可补分，极端浮点与 CSV/ID 攻击失败必须 fail closed，私有参考可复验。
- **Günther v9 / B05**：纯几何最远点在全不读观测信息的前提下 C=31.002741、总分=84.934793、三个观测 JS <0.020 **合法通过**；新旧版评分验证不等于科学预算取舍有效。必须修改科学生成机制、控制观测后验差异与预算冲突并多物理条件对照，**不能按算法名拒绝或者提高阈值**。

见 `references/10-...` 至 `references/13-observation-conditioned-budget-b05.md`；新增 `scripts/conditional_budget_pilot.py` 与合成逻辑回归，**不把逻辑测试当作 v10 数据实测**。

## 在 Codex 中使用

将本 ZIP 的顶层 `paper-to-scientific-benchmark/` 目录放入 `$CODEX_HOME/skills`（默认 `~/.codex/skills`）：

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R paper-to-scientific-benchmark "${CODEX_HOME:-$HOME/.codex}/skills/"
```

调用示例：

```text
使用 $paper-to-scientific-benchmark 先判断论文在当前平台要求下是否值得改题。
必须先给出 GO / REJECT / INSUFFICIENT_EVIDENCE，明确论文出处；非 GO 停止。
若 GO，以一个连贯研究问题为中心，设计由科学证据分别检验的判断（本平台当前评审要求三个）。
允许共用同一套模拟/数据；不要为了满足数量创造独立实验、文件或无关图结构。
先给统一研究目标、判断/证据/真值/独立评分矩阵，确认后才做数据和评分器。
```

评审修订示例：

```text
使用 $paper-to-scientific-benchmark 分析本轮拒绝原因。
先判断评审指出的是配方执行、缺乏科学解释、同一预测拆组、评分不唯一还是资源问题。
不要自动拆成三套独立实验；只修改科学根因层并同步公开题面与私有评分契约。
```

## 目录

- `SKILL.md`：全部质量门与执行规则；
- `references/00-value-screening.md`：价值筛选与强制拒绝；
- `references/02-independence-tests.md`：**共享实验情况下的可证伪判断**；
- `references/05-review-playbook.md`：评审错误归因；
- `references/06-fp-lensing-case.md`：FP lensing 通过案例（方法示例，不是必须三个实验的证明）；
- `references/07-elbers-revision-lessons.md`：Elbers 旧设计失败的经验；
- `references/08-gunther-qc-lessons.md`：B01/B02/B03/B04 两轮 QC 失效与修复方案；
- `references/09-grader-quality-assurance.md`：必需硬质量门、极端数值/身份/格式红队、私有复验包协议；
- `references/10-revision-outcomes-and-failure-taxonomy.md`：BAO/FP/Günther/Simba 实际返修错误分类；
- `references/11-scientific-difficulty-and-identifiability-pilot.md`：预注册科学难度与可辨识性 Pilot；
- `references/12-release-identity-stage-and-evidence.md`：发行版本锁与错版附件回读；
- `references/13-observation-conditioned-budget-b05.md`：最远点合法通过后的主动采样信息必要性试验；
- `assets/`：筛选卡、平台字段模板、旧版单独文件 manifest，以及 `benchmark_manifest.shared_example.json`（**共享同一实验/真值/结果表的结构示例，不是科学解答**）；
- `scripts/`：结构预检、示例评分、科学质量门覆盖检查、评阅包/日志完整性检查、数值/CSV/ID 守卫与自动测试（其中数值守卫需 NumPy/SciPy）。

## 结构预检与评分示例

结构预检工具仅需 Python 3.9+ 标准库；`qc_guard_self_test.py` 的 Gaussian KL 专项数值示例需要 NumPy 和 SciPy。配置中的 `requirements.min_scientific_judgments` 按**目标平台的实际规定**调整；当前样例保留三个判断。`allow_shared_tables=true` 允许在同一个 CSV 里按列提交和评分多个科学判断（科学独立性仍需人工证明）。

```bash
python3 paper-to-scientific-benchmark/scripts/self_test.py
python3 paper-to-scientific-benchmark/scripts/qc_guard_self_test.py
python3 paper-to-scientific-benchmark/scripts/release_lock_self_test.py
python3 paper-to-scientific-benchmark/scripts/difficulty_pilot_self_test.py
python3 paper-to-scientific-benchmark/scripts/conditional_budget_self_test.py
python3 paper-to-scientific-benchmark/scripts/qc_matrix.py --matrix paper-to-scientific-benchmark/assets/qc-coverage-matrix.example.json
python3 paper-to-scientific-benchmark/scripts/preflight.py \
  --manifest paper-to-scientific-benchmark/assets/benchmark_manifest.example.json \
  --root paper-to-scientific-benchmark
```

示例 manifest 中无真实私有真值文件，因此此处**不使用** `--final`。有实际 benchmark 时应在公开/私有隔离环境运行 `--final` 和 `scripts/score.py`。预检不会自动认定科学独立性；五小时 Agent 完整求解也需要独立实测。

## 兼容性

原 FP lensing V4 的三项独立输出结构仍然有效。旧版参考评分器与新版评分器在不启用共享表时采用相同的默认计分逻辑；额外支持共享观测/同一张真值表内多物理标签。`references/06-fp-lensing-case.md` 内列示的 V4 分数为历史记录，不能当作本次修改的新实测结果。

## 真正发布新题目前的强制预检

使用项目的**实际**私有矩阵、日志和清单，而不是本 Skill 提供的示例文件：

```bash
python scripts/qc_matrix.py --matrix private/qc_quality_gates.json --audit private/qc_matrix_status.json
python scripts/qc_release.py --root . --manifest private/qc_release_manifest.json
python private/audit_qc.py  # 必须真正调用冻结版 private/grader.py 运行反例
```

`qc_release.py` 检查文件、ZIP 隔离、audit log 与现版 grader SHA；**不会**代替执行任务专用审计，更不能保证科学能力有效性或平台审核通过。`assets/qc-release-manifest.example.json` 只是字段模板：直接对 Skill 根目录运行该模板会正确地报缺少真实评阅文件。
