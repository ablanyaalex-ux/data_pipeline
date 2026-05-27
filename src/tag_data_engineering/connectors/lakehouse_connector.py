import contextlib
import threading
import uuid
from abc import ABC
from abc import abstractmethod
from contextlib import contextmanager
from typing import Any
from typing import Generator

from pyspark.sql import DataFrame
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType


class LakehouseConnector(ABC):
    # Class-level dictionary to store locks per SparkSession
    _session_locks: dict[int, threading.Lock] = {}
    _locks_lock = threading.Lock()  # Lock to protect the locks dictionary itself

    def __init__(
        self,
        spark: SparkSession,
        base_path: str = "",
    ):
        self.spark = spark
        self.base_path = base_path
        self.spark.conf.set("spark.databricks.delta.schema.autoMerge.enabled", "true")
        # Get or create a lock for this SparkSession
        session_id = id(spark)
        with LakehouseConnector._locks_lock:
            if session_id not in LakehouseConnector._session_locks:
                LakehouseConnector._session_locks[session_id] = threading.Lock()
            self._temp_view_lock = LakehouseConnector._session_locks[session_id]

    def get_table_path(self, schema: str, table: str) -> str:
        return f"{schema}.{table}"

    @abstractmethod
    def get_files_path(self, entity: str, run_id: str | None = None) -> str:
        pass

    @abstractmethod
    def mkdirs(self, path: str) -> None:
        pass

    @abstractmethod
    def write_file(self, path: str, content: str) -> None:
        pass

    @abstractmethod
    def delete_dir(self, path: str) -> None:
        pass

    @abstractmethod
    def path_exists(self, path: str) -> bool:
        pass

    @abstractmethod
    def list_dir(self, path: str) -> list[tuple[str, str]]:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

    def run_sql(self, sql: str) -> DataFrame:
        return self.spark.sql(sql)

    def create_schema(self, name: str) -> None:
        self.spark.sql(f"CREATE SCHEMA IF NOT EXISTS {name}")

    def table_exists(self, schema: str, table: str) -> bool:
        return self.spark.catalog.tableExists(f"{schema}.{table}")

    def read_json(self, path: str) -> DataFrame:
        return self.spark.read.json(path)

    @contextmanager
    def create_temp_view(self, df: DataFrame, prefix: str = "temp") -> Generator[str, None, None]:
        """Thread-safe context manager for temporary views.
        Creates a uniquely-named temporary view that is automatically cleaned up.
        Uses a lock to ensure thread-safety when multiple transformations run in parallel.
        """
        view_name = f"{prefix}_{uuid.uuid4().hex[:8]}"
        with self._temp_view_lock:
            try:
                df.createOrReplaceTempView(view_name)
                yield view_name
            finally:
                with contextlib.suppress(Exception):
                    self.spark.catalog.dropTempView(view_name)

    def write_data_to_table(
        self,
        data: list[tuple[Any, ...]],
        schema: StructType,
        table: str,
        mode: str = "append",
        format: str = "delta",
        partition_by: list[str] | None = None,
        options: dict[str, str] | None = None,
    ) -> None:
        df = self.spark.createDataFrame(data, schema=schema)
        writer = df.write.format(format).mode(mode)
        if partition_by:
            writer = writer.partitionBy(partition_by)
        if options:
            for key, value in options.items():
                writer = writer.option(key, value)
        writer.saveAsTable(table)

    def set_conf(self, key: str, value: str) -> None:
        self.spark.conf.set(key, value)

    def refresh_sql_endpoint_metadata(self) -> None:  # noqa: B027
        pass
