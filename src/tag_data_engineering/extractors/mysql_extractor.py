import json
import logging

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from tag_data_engineering.extractors.sqlalchemy_extractor import SqlalchemyExtractor
from tag_data_engineering.extractors.sqlalchemy_extractor import SqlalchemyExtractorConfig


class MySqlExtractorConfig(SqlalchemyExtractorConfig):
    source_database: str


class MySqlExtractor(SqlalchemyExtractor[MySqlExtractorConfig]):
    @property
    def extractor_type(self) -> str:
        return "mysql"

    def _quote_identifier(self, identifier: str) -> str:
        return f"`{identifier}`"

    def _quote_table(self, config: MySqlExtractorConfig) -> str:
        table_name = self._quote_identifier(config.source_table)
        if config.source_database:
            return f"{self._quote_identifier(config.source_database)}.{table_name}"
        return table_name

    def _source_name(self, config: MySqlExtractorConfig) -> str:
        return f"{config.source_database}.{config.source_table}"

    @property
    def _config_class(self) -> type[MySqlExtractorConfig]:
        return MySqlExtractorConfig

    def _get_or_build_engine(self, config: MySqlExtractorConfig) -> Engine:
        if self._engine is None:
            credentials = json.loads(self.secret_provider.get_secret(config.source_secret_key))
            self._engine = create_engine(f"mysql+pymysql://{credentials['username']}:{credentials['password']}@{credentials['host']}:{credentials['port']}/{config.source_database}?charset=utf8mb4", pool_pre_ping=True)
            logging.info(f"MySQL extractor built engine for {config.source_database}.{config.source_table}")
        return self._engine
