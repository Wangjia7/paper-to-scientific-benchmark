# 技能交付与新题目预检用例

这些测试在每次基于新论文生成数据后执行，而不是让 Agent 看见隐藏答案。

## 结构测试（自动）

- `python3 scripts/self_test.py` 必须输出 PASS。
- `python3 scripts/preflight.py --manifest private/manifest.json --root . --public-dir public --final` 必须没有 ERROR。
- `python3 scripts/preflight.py --manifest private/manifest.json --root . --emit-public-scorecard public/scorecard.json` 必须只输出评分元数据，不包含真值或 ID→组映射。
- `python3 scripts/score.py --manifest private/manifest.json --root . --submission work/reference_outputs` 参考提交应满足所有门槛。

## 前置价值拒绝测试（专家必须执行，不能靠脚本）

- 只有已给定公式和全部参数的论文：输出 `REJECT`，明确不再创建数据和评分器。
- 一篇只有单一盲测预测、40 个不同工况的论文：若平台要求 ≥3 独立判断且没有其他论文支持的机制，输出 `REJECT`，不把工况称为三问。
- 论文高影响力但只有不可识别的隐藏目标：仍输出 `REJECT`；不能以高影响力放行。
- 论文或补充材料缺关键页但可能有价值：输出 `INSUFFICIENT_EVIDENCE`，而非无证据批评。
- FP lensing V4 例子：明确说明为什么 A/B/C 分别满足证据、真值、独立评分，`GO` 才能继续。
- 每份拒绝必须写论文来源、具体不可克服原因、为何不能靠增量工程解决，并**停止**任务字段生成。

## 科学测试（专家/模型人工检查，不能仅靠脚本）

- 删除 A 的结论不会自动得到 B/C；三问各自的单位/对照/注入标签清楚。
- 每问至少两个合理科学方案的表现有可解释差异，且做过科学消融。
- 不使用任何隐藏真值调参的参考解可达到合格。
- 公开数据足以辨认目标：不是任意变量/密码/文件名的“盲猜”。
- 物理观测与仿真额外构造区分明确；没有虚构“论文已经验证”的结果。

## 评分隔离测试（自动，适配真实 grader）

- 真实答案与强基线、弱基线、零基线。
- 乱序 ID、容差边界、缺行、多行、未知 ID、重复 ID、非整数 ID。
- 空值、无穷、NaN、浮点数格式变体、单位错位。
- 单独将 B 的文件置为非法，A/C 原分保留，整体不合格。
- 让某一组不及最低通过数，但总分仍达 80，结果不合格。
- 确认公开 ZIP 不含 private/、隐藏真值、私有合成器、可直接复原隐藏答案的编码。

## 资源测试

- 在干净 Linux 容器安装最小开源依赖、从 public/ 目录运行参考程序。
- 记录 CPU 型号、核数、内存峰值、完整运行/软件调用耗时。
- 5 小时限制包括 Agent 探索、编译、运行和输出验证；参考程序用时数秒只能证实存在可解路径。
