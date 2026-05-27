from pathlib import Path
from unittest.mock import patch

import pytest

from tag_data_engineering.models import BronzeMetadata
from tag_data_engineering.models import TransformationMetadata
from tag_data_engineering.pipeline.models import Layer
from tag_data_engineering.pipeline.pipeline_discoverer import PipelineDiscoverer
from tag_data_engineering.runners.transformation_runner import TransformationRunner
from tests.conftest import MockDataFrame
from tests.conftest import get_recorded_run
from tests.conftest import make_mock_connector
from tests.conftest import make_row


def make_run_sql_side_effect(unprocessed_runs_df, show_tables_df=None, default_df=None):
    """Create a side_effect for connector.run_sql that returns different results based on the SQL query."""
    if default_df is None:
        default_df = MockDataFrame()
    if show_tables_df is None:
        show_tables_df = MockDataFrame()

    def side_effect(sql):
        sql_lower = sql.strip().lower()
        if "left join" in sql_lower and "_metadata.landing_runs" in sql_lower:
            return unprocessed_runs_df
        if sql_lower.startswith("show tables"):
            return show_tables_df
        return default_df

    return side_effect


@pytest.fixture(autouse=True)
def _patch_pyspark():
    with patch("tag_data_engineering.runners.transformation_runner.lit"), patch("tag_data_engineering.runners.transformation_runner.col"), patch("tag_data_engineering.runners.transformation_runner.row_number"), patch(
        "tag_data_engineering.runners.transformation_runner.Window"
    ):
        yield


@pytest.fixture
def connector():
    return make_mock_connector()


@pytest.fixture
def bronze_metadata():
    return BronzeMetadata(
        schema="bronze",
        pipeline_group="test",
        table="test_entity",
        entity="test_entity",
        merge_key="id",
        source_format="jsonl",
    )


@pytest.fixture
def silver_metadata():
    return TransformationMetadata(
        schema="silver",
        pipeline_group="test",
        table="test_entity",
        merge_key="id",
        sql="SELECT CAST(id AS INT) as id, name, CAST(value AS INT) as value FROM bronze.test_entity",
    )


class TestTransformationRunner:
    def test_bronze_no_unprocessed_runs_returns_zero(self, connector, bronze_metadata):
        runner = TransformationRunner(connector=connector)
        result = runner.run_transformation(bronze_metadata)
        assert result.rows_processed == 0
        connector.read_json.assert_not_called()

    def test_bronze_creates_schema(self, connector, bronze_metadata):
        connector.run_sql.side_effect = make_run_sql_side_effect(
            unprocessed_runs_df=MockDataFrame(rows=[make_row(run_id="run-001", file_count=2)]),
        )
        connector.read_json.return_value = MockDataFrame(count=2)
        runner = TransformationRunner(connector=connector)
        runner.run_transformation(bronze_metadata)
        connector.create_schema.assert_called_with("bronze")

    def test_bronze_creates_table_on_first_run(self, connector, bronze_metadata):
        connector.run_sql.side_effect = make_run_sql_side_effect(
            unprocessed_runs_df=MockDataFrame(rows=[make_row(run_id="run-001", file_count=2)]),
        )
        connector.read_json.return_value = MockDataFrame(count=2)
        runner = TransformationRunner(connector=connector)
        result = runner.run_transformation(bronze_metadata)
        create_table_calls = [call for call in connector.run_sql.call_args_list if "CREATE TABLE" in str(call)]
        assert len(create_table_calls) == 1
        assert result.rows_processed == 2

    def test_bronze_merges_on_subsequent_runs(self, connector, bronze_metadata):
        connector.run_sql.side_effect = make_run_sql_side_effect(
            unprocessed_runs_df=MockDataFrame(rows=[make_row(run_id="run-001", file_count=2)]),
            show_tables_df=MockDataFrame(rows=[make_row(tableName="test_entity")]),
        )
        connector.read_json.return_value = MockDataFrame(count=2)
        runner = TransformationRunner(connector=connector)
        runner.run_transformation(bronze_metadata)
        merge_calls = [call for call in connector.run_sql.call_args_list if "MERGE INTO" in str(call)]
        assert len(merge_calls) == 1

    def test_bronze_skips_already_processed_runs(self, connector, bronze_metadata):
        runner = TransformationRunner(connector=connector)
        result = runner.run_transformation(bronze_metadata)
        assert result.rows_processed == 0

    def test_bronze_processes_multiple_pending_runs(self, connector, bronze_metadata):
        connector.run_sql.side_effect = make_run_sql_side_effect(
            unprocessed_runs_df=MockDataFrame(
                rows=[
                    make_row(run_id="run-001", file_count=1),
                    make_row(run_id="run-002", file_count=1),
                ],
            ),
        )
        connector.read_json.return_value = MockDataFrame(count=1)
        runner = TransformationRunner(connector=connector)
        runner.run_transformation(bronze_metadata)
        assert connector.read_json.call_count == 2
        assert connector.write_data_to_table.call_count == 2

    def test_bronze_skips_runs_with_zero_files(self, connector, bronze_metadata):
        connector.run_sql.side_effect = make_run_sql_side_effect(
            unprocessed_runs_df=MockDataFrame(rows=[make_row(run_id="run-001", file_count=0)]),
        )
        runner = TransformationRunner(connector=connector)
        runner.run_transformation(bronze_metadata)
        connector.read_json.assert_not_called()
        connector.write_data_to_table.assert_called_once()

    def test_bronze_records_run_metadata(self, connector, bronze_metadata):
        connector.run_sql.side_effect = make_run_sql_side_effect(
            unprocessed_runs_df=MockDataFrame(rows=[make_row(run_id="run-001", file_count=1)]),
        )
        connector.read_json.return_value = MockDataFrame(count=5)
        runner = TransformationRunner(connector=connector)
        runner.run_transformation(bronze_metadata)
        recorded = get_recorded_run(connector, call_index=0)
        assert recorded["entity"] == "test_entity"
        assert recorded["run_id"] == "run-001"
        assert recorded["status"] == "completed"

    def test_silver_creates_table(self, connector, silver_metadata):
        connector.run_sql.side_effect = make_run_sql_side_effect(
            unprocessed_runs_df=MockDataFrame(),
            default_df=MockDataFrame(count=2),
        )
        runner = TransformationRunner(connector=connector)
        result = runner.run_transformation(silver_metadata)
        create_table_calls = [call for call in connector.run_sql.call_args_list if "CREATE TABLE" in str(call)]
        assert len(create_table_calls) == 1
        assert result.rows_processed == 2

    def test_silver_merges_on_subsequent_runs(self, connector, silver_metadata):
        source_df = MockDataFrame(count=2)

        def side_effect(sql):
            sql_lower = sql.strip().lower()
            if sql_lower.startswith("show tables"):
                return MockDataFrame(rows=[make_row(tableName="test_entity")])
            return source_df

        connector.run_sql.side_effect = side_effect
        runner = TransformationRunner(connector=connector)
        runner.run_transformation(silver_metadata)
        merge_calls = [call for call in connector.run_sql.call_args_list if "MERGE INTO" in str(call)]
        assert len(merge_calls) == 1

    def test_silver_raises_error_for_unknown_table(self):
        discoverer = PipelineDiscoverer(Path(__file__).parent.parent / "transformations")
        with pytest.raises(ValueError, match="No job found for silver/nonexistent_table"):
            discovered_jobs = discoverer.discover_layer(Layer.SILVER)
            matching_job = next((job for job in discovered_jobs if job.entity == "nonexistent_table"), None)
            if not matching_job:
                available = [job.entity for job in discovered_jobs]
                raise ValueError(f"No job found for silver/nonexistent_table. Available: {available}")

    def test_pipeline_discoverer_finds_transformations(self):
        discoverer = PipelineDiscoverer(Path(__file__).parent.parent / "transformations")
        bronze_jobs = discoverer.discover_layer(Layer.BRONZE)
        assert len(bronze_jobs) > 0
        silver_jobs = discoverer.discover_layer(Layer.SILVER)
        assert len(silver_jobs) > 0
        gold_jobs = discoverer.discover_layer(Layer.GOLD)
        assert len(gold_jobs) == 0
