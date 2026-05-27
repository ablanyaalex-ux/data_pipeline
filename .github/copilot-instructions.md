# Copilot Instructions — TAG Data Engineering

This workspace contains two related repositories that together form the full data engineering platform.

---

## Repository Overview

### Data_Pipeline (this repo)
The **core production data pipeline** implementing Medallion architecture on Microsoft Fabric.

- **Purpose**: Move data from external sources through Landing → Bronze → Silver → Gold layers
- **Key directories**:
  - `src/tag_data_engineering/` — main Python package (deployed as a wheel to Fabric Environment)
    - `connectors/` — `FabricLakehouseConnector` (production) and `LocalLakehouseConnector` (MinIO for local dev)
    - `extractors/` — source system extraction classes (MySQL, Postgres, SQL Server, REST API, Blob, Verint)
    - `transformations/` — metadata-driven config (`metadata.json` + `data.sql`) per entity, per layer
    - `runners/` — orchestration logic (`TransformationRunner`, `LandingRunner`, etc.)
    - `pipeline/` — pipeline discovery and Fabric Pipeline JSON serialisation
    - `secrets/` — Azure Key Vault and mock secret providers
  - `jobs/notebook/` — Fabric notebook entrypoints (`run_transformation.ipynb`)
  - `scripts/` — deployment scripts (`pipeline_deploy.py`, `pipeline_run.py`, etc.)
  - `tests/` — unit tests (no Docker required)
  - `tests_integration/` — end-to-end tests (requires Docker + MinIO)
- **Transformation config pattern**: each entity has a folder under `src/tag_data_engineering/transformations/<layer>/<entity>/` containing `metadata.json` (schema/merge/dependency config) and `data.sql` (plain SELECT logic)
- **Deployment**: `scripts/pipeline_deploy.py` builds the wheel, publishes it to a Fabric Environment, then deploys CopyJobs and sub-pipelines per group

### Data_Pipeline_Lab (adjacent repo at `../Data_Pipeline_Lab`)
A **SQL-first experimentation layer** that runs after the Gold layer of this pipeline.

- **Purpose**: Lightweight lab for iterating on SQL transformations without rebuilding the core wheel
- **Key directories**:
  - `transformations/` — numbered SQL files (`NN_<name>.sql`) executed at runtime
  - `sandboxbids_scripts/` — numbered SQL scripts for sandbox/BIDS analysis (not deployed)
  - `scripts/` — Python utilities (upload, run, check SQL)
- **Output layer**: `lab.*` tables in Microsoft Fabric Lakehouse
- **Execution**: SQL files are deployed to `Files/transformations/lab/` and run via the `run_transformation` notebook with `layer=lab`
- **No wheel rebuild required** for SQL-only changes in that repo

---

## Relationship Between Repos

- `Data_Pipeline` is the **production pipeline**; its Gold layer outputs (`gold.dim_*`, `gold.fact_*`) are the inputs to `Data_Pipeline_Lab`
- `Data_Pipeline_Lab` SQL files reference Silver and Gold tables produced by this repo
- Lab SQL files are often **prototypes for new Gold entities** — when a lab transformation is mature it gets promoted into `src/tag_data_engineering/transformations/gold/<entity>/` in this repo
- The `run_transformation` notebook (`jobs/notebook/run_transformation.ipynb`) handles execution for both the core layers and the `lab` layer
- Gold naming convention: `gold.dim_<name>` for dimensions, `gold.fact_<name>` for facts; Silver: `silver.<source>_<entity>`

---

## Layer Architecture

| Layer | Location | Config | SQL pattern |
|---|---|---|---|
| Landing | `transformations/landing/<entity>/` | `metadata.json` only | extractor config |
| Bronze | `transformations/bronze/<entity>/` | `metadata.json` only | ingest from landing JSON |
| Silver | `transformations/silver/<entity>/` | `metadata.json` + `data.sql` | SELECT from `bronze.*` |
| Gold | `transformations/gold/<entity>/` | `metadata.json` + `data.sql` | SELECT from `silver.*` / `gold.*` |

All paths above are relative to `src/tag_data_engineering/`.

---

## Common Patterns

- `data.sql` is a plain `SELECT` statement — no `CREATE TABLE` wrapper; the runner adds that
- `metadata.json` drives schema, merge key, pipeline group, and inter-entity dependencies
- All Gold entities belong to `pipeline_group: "all"`; Silver/Bronze/Landing use the source system name (e.g. `"cms"`, `"popla"`)
- Both repos use `uv` + `Makefile` for local dev; `make install`, `make lint-check`, `make test`
- CI uses Azure Pipelines (`azure-pipelines-check.yml`, `azure-pipelines-deploy.yml`)
- Target platform: **Microsoft Fabric** (Lakehouse, Notebooks, Data Pipelines)

---

## When Answering Questions

- If a question involves a table or column, check `src/tag_data_engineering/transformations/` in this repo first
- Gold SQL is in `transformations/gold/<entity>/data.sql`; Silver SQL is in `transformations/silver/<entity>/data.sql`
- Lab SQL is in `../Data_Pipeline_Lab/transformations/*.sql`
- The shared execution notebook is `jobs/notebook/run_transformation.ipynb`
- When a lab file is being promoted to Gold, see `.github/instructions/lab-to-gold.instructions.md`
