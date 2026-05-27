from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock


class MockDataFrame:
    """Lightweight mock DataFrame that supports chaining without PySpark."""

    def __init__(self, rows=None, count=None, num_partitions=1):
        self._rows = rows or []
        self._count = count if count is not None else len(self._rows)
        self._num_partitions = num_partitions
        self.columns = []
        self.write = MagicMock()
        self.write.mode.return_value = self.write
        self.write.format.return_value = self.write
        self.rdd = MagicMock()
        self.rdd.getNumPartitions.return_value = self._num_partitions

    def count(self):
        return self._count

    def collect(self):
        return self._rows

    def withColumn(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def drop(self, *args, **kwargs):
        return self

    def select(self, *args, **kwargs):
        return self


def make_mock_connector(base_path="file:///tmp/test-lakehouse"):
    """Create a mock LakehouseConnector with sensible defaults."""
    connector = MagicMock()
    connector.base_path = base_path
    connector.spark = MagicMock()
    connector.get_files_path.side_effect = lambda entity, run_id=None: (f"{base_path}/Files/{entity}/{run_id}/" if run_id else f"{base_path}/Files/{entity}/*/")
    connector.get_table_path.side_effect = lambda schema, table: f"{schema}.{table}"
    connector.table_exists.return_value = False
    connector.path_exists.return_value = False

    @contextmanager
    def mock_create_temp_view(df, prefix="temp"):
        yield "mock_temp_view"

    connector.create_temp_view = mock_create_temp_view

    empty_df = MockDataFrame()
    connector.run_sql.return_value = empty_df
    connector.read_json.return_value = empty_df

    return connector


def make_row(**kwargs):
    """Create a mock Row object from keyword arguments."""
    return SimpleNamespace(**kwargs)


def get_recorded_run(connector, call_index=0):
    """Extract the run metadata from a write_data_to_table call.

    Returns a dict with keys: entity, run_id, started_at, completed_at,
    status, file_count, total_record_count, error_message, cursor.
    """
    call_args = connector.write_data_to_table.call_args_list[call_index]
    row = call_args[1]["data"][0] if "data" in call_args[1] else call_args[0][0][0]
    keys = ["entity", "run_id", "started_at", "completed_at", "status"]
    # Detect if this is a landing run (9 fields) or bronze run (7 fields)
    if len(row) == 9:
        keys += ["file_count", "total_record_count", "error_message", "cursor"]
    else:
        keys += ["rows_processed", "error_message"]
    return dict(zip(keys, row))
