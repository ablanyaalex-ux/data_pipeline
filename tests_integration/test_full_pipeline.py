import contextlib
import difflib
import hashlib
from pathlib import Path
from typing import List
from typing import Tuple

import pandas as pd
from pyspark.sql import SparkSession

from tag_data_engineering.pipeline.models import PipelineDefinition
from tests_integration.pipeline_executor import PipelineExecutor


EXCLUDE_COLUMNS = ["_run_id"]
TABLE_LAYERS = ["bronze", "silver", "gold"]


def _row_hash(row: pd.Series) -> str:
    # Convert all values to strings and join, then hash
    row_str = "|".join(str(v) for v in row.values)
    return hashlib.md5(row_str.encode()).hexdigest()


def compare_csv_files(expected_path: Path, actual_path: Path) -> Tuple[bool, str]:
    if not expected_path.exists():
        return False, f"Expected file not found: {expected_path}"
    if not actual_path.exists():
        return False, f"Actual file not found: {actual_path}"
    expected_df = pd.read_csv(expected_path)
    actual_df = pd.read_csv(actual_path)
    # Sort both dataframes by row hash for deterministic comparison
    expected_df["_row_hash"] = expected_df.apply(_row_hash, axis=1)
    actual_df["_row_hash"] = actual_df.apply(_row_hash, axis=1)
    expected_df = expected_df.sort_values(by="_row_hash").drop(columns=["_row_hash"]).reset_index(drop=True)
    actual_df = actual_df.sort_values(by="_row_hash").drop(columns=["_row_hash"]).reset_index(drop=True)
    # Convert back to string lines for comparison
    expected_lines = expected_df.to_csv(index=False).splitlines(keepends=True)
    actual_lines = actual_df.to_csv(index=False).splitlines(keepends=True)
    if expected_lines == actual_lines:
        return True, ""
    diff = difflib.unified_diff(expected_lines, actual_lines, fromfile=str(expected_path), tofile=str(actual_path), lineterm="")
    diff_output = "\n".join(diff)
    return False, diff_output


def list_tables(spark: SparkSession, layer: str) -> List[str]:
    tables = []
    try:
        table_rows = spark.sql(f"SHOW TABLES IN {layer}").collect()
    except Exception:
        # Layer might not exist yet
        return tables
    for row in table_rows:
        table_name = row["tableName"]
        with contextlib.suppress(Exception):
            # Verify table actually exists by trying to access it
            spark.table(f"{layer}.{table_name}")
            tables.append(table_name)
    return tables


class TestFullPipeline:
    def test_full_pipeline_execution(
        self,
        subtests,
        pipeline: PipelineDefinition,
        spark_session: SparkSession,
        pipeline_executor: PipelineExecutor,
    ):
        # First run - creates tables and loads data
        results = pipeline_executor.execute(pipeline)
        failed_results = [r for r in results if not r.success]
        assert len(failed_results) == 0, f"First run failed: {[(r.activity_name, r.error_message) for r in failed_results]}"
        # Second run - exercises MERGE paths
        results = pipeline_executor.execute(pipeline)
        failed_results = [r for r in results if not r.success]
        assert len(failed_results) == 0, f"Second run (MERGE) failed: {[(r.activity_name, r.error_message) for r in failed_results]}"
        # Validate results against expected outputs
        expected_dir = Path(__file__).parent / "results_expected"
        actual_dir = Path(__file__).parent / "results_actual"
        for layer in TABLE_LAYERS:
            layer_path = actual_dir / layer
            layer_path.mkdir(parents=True, exist_ok=True)
            tables = list_tables(spark_session, layer)
            for table_name in tables:
                actual_path = actual_dir / layer / f"{table_name}.csv"
                df = spark_session.table(f"{layer}.{table_name}")
                pdf = df.toPandas().drop(columns=EXCLUDE_COLUMNS, errors="ignore")
                pdf.to_csv(actual_path, index=False)
                with subtests.test(msg=f"{layer}.{table_name}", layer=layer, table=table_name):
                    expected_path = expected_dir / layer / f"{table_name}.csv"
                    assert expected_path.exists(), f"Expected table does not exist: {actual_path}"
                    matches, diff = compare_csv_files(expected_path, actual_path)
                    assert matches, f"Output does not match expected.\n\nPlease inspect:\nactual: {actual_path}\nexpected: {expected_path}\n\nDiff:\n{diff}"
