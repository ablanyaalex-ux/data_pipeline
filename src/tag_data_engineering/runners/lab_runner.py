import logging
from pathlib import Path

import sqlglot

from tag_data_engineering.connectors.lakehouse_connector import LakehouseConnector


class LabRunner:
    def __init__(self, connector: LakehouseConnector, transformations_path: str = "Files/transformations"):
        self.connector = connector
        self.transformations_path = transformations_path.rstrip("/")

    def run(self, layer: str = "lab", entity: str = "") -> list[str]:
        if not entity:
            raise ValueError("entity must be provided for lab runs. Use 'all' to execute all SQL files.")
        self.connector.spark.sql("CREATE SCHEMA IF NOT EXISTS lab")
        layer_path = f"{self.transformations_path}/{layer}".rstrip("/")
        self.connector.mkdirs(layer_path)
        entries = self.connector.list_dir(layer_path)
        sql_files = sorted(
            [(name, entry_path) for name, entry_path in entries if name.endswith(".sql") and not name.startswith("_")],
            key=lambda item: item[0],
        )
        if not sql_files:
            logging.info(f"No SQL files found in {layer_path}. Skipping lab run.")
            return []
        if entity != "all":
            filtered_files: list[tuple[str, str]] = []
            for sql_file_name, sql_file_path in sql_files:
                stem = Path(sql_file_name).stem
                normalized_stem = stem
                prefix, sep, remainder = stem.partition("_")
                if sep and prefix.isdigit() and remainder:
                    normalized_stem = remainder
                entity_without_suffix = entity.removesuffix(".sql")
                if entity in {sql_file_name, stem, normalized_stem} or entity_without_suffix in {stem, normalized_stem}:
                    filtered_files.append((sql_file_name, sql_file_path))
            if not filtered_files:
                available = [name for name, _ in sql_files]
                raise ValueError(f"Entity '{entity}' not found in {layer_path}. Available SQL files: {available}")
            sql_files = filtered_files
        applied: list[str] = []
        for sql_file_name, sql_file_path in sql_files:
            rows = self.connector.spark.read.text(sql_file_path).collect()
            sql_text = "\n".join(row.value for row in rows)
            if not sql_text.strip():
                raise ValueError(f"SQL file '{sql_file_name}' is empty")

            try:
                statements = sqlglot.parse(sql_text, read="spark")
            except Exception as exc:
                raise ValueError(f"Failed to parse SQL file '{sql_file_name}': {exc}") from exc

            if not statements:
                raise ValueError(f"SQL file '{sql_file_name}' contains no executable statements")

            for statement in statements:
                if statement:
                    self.connector.spark.sql(statement.sql(dialect="spark"))

            applied.append(sql_file_name)
        self.connector.refresh_sql_endpoint_metadata()
        return applied
