import json
import logging
from datetime import date
from datetime import datetime
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from tag_data_engineering.extractors.sqlalchemy_extractor import SqlalchemyExtractor
from tag_data_engineering.extractors.sqlalchemy_extractor import SqlalchemyExtractorConfig


class SqlServerExtractorConfig(SqlalchemyExtractorConfig):
    source_schema: str | None = None


class SqlServerExtractor(SqlalchemyExtractor[SqlServerExtractorConfig]):
    @property
    def extractor_type(self) -> str:
        return "sql_server"

    @property
    def _config_class(self) -> type[SqlServerExtractorConfig]:
        return SqlServerExtractorConfig

    def _quote_identifier(self, identifier: str) -> str:
        return f"[{identifier}]"

    def _quote_table(self, config: SqlServerExtractorConfig) -> str:
        table_name = self._quote_identifier(config.source_table)
        if config.source_schema:
            return f"{self._quote_identifier(config.source_schema)}.{table_name}"
        return table_name

    def _source_name(self, config: SqlServerExtractorConfig) -> str:
        if config.source_schema:
            return f"{config.source_schema}.{config.source_table}"
        return config.source_table

    def _get_or_build_engine(self, config: SqlServerExtractorConfig) -> Engine:
        if self._engine is None:
            credentials = json.loads(self.secret_provider.get_secret(config.source_secret_key))
            driver = credentials.get("driver", "ODBC Driver 18 for SQL Server")
            database = credentials["database"]
            driver_param = quote_plus(driver)
            self._engine = create_engine(
                (f"mssql+pyodbc://{credentials['username']}:{credentials['password']}@{credentials['host']}:{credentials['port']}/{database}?driver={driver_param}&TrustServerCertificate=yes&Encrypt=no"),
                pool_pre_ping=True,
            )
            logging.info(f"SQL Server extractor built engine for {self._source_name(config)}")
        return self._engine

    def _format_cursor_filter(
        self,
        key: str,
        value: str | float | int | bool | datetime,
        column_type: str,
        operator: str = ">=",
    ) -> str:
        normalized = column_type.lower()
        if normalized in {"datetime", "datetime2", "timestamp", "date"}:
            if isinstance(value, str):
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if isinstance(value, date) and not isinstance(value, datetime):
                value = datetime.combine(value, datetime.min.time())
            if isinstance(value, datetime):
                iso_value = value.isoformat(timespec="microseconds")
                return f"{self._quote_identifier(key)} {operator} CONVERT(datetime2(6), '{iso_value}', 126)"
        return super()._format_cursor_filter(
            key=key,
            value=value,
            column_type=column_type,
            operator=operator,
        )
