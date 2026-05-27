# TAG Data Engineering

This project implements a Medallion architecture data pipeline for Microsoft Fabric, designed to move data from external sources through Landing, Bronze, Silver, and Gold layers.

## Architecture

The pipeline follows the standard Medallion architecture:

1.  **External → Landing (Extraction)**: Raw data extraction from source systems (APIs, Databases) into JSON files.
2.  **Landing → Bronze (Ingestion)**: Ingestion of raw JSON into Delta tables with deduplication.
3.  **Bronze → Silver (Transformation)**: Cleaning, validation, and business logic application.
4.  **Silver → Gold (Modeling)**: Aggregation and modeling for analytics and reporting.

## Data Pipeline Layers

### 1. Extraction (External → Landing)

**Purpose**: Extract data from source systems and write to the landing zone as JSON files.

**Process**:
-   **Full Refresh**: Currently supports full extraction of datasets.
-   **File Structure**: Data is split into batches and stored in `Files/<source>/<entity>/<run_id>/`.
-   **Tracking**: Each run is logged in `_metadata.landing_runs`.

### 2. Bronze Layer (Raw Data Ingestion)

**Purpose**: Load data from landing JSON files into Delta tables with minimal transformation.

**Key Features**:
-   **Metadata-Driven**: Uses `metadata.json` to define source, entity, and merge keys.
-   **Deduplication**: Removes duplicate records from the source files.
-   **Incremental Loading**: Tracks processed runs in `_metadata.landing_runs_processed` to only ingest new data.

### 3. Silver Layer (Business Logic)

**Purpose**: Apply business rules, data quality checks, and transformations to create clean, trusted datasets.

**Implementation**:
-   **SQL-Based**: Transformations are defined in `data.sql` files.
-   **Schema Definition**: Output schema is defined in `metadata.json`.
-   **Process**: Reads from Bronze, applies SQL transformations, and writes to Silver tables.

### 4. Gold Layer (Analytics & Reporting)

**Purpose**: Provide denormalized, aggregated views optimized for reporting.

**Structure**:
-   **Dimensions**: Reference tables (e.g., `dim_dates`, `dim_users`).
-   **Facts**: Transaction tables (e.g., `fact_appeals`).
-   **Implementation**: Similar to Silver, using `metadata.json` and `data.sql`.

## Configuration

The pipeline is configuration-driven. Metadata is located in `src/tag_data_engineering/transformations/`.

### Directory Structure
```
transformations/
  landing/
    <entity>/
      metadata.json         # Extraction config
  bronze/
    <entity>/
      metadata.json         # Bronze merge config
  silver/
    <entity>/
      metadata.json         # Schema definitions
      data.sql              # Transformation logic
  gold/
    <entity>/
      metadata.json
      data.sql
```

### Adding a New Entity

1.  **Landing**: Create `transformations/landing/<entity>/metadata.json` specifying the source and extraction mode.
2.  **Bronze**: Create `transformations/bronze/<entity>/metadata.json` specifying the merge key.
3.  **Silver**: Create `transformations/silver/<entity>/` with `metadata.json` (columns) and `data.sql` (logic).
4.  **Gold**: Create `transformations/gold/<entity>/` with `metadata.json` and `data.sql`.

## Development Workflow

### Prerequisites
-   Python 3.x
-   Docker (for local testing)
-   `uv` (Python package manager)

### Installation
```bash
make install
```

### Code Quality
Run linter and type checker:
```bash
make lint-check
make type-check
```
To automatically fix linting issues:
```bash
make lint-fix
```

### Testing
Run unit tests (requires Docker):
```bash
make test
```
Run integration tests:
```bash
make test-integration
```

## Deployment

The pipeline is deployed to Microsoft Fabric as a Data Pipeline orchestrating Notebook activities.

### Deploy Pipeline

Deploy the pipeline to Microsoft Fabric:

```bash
python scripts/pipeline_deploy.py \
  -w "Your_Workspace" \
  -p "pipeline_name" \
  -l "lakehouse_name" \
  -e "environment_name"
```

### Deploy with Schedule

To create a schedule that runs the pipeline automatically, use cron syntax:

```bash
# Run at 6:00 AM daily
python scripts/pipeline_deploy.py \
  -w "Your_Workspace" \
  -p "pipeline_name" \
  -l "lakehouse_name" \
  -e "environment_name" \
  --schedule "0 6 * * *"
```

Cron format: `minute hour day month day-of-week`
- All schedules run in UTC timezone
- Currently supports daily schedules

### Run Pipeline Manually

To trigger a pipeline run manually:

```bash
python scripts/pipeline_run.py -w "Your_Workspace" -p "pipeline_name"
```

-   **Jobs**: Located in `jobs/notebook/`.
-   **Orchestration**: Fabric Data Pipeline triggers notebook activities sequentially or in parallel based on dependencies.
-   **Schedule**: Optional - can be configured during deployment.

-   **ExtractionMetadata**: Configuration for landing extraction.
-   **TransformationRunner**: Orchestrates the transformation process.
-   **FabricLakehouseConnector**: Manages connections to the Fabric Lakehouse.
-   **LocalLakehouseConnector**: Enables local development using MinIO.
