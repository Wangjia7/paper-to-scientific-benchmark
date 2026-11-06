# 返修通过后的制度化回归（2026-11-05）

## 新增验收思路

- BAO V2 简单方法能完成 A/B/C：防止把三个独立参数估计当成研究判断。V3 中 GG-only 与无条件 GI 都总分接近通过，却不满足正确预注册的科学必要条件。已冻结的必要门不可事后针对特定基线修改。
- FP V4 的科学设计正确但附件错版：`fp_selection_response_v1` 的四文件公开 ZIP 必须被 V4 Release Lock 拒绝，即使 README 文案修改成 V4；V4 20 文件 ZIP 必须通过，并与私有评阅 ZIP 配对。
- Günther B01/B02/B03/B04：保证旧版 `qc_guard_self_test.py`、`self_test.py`、科学质量门矩阵脚本仍通过。
- Simba 2609.19993 的解释边界：验证 null reference 的类型（same-realization vs independent-box）、样本组成变动、同示踪体 2PCF、公私结构匹配是否被不当地等同真实环匹配。需要真实数据后才能测试，不能当作已通过。

## 软件测试

```
python scripts/self_test.py
python scripts/qc_guard_self_test.py
python scripts/release_lock_self_test.py
python scripts/difficulty_pilot_self_test.py
```

## 预期判据

- 正确 public/private/release text 的 ZIP：结构预检通过，但必须单独运行 private generator、grader、audit。
- 公开包缺任意 V4 关键文件、version 错误、成员 SHA 不符、输出模板行数错误、ID 别名、把私有真值混入 public：Release Lock 必须失败。
- Pilot 提交中任意普通方法已经通过**所有**必要科学门、没有 public-only 参考解、只有一个种子、日志不存在、评分合同在 final blind 后确定：结构门必须失败。
- 承认以上测试只处理工程一致性与已记录逻辑，不能代替科学家对机制与可辨识性的判断。
