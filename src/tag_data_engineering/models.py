from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from pydantic import Field


class SetupMetadata(BaseModel):
    pass


class ExtractionMode(str, Enum):
    FULL_REFRESH = "full_refresh"
    INCREMENTAL = "incremental"


class ExtractionMetadata(BaseModel):
    entity: str
    pipeline_group: str
    extraction_mode: ExtractionMode
    max_file_size_mb: int = 100  # Maximum size of each JSON file in MB
    output_format: str  # Output file format: 'jsonl', 'json', 'parquet', etc.
    extractor: str  # Type of extractor to use (e.g., 'rest_api', 'copy_job')
    extractor_config: dict[str, Any] = Field(default_factory=dict)  # Configuration specific to the extractor type

    @classmethod
    def from_json_file(cls, file_path: Path) -> "ExtractionMetadata":
        return cls.model_validate_json(file_path.read_text())


class TransformationMetadata(BaseModel):
    schema_name: str = Field(alias="schema")  # Maps 'schema' from JSON to schema_name
    pipeline_group: str
    table: str
    merge_key: str | list[str]  # Primary key for MERGE operations
    sql: str = ""  # SQL transformation; populated by PipelineDiscoverer
    overwrite_matching_existing_source_keys: bool = False
    source_merge_key: list[str] = Field(default_factory=list)

    model_config = {
        "populate_by_name": True,
    }

    @property
    def merge_key_list(self) -> list[str]:
        if isinstance(self.merge_key, list):
            return self.merge_key
        return [self.merge_key]

    @classmethod
    def from_json_file(cls, file_path: Path) -> "TransformationMetadata":
        return cls.model_validate_json(file_path.read_text())


class BronzeMetadata(BaseModel):
    """Metadata for bronze layer transformations.

    Attributes:
        schema_name: Target schema (default: bronze)
        table: Target table name
        entity: Entity name in landing (e.g., 'cms_companies')
        merge_key: Single key or composite key for deduplication/merge
        source_format: Format of landing files: jsonl, json, parquet, csv
        explode_fields: Optional list of struct columns to flatten/explode (e.g., ["attributes"])
    """

    schema_name: str = Field(alias="schema")  # Maps 'schema' from JSON to schema_name
    pipeline_group: str
    table: str
    entity: str  # Entity name in landing (e.g., 'cms_companies')
    merge_key: str | list[str]  # Single key or composite key
    source_format: str  # Format of landing files: jsonl, json, parquet, csv
    explode_fields: list[str] = Field(default_factory=list)  # Struct columns to flatten

    model_config = {
        "populate_by_name": True,
    }

    @property
    def merge_key_list(self) -> list[str]:
        if isinstance(self.merge_key, list):
            return self.merge_key
        return [self.merge_key]

    @classmethod
    def from_json_file(cls, file_path: Path) -> "BronzeMetadata":
        return cls.model_validate_json(file_path.read_text())
