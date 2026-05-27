from pydantic import BaseModel


class IncrementalConfig(BaseModel):
    column: str  # Column to track changes (e.g., "updated_at")
    column_type: str  # Data type: "DateTime", "Int", etc.


class CopyJobExtractorConfig(BaseModel):
    source_connection: str  # Fabric connection name (must exist, managed externally)
    source_table: str | None = None  # Database table to extract (not needed for blob storage)
    source_schema: str | None = None  # Schema name (e.g., "dbo" for SQL Server)
    source_database: str | None = None  # Database name (for Azure SQL)
    source_type: str = "MySqlTable"  # MySqlTable, AzureSqlTable, etc.
    source_connection_type: str = "MySql"  # MySql, AzureSqlDatabase, etc.
    incremental: IncrementalConfig | None = None
    # For Azure Blob Storage copy jobs, we need additional fields to specify the container and file path
    source_container: str | None = None  # For Azure Blob Storage, the container name
    source_folder: str | None = None  # For Azure Blob Storage, the folder path (e.g., "verint_activity_mapping")
    source_sheet_name: str | None = None  # For Azure Blob Storage, Excel sources (e.g. "Raw Data 1")


# NOTE(krishan711): There is no actual CopyJobExtractor class implementation because
# the extraction is performed directly in Fabric using the InvokeCopyJob
# activity. This file only contains the configuration model used by the
# pipeline builder to create the Fabric Copy Job definition.
