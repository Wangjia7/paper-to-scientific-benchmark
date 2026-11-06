# 技能交付与新题目预检用例

这些测试在每次基于新论文生成数据后执行，而不是让 Agent 看见隐藏答案。

## 结构测试（自动）

- `python3 scripts/self_test.py` 必须输出 PASS。
- `python3 scripts/preflight.py --manifest private/manifest.json --root . --public-dir public --final` 必须没有 ERROR。
- `python3 scripts/preflight.py --manifest private/manifest.json --root . --emit-public-scorecard public/scorecard.json` 必须只输出评分元数据，不包含真值或 ID→组映射。
- `python3 scripts/score.py --manifest private/manifest.json --root . --submission work/reference_outputs` 参考提交应满足所有门槛。

## 前置价值拒绝测试（专家必须执行，不能靠脚本）

- 只有已给定公式和全部参数的论文：输出 `REJECT`，明确不再创建数据和评分器。
- 一篇只有单一盲测预测、40 个不同工况的论文：若该平台明确要求多个科学判断，且没有其他论文支持的机制，输出 `REJECT`，不把工况称为三问。
- 论文高影响力但只有不可识别的隐藏目标：仍输出 `REJECT`；不能以高影响力放行。
- 论文或补充材料缺关键页但可能有价值：输出 `INSUFFICIENT_EVIDENCE`，而非无证据批评。
- FP lensing V4 例子：明确说明为什么 A/B/C 分别满足证据、真值、独立评分，`GO` 才能继续；说明三套独立实验只是当次实现。
- 每份拒绝必须写论文来源、具体不可克服原因、为何不能靠增量工程解决，并**停止**任务字段生成。

- Elbers 旧版三个独立合成数据题（固定误差回归、九选一、质量反演）：即使数据/文件独立也应退回 Gate 1，不能以三项分数当作科研判断通过。
- **共享实验正例**：同一批不同 LPT 阶数/起始红移/分辨率/质量的模拟提供三个具有专属证据和失败模式的结论，若符合物理可识别性，应允许进入下一关，不因只有一个数据集而拒绝。

## 科学测试（专家/模型人工检查，不能仅靠脚本）

- 删除 A 的结论不会自动得到 B/C；科学判断有不同命题与可识别的对照（允许共享同一批数据、参数甚至同一真值表）。
- 每问至少两个合理科学方案的表现有可解释差异，且做过科学消融。
- 不使用任何隐藏真值调参的参考解可达到合格。
- 公开数据足以辨认目标：不是任意变量/密码/文件名的“盲猜”。
- 物理观测与仿真额外构造区分明确；没有虚构“论文已经验证”的结果。

## 评分隔离测试（自动，适配真实 grader）

- 真实答案与强基线、弱基线、零基线。
- 乱序 ID、容差边界、缺行、多行、未知 ID、重复 ID、非整数 ID。
- 空值、无穷、NaN、浮点数格式变体、单位错位。
- 只使 B 的字段无效（即使三问共享一张 CSV），A/C 仍可独立计分且整体不合格。
- 让某一组不及最低通过数，但总分仍达 80，结果不合格。
- 确认公开 ZIP 不含 private/、隐藏真值、私有合成器、可直接复原隐藏答案的编码。

- 共享输出表的结构测试：在 `allow_shared_tables=true` 的示例中单列错误只影响该判断；同一 `judgment_id` 拆成多个 checkpoint **不能**冒充多科学判断。

## 资源测试

- 在干净 Linux 容器安装最小开源依赖、从 public/ 目录运行参考程序。
- 记录 CPU 型号、核数、内存峰值、完整运行/软件调用耗时。
- 5 小时限制包括 Agent 探索、编译、运行和输出验证；参考程序用时数秒只能证实存在可解路径。

## 新增 QC 实际审计（不是只看正确参考的分数）

执行 `python scripts/qc_guard_self_test.py`（NumPy/SciPy）和 `python scripts/qc_matrix.py --matrix assets/qc-coverage-matrix.example.json`。随后必须在**每一道真实题目的冻结版私有 grader**上运行 `references/09-grader-quality-assurance.md` 中的专项反例，并保存运行输出、脚本、命令、哈希。通用工具 PASS **绝不**代表实际题目 grader 已经过 QC。

- 本科学目标的必要域×必要指标都存在逻辑 AND 的 `hard gates`。一个区域的分布或来源份额错误，即使全题总分≥80、B≥18，也不能通过；其它科学判断分数不变。
- 输入所有元素有限也要测试中间溢出：`±1e160/±1e200`、正负交错、`1e308 I`。任何 KL `NaN/Inf` 都不能成为0损失或通过。输出诊断 JSON 必须是合法的严格 JSON。
- 身份验证必须遵守 ASCII 规范及公开候选集合；全角数字别名映射的相同科学位置不能被当作不同点。
- CSV 每一行多/少一列、重复表头/空值不能被静默忽略；合法引号和允许的行顺序不应改变科学得分。
- 私有评阅包含版本一致的 generator、truth、grader、public-only reference、审计/独立重复抽样、命令、日志。只给 public 的求解器在独立环境运行，私有评分独立运行。
- 测试通过状态分为 `REFERENCE_PASSES / SCIENTIFIC_FAILURE_REJECTED / INVALID_REJECTED / SCIENTIFIC_EQUIVALENT_ACCEPTED / REPRODUCIBLE / RESOURCE_VERIFIED`，任何缺失保留 `NOT_VERIFIED`。


## v2.4 B05 科学信息必要性与几何旁路回归

- 检查器自身合成对照应通过；把任意一次 `geometry_only` 合法结果替换成 v9 审核报告的 C=31.002741、总分 84.934793、JS=[0.006496,0.005615,0.003314] 后，必须返回 `PILOT_FAIL_SCIENCE_DECISION_BYPASS`。这不是对 Günther v2.3 的重新模拟。
- 使用同一未修改 grader，输入科学 blind/geometry、距离去重、旧一次排序、条件化及 public-only 参考的所有**真实结果**；必须包含 A/B/C、三个 JS 和 B 六必要条件。
- 仅换 24 个候选点布局但保留同一观测/后验物理，则**不能**声称完成独立物理条件复验。冻结后还应测试不同后验位置/物理响应/观测精度。
- 普通路线只要合法全部通过，不能因算法名被拒绝；下一版应回到科学数据生成器，而不能对 84.934793 事后抬阈值。
- 继续执行 B01–B04 安全回归以及 FP 错版 Release Lock；完成生产级审核时必须真正运行对应私有 grader，而非仅运行新 Skill 的逻辑审计。
