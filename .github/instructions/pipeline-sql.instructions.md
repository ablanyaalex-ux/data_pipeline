---
applyWhen: editing data.sql files in the transformations directory
---

# Pipeline SQL Transformations — data.sql

Each `data.sql` file contains a plain `SELECT` statement only — no `CREATE TABLE`, no `INSERT`, no `CREATE OR REPLACE`. The runner wraps it.

## Rules by layer

### Silver (`transformations/silver/<entity>/data.sql`)
- Reads from `bronze.<entity>` (same entity name)
- Every column should be explicitly `CAST` to the target type, e.g. `CAST(id AS BIGINT) AS id`
- Rename columns where appropriate (e.g. `active` → `is_active`)
- Exclude or comment out sensitive columns with a comment explaining why
- No joins to other tables unless deriving a computed column

### Gold (`transformations/gold/<entity>/data.sql`)
- Reads from `silver.*` and/or other `gold.*` tables declared in the entity's `metadata.json` `dependencies`
- Silver columns are already typed — do **not** re-CAST columns that come from silver; reference them directly by their silver output name
- May use CTEs for intermediate logic
- Dimension tables: produce a surrogate or natural key column named `<entity>_id`
- Fact tables: produce foreign keys as `<dim>_id` columns, joined from `gold.dim_*` tables
- `gold.dim_dates` is joined on `CAST(<timestamp_col> AS DATE) = dd.calendar_date`
- Column name convention: snake_case; booleans prefixed `is_` or `has_`

## Style conventions
- Use `--` comments at the top to describe purpose; additional comments on complex logic
- Columns that are commented out (excluded) should stay in the file as `-- CAST(col AS TYPE) AS col` with a reason
- Prefer `LEFT JOIN` for optional relationships, `INNER JOIN` only when the relationship is guaranteed
- Always `CAST` source columns to explicit Spark SQL types before using them in output
