# 一个能执行、却把 38 算成 −24 的 SQL

账单 11 的金额为 100，两笔已结算收款为 30 和 20，两笔贷项为 5 和 7。问题要求余额，因此答案是 `100 − 30 − 20 − 5 − 7 = 38`。

一次真实模型输出却算成 −24。原始记录是
[`billing_transfer_v1/episode_0098.json`](../outputs/validation/billing_transfer_v1/episode_0098.json)，模型为 `qwen2.5-coder:14b`，使用当时的 SQL 文本 v1 提示。

关键错误结构如下：

```sql
SELECT i.id AS invoice_id,
       i.amount - COALESCE(SUM(r.amount), 0)
                - COALESCE(SUM(c.amount), 0) AS balance
FROM invoices i
LEFT JOIN receipts r ON i.id = r.invoice_id AND r.state = 'settled'
LEFT JOIN credits c ON i.id = c.invoice_id
GROUP BY i.id, i.amount
ORDER BY invoice_id;
```

两笔收款与两笔贷项产生四个组合，收款和贷项都被算了两遍：`100 − 100 − 24 = −24`。SQL 语法、列名、只读检查都可以通过，因此不能靠执行成功判定正确。

正确的结构是让每张明细表先回到“一张账单一行”的粒度，再连接：

```sql
SELECT i.id AS invoice_id,
       i.amount - COALESCE(r.total_receipts, 0)
                - COALESCE(c.total_credits, 0) AS balance
FROM invoices i
LEFT JOIN (
    SELECT invoice_id, SUM(amount) AS total_receipts
    FROM receipts WHERE state = 'settled' GROUP BY invoice_id
) r ON i.id = r.invoice_id
LEFT JOIN (
    SELECT invoice_id, SUM(amount) AS total_credits
    FROM credits GROUP BY invoice_id
) c ON i.id = c.invoice_id
ORDER BY i.id;
```

这是后续 Qwen3 14B 推理预检中实际生成的结构，见
[`quality_pilot_14b_v2/invoice_balance.json`](../outputs/validation/quality_pilot_14b_v2/invoice_balance.json)。它不是写进运行时的答案模板。预检只是已知问题的成功案例；配置是否值得采用，要看完整回归以及延迟。

完整回归也保留了反例：`quality_regression_v1/episode_0026.json` 的同模型查询正确预聚合了明细，却漏掉 `state = 'settled'`。因此，避免重复计数和保留所有业务条件是两个不同问题。展示中的显式业务词典不会混入无词典回归成绩。

`SUM(DISTINCT amount)` 也不是通用修复：两笔合法交易可以有相同金额，去重数值会丢掉真实交易。需要按实体粒度处理数据，而不是按金额去重。

这个问题改变了项目的评估方法：

- 测试答案由独立 Python 算术得出，在 Agent 执行结束后评分。
- 同一条生成 SQL 在两个数据实例上运行，避免只检查一次偶然匹配。
- 既记录错误结果，也记录停止与重试；不把停止当成答对。
- 通用 SQL 保持人工审核。固定业务参考查询属于另一种验证模式，不能混入盲测成绩。

面试时可以用这一例解释为什么需要评估、为什么执行反馈有边界，以及为什么“加一个 Agent”不自动解决数据语义。
