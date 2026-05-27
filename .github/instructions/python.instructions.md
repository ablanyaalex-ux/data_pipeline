---
applyWhen: editing Python files in this repository or in Data_Pipeline_Lab
---

# Python — TAG Data Engineering

## Data_Pipeline (this repo)
- Main package: `src/tag_data_engineering/`
- `connectors/` — `FabricLakehouseConnector` (production) and `LocalLakehouseConnector` (MinIO for local dev); both implement `LakehouseConnector` ABC
- `extractors/` — source system extraction classes (MySQL, Postgres, SQL Server, REST API, Blob, Verint)
- `transformations/` — metadata-driven config files only (not Python); loaded by `TransformationRunner`
- `runners/` — `TransformationRunner` (Bronze/Silver/Gold), `LandingRunner`, `LandingCopyjobNormalizeRunner`, `SetupRunner`
- `pipeline/` — `PipelineDiscoverer` scans `transformations/` and builds `PipelineDefinition` with dependency ordering
- `secrets/` — `AzureSecretProvider` (Key Vault) and `MockSecretProvider` (tests)
- `deployment/` — Fabric REST API client, pipeline/copyjob serialisation
- `metadata_schema.py` — Pydantic models validating `metadata.json` files
- Package manager: `uv`; `make install` to set up

## Data_Pipeline_Lab (`../Data_Pipeline_Lab`)
- `scripts/upload_lab_files.py` — syncs SQL files to Lakehouse `Files/transformations/lab/`
- `scripts/run_lab_notebook.py` — triggers `run_transformation` notebook with `layer=lab`
- `scripts/check_lab_sql.py` — validates SQL syntax locally
- No Python package; scripts only

## Testing
- Unit tests: `tests/` — no Docker required; `make test`
- Integration tests: `tests_integration/` — requires Docker + MinIO; `make test-integration`
- `tests/conftest.py` provides `MockDataFrame`, `make_mock_connector`, `make_row` helpers
- Integration tests run the full pipeline end-to-end and compare CSV output against `tests_integration/results_expected/`

## Code style
- Linter: `ruff` (line length 240); `make lint-check` / `make lint-fix`
- Type checker: `pyrefly`; `make type-check`
- Snake_case for all names; classes PascalCase

## Adding a new source entity (all four layers)
1. `transformations/landing/<entity>/metadata.json` — extraction config (extractor, source table, secret key)
2. `transformations/bronze/<entity>/metadata.json` — merge key + source format
3. `transformations/silver/<entity>/metadata.json` + `data.sql` — schema and SELECT from `bronze.<entity>`
4. `transformations/gold/<entity>/metadata.json` + `data.sql` — modelling SELECT from `silver.*` / `gold.*`
5. Integration test fixture data + expected CSVs — see `new-blob-entity.instructions.md` for blob sources

For blob-sourced entities, also create:
- `tests_integration/external_providers/tagdataengineering/ingest-data/<entity>/<entity>_<YYYYMMDD>.csv` — sample input fixture
- `tests_integration/results_expected/bronze/<entity>.csv`, `silver/<entity>.csv`, `gold/dim_<name>.csv` — expected pipeline output

## Adding a Gold-only entity (no new source)
If data already exists in Silver, only steps 3–4 above are needed (skip landing and bronze).
