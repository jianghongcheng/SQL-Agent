# 常用只读函数误拦修复

## 证据与改动

对 BIRD v2 的停止记录重放最后一个 SQL，保持只读 authorizer 和 VM 预算，发现 25 个 `LIKE`、21 个 `strftime`，以及若干 `instr`、`julianday`、`datetime` 调用被白名单拦截。53 个执行中断仍属于预算限制。本轮不扩大预算、不修复或掩盖模型生成的语法与语义错误。

[SQLite 官方函数说明](https://www.sqlite.org/lang_corefunc.html)确认 LIKE 运算符由 like 函数实现；[日期函数文档](https://www.sqlite.org/lang_datefunc.html)说明日期函数输入、输出和修饰符。基于实际失败和函数用途，在生产 `ContractSQLSession.FUNCTIONS` 增加 `like / instr / strftime / julianday / date / datetime` 六项。没有开放任意函数，load_extension 和 randomblob 仍被拒绝，外部访问、写入和 VM 限制保持原样。

日期函数允许依赖当前时间的调用，因此依赖 now 的任务仍需要明确时间口径，不能保证跨时间重跑一致。函数名称白名单假定注册连接使用可信 SQLite 内建函数，并不为任意用户注册的同名 UDF 提供安全保证。

六条最小生产执行器测试修复前均失败，修复后通过。补了两个禁止函数测试，完整回归 **121 passed**。没有临时调试日志进入运行代码。

## 全部 500 题冻结候选重放

运行 `scripts/replay_bird_function_policy.py`，对 v2 每题最后一个原始提议执行一次授权/运行/结果检查；没有调用模型，也没有运行核对器。它隔离检查执行能力变化，不是新的 500 题生成实验。提示里的可用函数列表会随白名单变化，但本次没有测量该提示变化对重新生成的影响。

| 指标 | v2 原结果 | 新执行器重放 |
|---|---:|---:|
| 参考结果一致 | 140 | 149 |
| 执行器 KEEP | 358 | 396 |
| 已评分但错误的 KEEP | 217 | 246 |
| KEEP 但参考无法评分 | 1 | 1 |

新增 38 个可执行候选，只有 9 个参考正确，29 个仍错；原有 140 个正确候选没有损失。正确新增 ID：532、629、1048、1139、1036、1084、1133、1102、901。

149/500=29.8% 仅是这批冻结候选的参考一致性，不是修复后模型新生成准确率，更不是生产准确率。旧错误数增加说明执行器不应承担语义裁判职责；通用任务仍需审核。不能把这项修改宣称为整体可靠性已经提高。

保存了所有 500 个唯一题号的原/新判定、运行轨迹、SQL 错误与必要的离线参考比较。原先 KEEP 的结果必须与旧输出完全一致；新增 KEEP 仅在执行后使用参考 SQL 评分。原有参考异常保持未知。执行前后所有数据库文件 SHA-256 一致，运行期间修改文件的源码哈希一致。

产物：`outputs/validation/bird_function_replay_v1/`，包括 summary、manifest、500 条记录、修复前失败分类、红测试日志、完整回归日志。

```bash
PYTHONPATH=src:. python scripts/replay_bird_function_policy.py \
  --output outputs/validation/function-replay-new
```

本轮关闭的是确认存在的函数误拦缺口。语义错误、执行预算触顶、模型持续生成非法 JSON、独立核对重复波动仍需分别处理。旧 500 题生成结果和核对结果未覆盖。
