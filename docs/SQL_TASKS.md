# Register a SQL task

Create an application-owned JSON file, e.g. `tasks.json`:

```json
[
  {
    "task_id": "employee_names",
    "question": "List employee names",
    "database": "company.sqlite",
    "contract": {
      "columns": ["name"],
      "non_null": ["name"],
      "min_rows": 1,
      "max_rows": 1000,
      "version": "1"
    }
  }
]
```

Database paths resolve relative to this JSON file. The database must already
exist. Set `RADMEASURE_SQL_TASKS=/absolute/path/tasks.json` in API and worker.
Configure a real planner endpoint for custom tasks. The default scripted planner
is intentionally limited to the synthetic employee-name demonstration.

Submit `task_id`, optional `question`, and optional `initial_sql`. Extra fields
such as database paths or contract overrides are rejected. The question must
stay within the registered task's output contract; a different output schema
requires a separately registered task/contract. Authentication currently grants
roles across the configured service, not per-dataset tenant permissions.

Only SQLite query sources are supported. Registered connections use `mode=ro`
and `query_only`; SQLite user-defined function names are allowlisted during
execution. Do not use this as a sandbox for hostile database files.

Review records notes and disposition of an existing stopped task. To try revised
SQL, submit another job with a new idempotency key. `completed` means runtime
checks passed; independently assess semantic correctness where it matters.
