import pytest

from tag_data_engineering.models import ExtractionMetadata
from tag_data_engineering.models import ExtractionMode
from tag_data_engineering.runners.landing_copyjob_normalize_runner import LandingCopyJobNormalizeRunner
from tag_data_engineering.runners.landing_runner import LandingResult
from tests.conftest import MockDataFrame
from tests.conftest import get_recorded_run
from tests.conftest import make_mock_connector


@pytest.fixture
def sample_copyjob_metadata() -> ExtractionMetadata:
    return ExtractionMetadata(
        entity="test_copyjob_entity",
        pipeline_group="test",
        extractor="copy_job",
        extraction_mode=ExtractionMode.FULL_REFRESH,
        max_file_size_mb=1,
        output_format="jsonl",
        extractor_config={
            "source_connection": "test_source",
            "source_query": "SELECT * FROM test_table",
        },
    )


class TestLandingCopyJobNormalizeRunner:
    def test_successful_normalization(self, sample_copyjob_metadata):
        connector = make_mock_connector()
        connector.path_exists.return_value = True
        connector.read_json.return_value = MockDataFrame(count=3, num_partitions=1)
        runner = LandingCopyJobNormalizeRunner(connector=connector, extractors=[])

        result = runner.run(sample_copyjob_metadata)

        assert result.records_extracted == 3
        assert result.files_written == 1
        copyjob_path = f"{connector.base_path}/Files/copyjob_raw/{sample_copyjob_metadata.entity}/"
        connector.read_json.assert_called_once_with(copyjob_path)
        df = connector.read_json.return_value
        df.write.mode.assert_called_with("overwrite")
        output_path = connector.get_files_path(sample_copyjob_metadata.entity, result.run_id)
        df.write.mode("overwrite").json.assert_called_once_with(output_path)
        connector.delete_dir.assert_called_once_with(copyjob_path)
        recorded = get_recorded_run(connector)
        assert recorded["status"] == "completed"
        assert recorded["total_record_count"] == 3
        assert recorded["file_count"] == 1

    def test_successful_normalization_multiple_partitions(self, sample_copyjob_metadata):
        connector = make_mock_connector()
        connector.path_exists.return_value = True
        connector.read_json.return_value = MockDataFrame(count=2500, num_partitions=5)
        runner = LandingCopyJobNormalizeRunner(connector=connector, extractors=[])

        result = runner.run(sample_copyjob_metadata)

        assert result.files_written == 5

    def test_handles_empty_copyjob_output(self, sample_copyjob_metadata):
        connector = make_mock_connector()
        connector.path_exists.return_value = True
        connector.read_json.return_value = MockDataFrame(count=0)
        runner = LandingCopyJobNormalizeRunner(connector=connector, extractors=[])

        result = runner.run(sample_copyjob_metadata)

        assert result.records_extracted == 0
        assert result.files_written == 0
        recorded = get_recorded_run(connector)
        assert recorded["status"] == "completed"

    def test_handles_missing_copyjob_output_path(self, sample_copyjob_metadata):
        connector = make_mock_connector()
        runner = LandingCopyJobNormalizeRunner(connector=connector, extractors=[])

        result = runner.run(sample_copyjob_metadata)

        assert result.records_extracted == 0
        assert result.files_written == 0
        connector.write_data_to_table.assert_not_called()
        connector.read_json.assert_not_called()

    def test_deletes_raw_files_after_normalization(self, sample_copyjob_metadata):
        connector = make_mock_connector()
        connector.path_exists.return_value = True
        connector.read_json.return_value = MockDataFrame(count=1, num_partitions=1)
        runner = LandingCopyJobNormalizeRunner(connector=connector, extractors=[])

        runner.run(sample_copyjob_metadata)

        copyjob_path = f"{connector.base_path}/Files/copyjob_raw/{sample_copyjob_metadata.entity}/"
        connector.delete_dir.assert_called_once_with(copyjob_path)

    def test_records_run_metadata_on_success(self, sample_copyjob_metadata):
        connector = make_mock_connector()
        connector.path_exists.return_value = True
        connector.read_json.return_value = MockDataFrame(count=10, num_partitions=1)
        runner = LandingCopyJobNormalizeRunner(connector=connector, extractors=[])

        runner.run(sample_copyjob_metadata)

        recorded = get_recorded_run(connector)
        assert recorded["status"] == "completed"
        assert recorded["total_record_count"] == 10
        assert recorded["error_message"] is None

    def test_records_run_metadata_on_failure(self, sample_copyjob_metadata):
        connector = make_mock_connector()
        connector.path_exists.return_value = True
        connector.read_json.side_effect = RuntimeError("Read failed")
        runner = LandingCopyJobNormalizeRunner(connector=connector, extractors=[])

        with pytest.raises(RuntimeError, match="Normalization failed"):
            runner.run(sample_copyjob_metadata)

        recorded = get_recorded_run(connector)
        assert recorded["status"] == "failed"
        assert "Read failed" in recorded["error_message"]

    def test_different_entities_use_different_paths(self):
        connector = make_mock_connector()
        metadata_a = ExtractionMetadata(
            entity="entity_a",
            pipeline_group="test",
            extractor="copy_job",
            extraction_mode=ExtractionMode.FULL_REFRESH,
            max_file_size_mb=1,
            output_format="jsonl",
            extractor_config={},
        )
        metadata_b = ExtractionMetadata(
            entity="entity_b",
            pipeline_group="test",
            extractor="copy_job",
            extraction_mode=ExtractionMode.FULL_REFRESH,
            max_file_size_mb=1,
            output_format="jsonl",
            extractor_config={},
        )
        runner = LandingCopyJobNormalizeRunner(connector=connector, extractors=[])

        runner.run(metadata_a)
        runner.run(metadata_b)

        calls = connector.path_exists.call_args_list
        paths = [call[0][0] for call in calls]
        assert f"{connector.base_path}/Files/copyjob_raw/entity_a/" in paths
        assert f"{connector.base_path}/Files/copyjob_raw/entity_b/" in paths

    def test_generates_unique_run_ids(self, sample_copyjob_metadata):
        connector = make_mock_connector()
        connector.path_exists.return_value = True
        connector.read_json.return_value = MockDataFrame(count=1, num_partitions=1)
        runner = LandingCopyJobNormalizeRunner(connector=connector, extractors=[])

        result1 = runner.run(sample_copyjob_metadata)
        result2 = runner.run(sample_copyjob_metadata)

        assert result1.run_id != result2.run_id

    def test_returns_landing_result(self, sample_copyjob_metadata):
        connector = make_mock_connector()
        connector.path_exists.return_value = True
        connector.read_json.return_value = MockDataFrame(count=5, num_partitions=1)
        runner = LandingCopyJobNormalizeRunner(connector=connector, extractors=[])

        result = runner.run(sample_copyjob_metadata)

        assert isinstance(result, LandingResult)
        assert result.entity == sample_copyjob_metadata.entity
        assert result.records_extracted == 5
        assert result.files_written == 1
        assert result.duration_seconds >= 0

    def test_sets_max_partition_bytes(self, sample_copyjob_metadata):
        connector = make_mock_connector()
        connector.path_exists.return_value = True
        connector.read_json.return_value = MockDataFrame(count=1, num_partitions=1)
        runner = LandingCopyJobNormalizeRunner(connector=connector, extractors=[])

        runner.run(sample_copyjob_metadata)

        connector.set_conf.assert_called_with("spark.sql.files.maxPartitionBytes", str(1 * 1024 * 1024))
