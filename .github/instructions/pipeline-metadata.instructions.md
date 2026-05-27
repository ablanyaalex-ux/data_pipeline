---
applyWhen: editing metadata.json files in the transformations directory
---

# Pipeline Metadata — metadata.json

Each entity folder under `src/tag_data_engineering/transformations/<layer>/<entity>/` requires a `metadata.json`. The exact fields differ by layer.

## Landing (`transformations/landing/<entity>/metadata.json`)
```json
{
  "entity": "<entity_name>",
  "pipeline_group": "<source_system>",
  "extraction_mode": "full_refresh",
  "max_file_size_mb": 100,
  "output_format": "jsonl",
  "extractor": "mysql|postgres|sql_server|rest_api|blob|verint",
  "extractor_config": {
    "source_system": "<source_system>",
    "source_secret_key": "<keyvault_secret_name>",
    "source_database": "<db_name>",
    "source_table": "<table_name>"
  }
}
```
No `data.sql` needed for landing.

## Naming conventions

- **Landing and Bronze** entity/table names must **not** use `dim_` or `fact_` prefixes — use descriptive names that reflect the source system or data content (e.g. `puzzel_call_event_codes`, `ref_schemes`, `ref_employee_aliases`)
- **Silver** table names follow the same convention as bronze — no `dim_` or `fact_` prefixes
- **Gold** is the only layer where `dim_` and `fact_` prefixes are used
- Avoid exposing vendor or system names in gold table names — use business-facing names (e.g. `dim_call_queues` not `dim_puzzel_queues`)
- All table names across all layers must be **plural** (e.g. `cms_complaints`, `puzzel_call_event_codes`, `ref_schemes`, `dim_cases`, `fact_case_assignments`)

---

## Bronze (`transformations/bronze/<entity>/metadata.json`)
```json
{
  "schema": "bronze",
  "pipeline_group": "<source_system>",
  "table": "<entity_name>",
  "entity": "<entity_name>",
  "merge_key": "<pk_column>",
  "source_format": "jsonl"
}
```
No `data.sql` needed for bronze (ingested directly from landing JSON).

## Silver (`transformations/silver/<entity>/metadata.json`)
```json
{
  "schema": "silver",
  "pipeline_group": "<source_system>",
  "table": "<entity_name>",
  "merge_key": "<pk_column>",
  "dependencies": [
    "bronze.<entity_name>"
  ]
}
```
`pipeline_group` matches the source system (e.g. `"cms"`, `"popla"`, `"puzzel"`).

## Gold (`transformations/gold/<entity>/metadata.json`)
```json
{
  "schema": "gold",
  "pipeline_group": "all",
  "table": "<dim_or_fact_name>",
  "merge_key": "<pk_column>",
  "dependencies": [
    "silver.<source>_<entity>",
    "gold.<dim_name>"
  ]
}
```
- `pipeline_group` is always `"all"` for gold
- `table` follows `dim_<name>` or `fact_<name>` convention
- `dependencies` lists every `silver.*` or `gold.*` table referenced in `data.sql`
- `merge_key` is the primary key column of the output table (e.g. `"case_id"`, `"case_status_transition_id"`)
