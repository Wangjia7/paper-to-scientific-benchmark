# 09 — Grader Quality Assurance：计分逻辑、数值和序列化三重防线

## A. 任务设计阶段：质量门槛不可由其它得分补偿

给定评分权重 \(S=\sum_i w_i s_i\)，对每一条**科学必需命题**列出 domain × target 的质量门槛 \(g_{dt}\)。最终合格应为

\[
\mathrm{pass}=
\mathrm{files\_valid}\ \land\ (S\ge S_{\min})\ \land\
\bigwedge_j(S_j\ge S_{j,\min})\ \land\
\bigwedge_{(d,t)\in\mathrm{mandatory}}g_{dt}.
\]

- **示例**：三个观测区域分别需要可靠的联合协方差和来源比例，总计六格；每格有独立公开阈值。任何格失效，不可由别的区域或来源的高分补齐。
- **不应乱用**：不是所有单条预测/普通统计描述都必须达到满分；对哪些结果作为 *necessary* 应给出物理理由及可行参考路线。
- 同一个判断内有多个科学必需目标时，不能仅检查判断总分；同一个目标跨多个区域时，不能让严重局域错误隐藏在区域平均分中。
- 绝不使用未经公开的内部裁剪/隐含门槛；所有质量条件均写入题面、README 和评分器。
- 不能把门槛随意定得过紧；先用公开参考方法和固定**独立重复抽样**确定误差尺度、置信范围、容差临界值，再冻结合同和隐藏真值。不可按隐藏测试成绩反复微调阈值。

**反事实必测：** 保留 A/C 正确，只破坏 B 一个区域/一个关键指标；即使 B 总分和整题总分仍达到数值门槛，也必须 `passed=false`，其余独立任务继续报告原分数。随后破坏 B 的全部必要指标，再验证同样逻辑。

## B. 实际数值计算的安全性

### 必须检查中间数值，而不只检查文件输入

1. 所有输入必须满足科学定义：dtype、形状、finite、范围、对称/PSD、单位。
2. 每一个可能溢出的算子后检查 finite 与数学域约束，尤其 `difference`, `solve`, `quadratic form`, `trace`, `logdet`, `exp/log`, `loss`, `normalization`, `score`。
3. 对极端但 finite 的输入，求出稳定结果；若数学损失超出浮点表示范围，显式记为**远超门槛**而不是 `0` 或高分；非法数值导致对应科学输出无效，整题不过。
4. 只对已知 finite、且属于计算舍入误差范围的小负值作零裁剪。任何 `NaN` 参与裁剪都是错误。
5. JSON 必须 `allow_nan=False`；数学正无穷用于内部判别时，外部诊断以 `null` + 明确标志或固定状态字符串表示。
6. 对离散对象、非标准浮点输入以及矩阵病态进行极端测试，不用无物理根据的私有数值幅度封顶掩盖算法错误。

**推荐测试值**：`0`, `-0`, `±1e160`, `±1e200`, `±1e308`, 次正规数、`NaN`, `+Inf`, `-Inf`；协方差的极小/极大本征值、轻微非对称、允许的半正定边界及不允许的负本征值；损失恰好等于阈值、稍小和稍大。

本 Skill 的 `scripts/grader_guards.py` 提供**通用可复用示例**：严格 CSV、规范 ID 映射、IEEE float64 验证和安全 KL。这里的 KL 仅适用于明确需要 Gaussian KL 的 benchmark，**绝不能把它作为所有科研任务的固定评分公式**。真实 grader 仍必须跑专项测试。

## C. 解析与 ID 契约：既严谨又接受科学等价表示

| 保护对象 | 必须检查 | 应当接受 |
|---|---|---|
| CSV | 精确表头、无重复列、每一数据行列数匹配、必需单元格非空、行数及 ID 覆盖 | 允许的行重排、规范 CSV 引号与转义 |
| 候选 ID | 原样规范格式（ASCII 时不能宽松 Unicode）、公开候选全集成员、映射后 1:1、不重用实际对象 | 任意合法候选集合行次序；数据值相同但符合公开等价规则的表示 |
| NPZ 数值 | 非对象、无 pickle、规定 dtype 精度、shape、finite、适用的 PSD/sym | 若合同允许，IEEE binary64 big-/little-endian；只在类型验证后转换 |
| 输出反馈 | 所有必要 gate 都进入最终 `passed`，错误目标不影响其他独立目标的数值分数 | 有证据可审计的诊断 JSON，非法值不以 NaN/Infinity 原样输出 |

有意义的 `case_id` 不总是整数：不要在读取器中擅自用 `int()` 或 `str()` 规范化候选，避免不同字符串折叠到同一科学对象。仅在已经验证**成员资格与唯一性**的前提下通过公开映射获得内部索引。

## D. 私有包与独立复验协议

```
benchmark/
  public/README_AGENT.md
  public/SCHEMA.json
  public/inputs...
  private/grader.py
  private/reference_solver.py      # 只能读 public，不得读取 private truth
  private/truths...
  private/audit_qc.py              # 真正运行当前 grader 的正反例
  private/REVIEWER_README.md
  private/RESULTS.json             # 机器可读结果+各例 expected/observed
  generate.py / benchlib.py        # 可再生，不在 public ZIP
```

**真实运行顺序**：1. 从空目录只解压 public；2. 单独复制并运行参考解，不给它任何私有数据；3. 将提交产物传到另一个进程/目录运行私有 grader；4. 使用 generator 固定种子从头重生成并核对数组及哈希；5. 在同一冻结 grader 上执行故障注入、独立重复采样、性能和内存测试；6. 保留 stdout/stderr/exit code/资源日志及发布版本指纹。

不能用 `private/reference_solver.py` 存在、曾经算得高分、或旧版本日志代替本版复验。文件缺失应标明 `NOT_VERIFIED` 并暂停，而不是声称端到端成功。

## E. 评分器红队矩阵（**每次新题必测、按具体科学对象增补**）

| 类别 | 示例 | 必须验证的结果 |
|---|---|---|
| 正向/等价 | 正确公开参考解、合法行重排、规范引号、允许 dtype 字节序 | 分数/判定一致 |
| 跨域补分 | 仅损坏 LOW、MID、HIGH 的一项必需统计；一项全部坏 | 总分可能高但全题不过；其它任务数值分数不变 |
| 跨目标补分 | 均值/协方差全对、份额全错；反向亦然 | 必需目标不能被别的目标分数顶替 |
| 中间数值失败 | finite 1e160/1e200 均值、交错符号、巨大但 finite 协方差 | KL 不为零且不得获得通过 |
| 明确非法值 | NaN/Inf、float32、非法 shape、非 PSD、恶意/空字段 | 对应输出无效，全题不过 |
| 身份混淆 | Unicode 别名、非成员候选、重复真实位置、大小写/前后空格（合同不允许时） | 不能绕过实际候选数量限制 |
| CSV/ZIP 契约 | 额外/缺少列、重复表头、额外行、缺失行、重复 ID、错误目录 | 拒绝不合法文件，不忽略额外内容 |
| 边界 | KL/容差/PSD 界内、恰等于界、界外 nextafter | 与公开 `<=`/`<` 规则一致 |
| 数据隔离 | 从 public ZIP 查找 private/truth/generator；只给 public 的参考解 | 无泄漏且可运行 |

最低结论必须分成 `REFERENCE_PASSES`、`INVALID_REJECTED`、`SCIENTIFIC_FAILURE_REJECTED`、`SCIENTIFIC_EQUIVALENT_ACCEPTED`、`REPRODUCIBLE`、`RESOURCE_VERIFIED` 六类，不得以“113 个单测通过”的数量替代科学有效性审查。分类与运行产物应纳入评阅材料。

## F. 复用检查的边界

- `scripts/qc_matrix.py` 检查**必要门槛的声明覆盖**及可选的审计结论自洽性；不能证明测试真的运行，需要附实际 grader 日志。
- `scripts/qc_release.py` 配合 `assets/qc-release-manifest.example.json` 检查**评阅文件存在、版本指纹、日志文件可访问与 ZIP 隔离**；不证明运行日志真实、内容科学正确。
- `scripts/qc_guard_self_test.py` 测试通用函数在极端数值/CSV/ID 上的行为；不能替代具体 benchmark 的 `private/audit_qc.py`。
- `scripts/preflight.py`、`scripts/score.py` 是结构/示例工具；各题的真正 grader 应按照各题科学公式实现，并独立红队。
- 如果没有可执行私有包、未实际完成测试，就必须保留 `INSUFFICIENT_EVIDENCE` / `NOT_VERIFIED`，不得宣称已完成。
