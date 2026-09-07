# ContractSQL 面试交付标准

这是一份项目交付标准，不是公司招聘通过线，也不承诺拿到面试。岗位依据见已有的市场证据文档；那些岗位样本不是整个美国市场的代表性统计。

项目主线固定为：**将自然语言问题转成可审查的只读 SQL，记录工具证据，并用独立评估控制改动风险。**

## 必须具备的交付物

| 要求 | 判定证据 |
|---|---|
| 能用一分钟讲清问题和用途 | 一个问题、一个用户流程、一个失败例子，不按框架名单讲项目 |
| 能演示真正执行 | 本地提交任务、实际模型生成、数据库执行、查看结果、审核与轨迹 |
| 能解释边界 | 只读授权、查询预算、队列恢复、通用答案审核；不将契约检查当成语义证明 |
| 有完整可重复的实验 | 固定数据与源码、模型 digest、全部题目记录、独立答案、错误与成本一起报告 |
| 核心 SQL 行为有证据 | 先进行同协议模型对照，再在未用于调整的新数据库/问题上检查；不能只展示挑选成功题 |
| 能解释取舍和失败 | 哪个改动增加成本、哪个发生回归、为何没有上线；保留原始结果 |
| 简历描述可核查 | 项目归属真实，指标注明数据范围；无用户就不写用户量，无线上就不写线上收益 |

不设“达到 90% 就符合招聘要求”的任意阈值。面试准备要求的是能够解释实际结果、限制与工程决策；通用准确率不足仍然是项目风险，不能通过改名称消除。

## 目前已经验证的决策

- 独立核对器减少错误保留，但也误拒正确答案；不能称为提升答题能力。
- 关系计划在开发回归多答对 3/72，但调用翻倍且不确定区间跨零；不默认启用。
- 数据探查工具确实执行，但最终正确数从 39/72 变为 38/72；不默认启用。
- 已完成同协议模型比较与跨业务检查：模型在原开发题的优势未稳定迁移到新 schema，完整失败记录已保留。
- 冻结回归已完成：26 个已知问题 × 2 个实例 × 3 次重复，推理配置 142/156 正确，对照 102/156；p95 74.83 秒。保留全部 13 个错误和 1 次停止，不宣称通用生产准确率。
- 35 个原本正确的账单候选通过额外 24 个数据实例；这检查数据变化，不增加独立问题数。
- 工程回归 217 项通过：包括 WAL 并发写入下的任务读取快照，以及恶意/畸形 MCP 参数后进程继续处理请求。

## 展示交付

本地浏览器已验证真实指标查询、账单余额、数据过期拦截、审核记录和 token 展示；MCP 已验证认证、幂等提交与任务读取。完整实验页面包含 864 次不同协议的历史运行，不能把这些重复次数写成独立题目数。最新验收记录和重现命令见 [本地展示](LOCAL_DEMO.md)。

## 简历与口头讲解

现在可以用的保守项目描述：

> Built a read-only SQL agent with a durable job pipeline, bounded execution, human review, and auditable traces; developed reproducible evaluations that separate answer correctness from execution success and measure recovery, false acceptance, and model usage.

讲解按“问题 → 最小架构 → 一次实际执行 → 一项对照实验 → 已知限制”展开。不要把实验选项描述成必须全部启用的生产架构，也不要把公开模型的训练能力当成自己的模型研发成果。

可直接练习：[五分钟演示与追问](INTERVIEW_DEMO_GUIDE.md) · [一次真实 SQL 错误的技术说明](SQL_FANOUT_CASE_STUDY.md)。

可核查的评估描述（与上面的工程描述二选一或各一条）：

> Compared SQL generation configurations on 26 development questions across two database instances and three trials, improving correct candidates from 102/156 to 142/156 while documenting the 74.8-second p95 latency and retaining all failures for review.

这里的数字不能写成“生产准确率 91%”，也不能写成 156 道独立问题。面试前仍需自己实际讲解与操作；代码验收不能代替个人答辩能力。


## Small-scale product acceptance (2026-09-07 UTC)

See [PRODUCT_ACCEPTANCE.md](PRODUCT_ACCEPTANCE.md) for frozen inputs, failures
and reproduction. The default commerce task now accepts scalar, list and grouped
results on one registered database. Real browser login, three queries, approval
and history passed. First-run evaluation was 11/12 correct across six questions
and two synthetic datasets; all answers required review. An initial concurrent
polling failure was retained and fixed. Operational regression completed all
four concurrent requests (three correct; slowest 173.63 seconds) and five actual
process/transport fault checks using recorded SQL response fixtures. The full
suite passed 237 tests.

Explain the boundary clearly: result-shape/read-only checks do not prove question
semantics. A missing paid-order filter escaped those checks, and a repeated query
later confused paid revenue with net revenue. Human approval is an audit decision,
not an oracle. These measurements support local implementation and limited
reliability claims, not production accuracy, external adoption or an interview
success guarantee.
