import json
import logging
import math
import time
import uuid
from datetime import date
from datetime import datetime
from typing import Any
from typing import Iterator

import psycopg2
from psycopg2.extras import register_hstore
from pydantic import BaseModel
from pydantic import model_validator

from tag_data_engineering.extractors.base_extractor import BaseExtractor
from tag_data_engineering.extractors.models import ExtractionBatch
from tag_data_engineering.models import ExtractionMetadata
from tag_data_engineering.models import ExtractionMode


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


class PostgresExtractorConfig(BaseModel):
    source_secret_key: str
    source_table: str
    incremental: IncrementalConfig | None = None
    source_schema: str | None = None


class PostgresExtractor(BaseExtractor):
    def __init__(self, secret_provider, chunk_size: int = 10_000):
        super().__init__(secret_provider=secret_provider)
        self.chunk_size = chunk_size

    @property
    def extractor_type(self) -> str:
        return "postgres"

    @property
    def _config_class(self) -> type[PostgresExtractorConfig]:
        return PostgresExtractorConfig

    def _quote_identifier(self, identifier: str) -> str:
        return f'"{identifier}"'

    def _quote_table(self, config: PostgresExtractorConfig) -> str:
        table_name = self._quote_identifier(config.source_table)
        if config.source_schema:
            return f"{self._quote_identifier(config.source_schema)}.{table_name}"
        return table_name

    def _source_name(self, config: PostgresExtractorConfig) -> str:
        if config.source_schema:
            return f"{config.source_schema}.{config.source_table}"
        return config.source_table

    def _build_query(
        self,
        metadata: ExtractionMetadata,
        config: PostgresExtractorConfig,
        cursor: dict[str, str | None] | None = None,
    ) -> str:
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
        return query

    def _normalize_record(self, row: dict[str, Any]) -> dict[str, Any]:
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
        return normalized_record

    def _build_updated_cursor(
        self,
        row: dict[str, Any],
        cursor_fields: list[IncrementalColumnConfig],
    ) -> dict[str, str | None]:
        new_cursor: dict[str, str | None] = {}
        for field in cursor_fields:
            cursor_value = row.get(field.name)
            new_cursor[field.name] = None if cursor_value is None else str(cursor_value)
        return new_cursor

    def _format_log_cursor(self, cursor: dict[str, str | None] | None) -> str:
        if not cursor:
            return "None"
        return ", ".join(f"{key}={value}" for key, value in cursor.items())

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

    def extract(
        self,
        metadata: ExtractionMetadata,
        cursor: dict[str, str | None] | None = None,
    ) -> Iterator[ExtractionBatch]:
        config = self._config_class.model_validate(metadata.extractor_config)
        source_name = self._source_name(config)
        query = self._build_query(metadata, config, cursor)
        credentials = json.loads(self.secret_provider.get_secret(config.source_secret_key))
        cursor_fields = config.incremental.columns if config.incremental is not None else []

        total_start = time.perf_counter()
        fetched_rows = 0
        rows_emitted = 0
        chunk_count = 0
        new_cursor = cursor

        logging.info(
            "%s extractor starting %s extraction for %s (chunk_size=%s, cursor_fields=%s, cursor=%s)",
            self.extractor_type,
            metadata.extraction_mode.value,
            source_name,
            self.chunk_size,
            [field.name for field in cursor_fields],
            self._format_log_cursor(cursor),
        )

        with psycopg2.connect(
            host=credentials["host"],
            port=credentials["port"],
            user=credentials["username"],
            password=credentials["password"],
            dbname=credentials["database"],
            keepalives=1,
            keepalives_idle=300,
            keepalives_interval=10,
            keepalives_count=5,
        ) as connection:
            register_hstore(connection, globally=False, unicode=True)
            cursor_name = f"{config.source_table}_{uuid.uuid4().hex[:8]}"
            with connection.cursor(name=cursor_name) as db_cursor:
                db_cursor.itersize = self.chunk_size
                logging.info("%s extractor opened server-side cursor %s with itersize=%s", self.extractor_type, cursor_name, db_cursor.itersize)

                query_start = time.perf_counter()
                db_cursor.execute(query)
                logging.info("%s extractor executed query for %s in %.3fs: %s", self.extractor_type, source_name, time.perf_counter() - query_start, query)

                first_row = db_cursor.fetchone()
                if first_row is None:
                    logging.info("%s extractor returned no rows for %s; preserving cursor=%s", self.extractor_type, source_name, self._format_log_cursor(cursor))
                    logging.info(
                        "%s extractor completed %s with 0 rows across 0 chunk(s); total_time=%.2fs rows/sec=0.00 final cursor=%s", self.extractor_type, source_name, time.perf_counter() - total_start, self._format_log_cursor(new_cursor)
                    )
                    yield ExtractionBatch(records=[], cursor=new_cursor)
                    return

                if db_cursor.description is None:
                    raise RuntimeError("cursor.description is None after executing SELECT")

                columns = [desc[0] for desc in db_cursor.description]
                records: list[dict[str, Any]] = []
                chunk_start = time.perf_counter()

                for row in self._iter_rows(first_row, db_cursor):
                    raw_row = dict(zip(columns, row))
                    records.append(self._normalize_record(raw_row))
                    fetched_rows += 1
                    if config.incremental is not None:
                        new_cursor = self._build_updated_cursor(raw_row, cursor_fields)

                    if len(records) >= self.chunk_size:
                        chunk_count += 1
                        elapsed = time.perf_counter() - chunk_start
                        rows_per_second = fetched_rows / elapsed if elapsed > 0 else 0.0
                        logging.info(
                            "%s extractor emitting chunk %s from %s: %s rows in chunk, %s rows fetched total, cursor=%s",
                            self.extractor_type,
                            chunk_count,
                            source_name,
                            len(records),
                            fetched_rows,
                            self._format_log_cursor(new_cursor),
                        )
                        logging.info(
                            "%s extractor throughput for %s: elapsed=%.2fs rows=%s rows/sec=%.2f",
                            self.extractor_type,
                            source_name,
                            elapsed,
                            fetched_rows,
                            rows_per_second,
                        )
                        rows_emitted += len(records)
                        yield ExtractionBatch(records=records, cursor=new_cursor)
                        records = []

                if records:
                    chunk_count += 1
                    elapsed = time.perf_counter() - chunk_start
                    rows_per_second = fetched_rows / elapsed if elapsed > 0 else 0.0
                    logging.info(
                        "%s extractor emitting final chunk %s from %s: %s rows in chunk, %s rows fetched total, cursor=%s",
                        self.extractor_type,
                        chunk_count,
                        source_name,
                        len(records),
                        fetched_rows,
                        self._format_log_cursor(new_cursor),
                    )
                    logging.info(
                        "%s extractor throughput for %s: elapsed=%.2fs rows=%s rows/sec=%.2f",
                        self.extractor_type,
                        source_name,
                        elapsed,
                        fetched_rows,
                        rows_per_second,
                    )
                    rows_emitted += len(records)
                    yield ExtractionBatch(records=records, cursor=new_cursor)

        total_time = time.perf_counter() - total_start
        total_rows_per_second = fetched_rows / total_time if total_time > 0 else 0.0
        logging.info(
            "%s extractor completed %s with %s rows across %s chunk(s); total_time=%.2fs rows/sec=%.2f final cursor=%s",
            self.extractor_type,
            source_name,
            rows_emitted,
            chunk_count,
            total_time,
            total_rows_per_second,
            self._format_log_cursor(new_cursor),
        )

    def _iter_rows(self, first_row: tuple[Any, ...], db_cursor: Any) -> Iterator[tuple[Any, ...]]:
        yield first_row
        yield from db_cursor
