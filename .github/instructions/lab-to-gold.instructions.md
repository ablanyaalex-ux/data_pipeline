---
applyWhen: promoting a lab SQL file from Data_Pipeline_Lab into the gold layer of Data_Pipeline
---

# Promoting a Lab Transformation to Gold

Lab SQL files in `../Data_Pipeline_Lab/transformations/` are prototypes. When a lab transformation is mature and ready to become a production Gold entity, follow these steps.

## Source file format (lab)
Lab files look like:
```sql
CREATE OR REPLACE TABLE lab.<name> AS
SELECT ...
FROM silver.<source>_<entity>
LEFT JOIN gold.<dim_name> ...
```

## Target file format (gold)
Gold `data.sql` is a plain `SELECT` — no `CREATE OR REPLACE TABLE` header.

---

## Handling INSERT / VALUES-based lab SQL

If the lab SQL uses `INSERT INTO ... VALUES (...)` or `SELECT ... FROM VALUES (...)` instead of a `SELECT` from a silver/gold table, treat the data as a CSV and follow the full blob stack from **new-blob-entity.instructions.md** for Landing → Bronze → Silver → Gold.

Steps:
1. Create a CSV file with the static rows at `tests_integration/external_providers/tagdataengineering/ingest-data/<entity>/<entity>_<YYYYMMDD>.csv` — all rows can be included since the file is the source of truth
2. Follow the blob entity guide for Landing, Bronze, Silver, and Gold layers
3. The Gold `data.sql` is a plain `SELECT` from `silver.<entity>` with explicit `CAST` on every column
4. If there is no natural integer primary key, generate a surrogate: `SHA2(CONCAT(col1, '|', col2, ...), 256) AS <entity>_id`

## Renaming conventions

When the lab table name contains a vendor or system name (e.g. `puzzel`, `cms`, `verint`), rename the gold entity to a business-facing name that does not expose the underlying system. For example:
- `dim_puzzel_queues` → `dim_call_queues`

---

## Step-by-step process

### 1. Identify the entity name
The `<name>` comes from the `CREATE OR REPLACE TABLE lab.<name>` statement. This becomes the Gold entity folder name and table name (e.g. `dim_companies`, `fact_case_assignments`).

### 2. Create the entity folder
```
src/tag_data_engineering/transformations/gold/<name>/
```

### 3. Create `data.sql`
- Copy the SQL body (everything after `CREATE OR REPLACE TABLE lab.<name> AS`)
- Remove the `CREATE OR REPLACE TABLE ...` header line
- The result must be a plain `SELECT` statement (with any leading CTEs)
- Do not change any `silver.*` or `gold.*` table references — they are already correct for production
- Apply the gold SQL conventions: explicit `CAST`, snake_case column names, booleans with `is_`/`has_` prefix

### 4. Create `metadata.json`
```json
{
  "schema": "gold",
  "pipeline_group": "all",
  "table": "<name>",
  "merge_key": "<pk_column>",
  "dependencies": [
    "silver.<source>_<entity>",
    "gold.<dim_name>"
  ]
}
```
- Scan the `data.sql` `FROM` and `JOIN` clauses to build the `dependencies` list
- Include every `silver.*` and `gold.*` table referenced; exclude `lab.*` references (they must be replaced)
- Choose `merge_key` as the primary key of the output table (the `_id` column of the dimension or the fact grain key)
- `pipeline_group` is always `"all"` for gold

### 5. Check for lab-specific references
Lab SQL sometimes joins to other `lab.*` tables. Before promoting:
- Replace any `lab.<dep>` reference with the corresponding `gold.<dep>` (promote dependencies first if needed)
- Confirm all referenced `silver.*` and `gold.*` tables already exist in `transformations/`

### 6. Verify
- Run `make lint-check` — the SQL files are packaged as-is, so ruff won't flag them, but confirm no syntax issues
- Check `src/tag_data_engineering/pipeline/pipeline_discoverer.py` picks up the new entity by running `python scripts/print_dependency_graph.py` against the updated package
- If adding integration test coverage, add expected CSV results to `tests_integration/results_expected/`

---

## Example

Lab file `04_dim_companies.sql`:
```sql
CREATE OR REPLACE TABLE lab.dim_companies AS
SELECT
    CAST(id AS BIGINT) AS company_id,
    name,
    sector_id
FROM silver.cms_companies
LEFT JOIN gold.dim_dates dd ON CAST(created_at AS DATE) = dd.calendar_date
```

Becomes `transformations/gold/dim_companies/data.sql`:
```sql
SELECT
    CAST(id AS BIGINT) AS company_id,
    name,
    sector_id
FROM silver.cms_companies
LEFT JOIN gold.dim_dates dd ON CAST(created_at AS DATE) = dd.calendar_date
```

And `transformations/gold/dim_companies/metadata.json`:
```json
{
  "schema": "gold",
  "pipeline_group": "all",
  "table": "dim_companies",
  "merge_key": "company_id",
  "dependencies": [
    "silver.cms_companies",
    "gold.dim_dates"
  ]
}
```
