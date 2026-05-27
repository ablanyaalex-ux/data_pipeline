import logging
import math
from abc import abstractmethod
from datetime import date
from datetime import datetime
from typing import Any
from typing import Generic
from typing import Iterator
from typing import TypeVar

from pydantic import BaseModel
from pydantic import model_validator
from sqlalchemy import text
from sqlalchemy.engine import Engine

from tag_data_engineering.extractors.base_extractor import BaseExtractor
from tag_data_engineering.extractors.models import ExtractionBatch
from tag_data_engineering.models import ExtractionMetadata
from tag_data_engineering.models import ExtractionMode
from tag_data_engineering.secrets.secret_provider import SecretProvider


ConfigT = TypeVar("ConfigT", bound="SqlalchemyExtractorConfig")


class IncrementalColumnConfig(BaseModel):
    name: str
    type: str


class IncrementalConfig(BaseModel):
    columns: list[IncrementalColumnConfig]

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_shape(cls, data):
        if isinstance(data, dict) and "columns" not in data and "column" in data and "column_type" in data:
            return {
                "columns": [
                    {
                        "name": data["column"],
                        "type": data["column_type"],
                    }
                ]
            }
        return data


class SqlalchemyExtractorConfig(BaseModel):
    source_secret_key: str
    source_table: str
    incremental: IncrementalConfig | None = None


class SqlalchemyExtractor(BaseExtractor, Generic[ConfigT]):
    def __init__(self, secret_provider: SecretProvider, engine: Engine | None = None, chunk_size: int = 50_000):
        super().__init__(secret_provider=secret_provider)
        self._engine = engine
        self.chunk_size = chunk_size

    @property
    @abstractmethod
    def _config_class(self) -> type[ConfigT]: ...

    @abstractmethod
    def _get_or_build_engine(self, config: ConfigT) -> Engine: ...

    @abstractmethod
    def _quote_identifier(self, identifier: str) -> str: ...

    @abstractmethod
    def _quote_table(self, config: ConfigT) -> str: ...

    @abstractmethod
    def _source_name(self, config: ConfigT) -> str: ...

    def extract(
        self,
        metadata: ExtractionMetadata,
        cursor: dict[str, str | None] | None = None,
    ) -> Iterator[ExtractionBatch]:
        config = self._config_class.model_validate(metadata.extractor_config)
        engine = self._get_or_build_engine(config)
        source_name = self._source_name(config)
        query = f"SELECT * FROM {self._quote_table(config)}"
        if metadata.extraction_mode == ExtractionMode.INCREMENTAL:
            if config.incremental is None:
                raise ValueError("incremental config is required for incremental extraction mode")
            cursor_fields = config.incremental.columns
            if cursor and all(cursor.get(field.name) not in (None, "NULL") for field in cursor_fields):
                comparisons: list[str] = []
                for index, field in enumerate(cursor_fields):
                    equality_filters: list[str] = [
                        self._format_cursor_filter(
                            previous_field.name,
                            str(cursor[previous_field.name]),
                            column_type=previous_field.type,
                            operator="=",
                        )
                        for previous_field in cursor_fields[:index]
                    ]
                    equality_filters.append(
                        self._format_cursor_filter(
                            field.name,
                            str(cursor[field.name]),
                            column_type=field.type,
                            operator=">=" if index == len(cursor_fields) - 1 else ">",
                        )
                    )
                    comparisons.append("(" + " AND ".join(equality_filters) + ")")
                query += " WHERE " + " OR ".join(comparisons)
            query += " ORDER BY " + ", ".join(f"{self._quote_identifier(field.name)} ASC" for field in cursor_fields)
        rows_emitted = 0
        fetched_rows = 0
        new_cursor = cursor
        records: list[dict[str, Any]] = []
        with engine.connect().execution_options(stream_results=True) as connection:
            result = connection.execute(text(query)).mappings()
            logging.info(f"{self.extractor_type} extractor executed query for {source_name}")
            for row in result:
                normalized_record: dict[str, Any] = {}
                for key, value in row.items():
                    normalized_key = str(key)
                    if value is None:
                        normalized_record[normalized_key] = None
                    elif isinstance(value, datetime):
                        normalized_record[normalized_key] = value.isoformat()
                    elif isinstance(value, date):
                        normalized_record[normalized_key] = value.isoformat()
                    elif isinstance(value, float) and math.isnan(value):
                        normalized_record[normalized_key] = None
                    else:
                        normalized_record[normalized_key] = value
                records.append(normalized_record)
                fetched_rows += 1
                if config.incremental is not None:
                    new_cursor = {}
                    for field in config.incremental.columns:
                        cursor_value = row.get(field.name)
                        new_cursor[field.name] = None if cursor_value is None else str(cursor_value)
                # emit if we've hit the chunk size
                if len(records) >= self.chunk_size:
                    logging.info(f"{self.extractor_type} extractor fetched {len(records)} rows from {source_name}")
                    rows_emitted += len(records)
                    yield ExtractionBatch(records=records, cursor=new_cursor)
                    records = []
        # flush any remaining records
        yield ExtractionBatch(records=records, cursor=new_cursor)
        rows_emitted += len(records)
        if fetched_rows == 0:
            logging.info(f"{self.extractor_type} extractor returned no rows for {source_name}; preserving existing cursor")
        logging.info(f"{self.extractor_type} extractor completed {source_name} with {rows_emitted} rows")

    def _format_cursor_filter(
        self,
        key: str,
        value: str | float | int | bool | datetime,
        column_type: str,
        operator: str = ">=",
    ) -> str:
        if isinstance(value, str):
            normalized = column_type.lower()
            if normalized in {"int", "integer", "bigint"}:
                value = int(value)
            elif normalized in {"float", "double", "decimal", "numeric"}:
                value = float(value)
            elif normalized in {"bool", "boolean"}:
                value = value.lower() == "true"
            elif normalized in {"datetime", "timestamp", "date"}:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if isinstance(value, bool):
            return f"{self._quote_identifier(key)} {operator} {1 if value else 0}"
        if isinstance(value, (int, float)):
            return f"{self._quote_identifier(key)} {operator} {value}"
        if isinstance(value, (str, datetime)):
            return f"{self._quote_identifier(key)} {operator} '{value}'"
        raise Exception(f"Unknown value type for _format_cursor_filter: {type(value)}")
