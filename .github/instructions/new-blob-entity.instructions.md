---
applyWhen: adding a new blob-sourced or CSV-file-sourced entity to the pipeline
---

# Adding a New Blob-Sourced Entity (Full Stack)

Use this guide when a new CSV/file is being ingested from blob storage and needs to flow through the full Medallion stack (Landing → Bronze → Silver → Gold) with integration test coverage.

---

## Step-by-step process

### 1. Add the integration test fixture
Place a representative sample CSV in the mock blob store:
```
tests_integration/external_providers/tagdataengineering/ingest-data/<entity>/<entity>_<YYYYMMDD>.csv
```
- Use the same column names and realistic sample data (a few rows is sufficient)
- The filename date suffix (`_YYYYMMDD`) is used by `TO_DATE(REGEXP_REPLACE(...))` patterns in silver if `source_file_date` is needed

### 2. Landing `metadata.json`
```json
{
  "entity": "<entity>",
  "pipeline_group": "other",
  "extraction_mode": "full_refresh",
  "max_file_size_mb": 100,
  "output_format": "jsonl",
  "extractor": "blob",
  "extractor_config": {
    "source_container": "ingest-data",
    "source_folder": "<entity>",
    "blob_account_url_keyvault": "data-ingest-storage-credentials"
  }
}
```
- Use `"extraction_mode": "incremental"` if new files are appended over time and only new ones should be picked up
- `blob_account_url_keyvault` resolves via `MockSecretProvider` in tests (value `'{"account_name":"test123"}'` is already configured in `tests_integration/conftest.py`)

### 3. Bronze `metadata.json`
```json
{
  "schema": "bronze",
  "pipeline_group": "other",
  "table": "<entity>",
  "entity": "<entity>",
  "merge_key": ["<col1>", "<col2>"],
  "source_format": "jsonl"
}
```
- Choose `merge_key` columns that uniquely identify a row in the source file
- Use a list for composite keys
- No `data.sql` needed — bronze ingests directly from JSONL landing files

### 4. Silver `metadata.json` + `data.sql`
```json
{
  "schema": "silver",
  "pipeline_group": "other",
  "table": "<entity>",
  "merge_key": ["<col1>", "<col2>"],
  "dependencies": ["bronze.<entity>"]
}
```
SQL conventions:
- Backtick-quote source column names (they come from the CSV header and may clash with reserved words)
- `CAST` every column explicitly to its target type
- Parse non-ISO date strings with `TO_DATE(CAST(col AS STRING), '<format>')` — e.g. `'dd/MM/yyyy'` for UK dates
- Null/empty `effective_to_date` columns stay null after `TO_DATE`; no special handling needed

### 5. Gold `metadata.json` + `data.sql`
```json
{
  "schema": "gold",
  "pipeline_group": "all",
  "table": "dim_<name>",
  "merge_key": "<name>_id",
  "dependencies": ["silver.<entity>"]
}
```
- Generate a surrogate key with `SHA2(CONCAT(col1, '|', col2, '|', ...), 256) AS <name>_id`
- `pipeline_group` is always `"all"` for gold

### 6. Integration test expected CSVs

Create expected output files for all three layers:

```
tests_integration/results_expected/bronze/<entity>.csv
tests_integration/results_expected/silver/<entity>.csv
tests_integration/results_expected/gold/dim_<name>.csv
```

**Bronze column format notes:**
- Columns appear in the same order as the source CSV header, with `source_file_name` appended last
- Numeric columns inferred as `Double` by Spark; whole-number values appear with `.0` (e.g. `150.0`)
- Date strings in non-ISO formats remain as strings (e.g. `01/01/2024`)

**Silver column format notes:**
- `DATE` columns appear as `YYYY-MM-DD`
- `DECIMAL(p,s)` columns: whole numbers appear without decimal point (e.g. `150`); values with 1 significant decimal digit carry trailing zeros to fill the declared scale (e.g. `112.50` for `DECIMAL(10,2)`)
- Null values appear as empty fields

**Gold column format notes:**
- `SHA2(..., 256)` surrogate keys are 64-character lowercase hex strings
- Pre-compute them in Python: `hashlib.sha256(f"{col1}|{col2}|{col3}".encode()).hexdigest()`
- All other columns follow the same format rules as silver

**Important:** The exact numeric formatting of `DECIMAL` columns depends on the Spark/pandas version in use. If the integration tests fail on formatting, run the pipeline once, copy `tests_integration/results_actual/<layer>/<table>.csv` to `tests_integration/results_expected/<layer>/`, and commit the corrected file.

---

## Example: `finance_case_fees`

| Layer | Files |
|---|---|
| Landing | `transformations/landing/finance_case_fees/metadata.json` |
| Bronze | `transformations/bronze/finance_case_fees/metadata.json` |
| Silver | `transformations/silver/finance_case_fees/metadata.json` + `data.sql` |
| Gold | `transformations/gold/dim_case_fees/metadata.json` + `data.sql` |
| Fixture | `tests_integration/external_providers/tagdataengineering/ingest-data/finance_case_fees/finance_case_fees_20240101.csv` |
| Expected | `results_expected/bronze/finance_case_fees.csv`, `results_expected/silver/finance_case_fees.csv`, `results_expected/gold/dim_case_fees.csv` |
