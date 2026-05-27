from datetime import datetime
from typing import Iterator

import pytest

from tag_data_engineering.extractors.base_extractor import BaseExtractor
from tag_data_engineering.extractors.models import ExtractionBatch
from tag_data_engineering.models import ExtractionMetadata
from tag_data_engineering.models import ExtractionMode
from tag_data_engineering.runners.landing_runner import LandingRunner
from tag_data_engineering.secrets.mock_secret_provider import MockSecretProvider
from tests.conftest import get_recorded_run
from tests.conftest import make_mock_connector


@pytest.fixture
def secret_provider() -> MockSecretProvider:
    return MockSecretProvider({})


@pytest.fixture
def sample_metadata() -> ExtractionMetadata:
    return ExtractionMetadata(
        entity="test_entity",
        pipeline_group="test",
        extractor="rest_api",
        extraction_mode=ExtractionMode.FULL_REFRESH,
        url="https://api.example.com/data",
        max_file_size_mb=1,
        output_format="jsonl",
    )


class MockExtractor(BaseExtractor):
    def __init__(self, batches: list[ExtractionBatch], secret_provider: MockSecretProvider):
        super().__init__(secret_provider=secret_provider)
        self._batches = batches

    @property
    def extractor_type(self) -> str:
        return "rest_api"

    def extract(
        self,
        metadata: ExtractionMetadata,
        cursor: dict[str, str | None] | None = None,
    ) -> Iterator[ExtractionBatch]:
        yield from self._batches


class FailingMockExtractor(BaseExtractor):
    def __init__(self, fail_after_batches: int, secret_provider: MockSecretProvider):
        super().__init__(secret_provider=secret_provider)
        self._fail_after = fail_after_batches
        self._count = 0

    @property
    def extractor_type(self) -> str:
        return "rest_api"

    def extract(
        self,
        metadata: ExtractionMetadata,
        cursor: dict[str, str | None] | None = None,
    ) -> Iterator[ExtractionBatch]:
        while self._count < self._fail_after:
            yield ExtractionBatch(records=[{"id": self._count}])
            self._count += 1
        raise RuntimeError("Simulated extraction failure")


class TestLandingRunner:
    def test_successful_single_file_extraction(
        self,
        sample_metadata: ExtractionMetadata,
        secret_provider: MockSecretProvider,
    ):
        connector = make_mock_connector()
        batch = ExtractionBatch(
            records=[
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
                {"id": 3, "name": "Charlie"},
            ]
        )
        mock_extractor = MockExtractor([batch], secret_provider)
        runner = LandingRunner(connector=connector, extractors=[mock_extractor])

        result = runner.run(sample_metadata)

        assert result.entity == "test_entity"
        assert result.records_extracted == 3
        assert result.files_written == 1

        connector.write_file.assert_called_once()
        written_content = connector.write_file.call_args[0][1]
        assert '{"id": 1, "name": "Alice"}' in written_content
        assert '{"id": 2, "name": "Bob"}' in written_content
        assert '{"id": 3, "name": "Charlie"}' in written_content

        run = get_recorded_run(connector)
        assert run["status"] == "completed"
        assert run["file_count"] == 1
        assert run["total_record_count"] == 3
        assert run["error_message"] is None

    def test_multiple_files_when_exceeding_size_limit(
        self,
        sample_metadata: ExtractionMetadata,
        secret_provider: MockSecretProvider,
    ):
        connector = make_mock_connector()
        large_string = "x" * 500_000
        batch1 = ExtractionBatch(records=[{"data": large_string}, {"data": large_string}])
        batch2 = ExtractionBatch(records=[{"data": large_string}])
        mock_extractor = MockExtractor([batch1, batch2], secret_provider)
        runner = LandingRunner(connector=connector, extractors=[mock_extractor])

        result = runner.run(sample_metadata)

        assert result.records_extracted == 3
        assert result.files_written >= 2
        assert connector.write_file.call_count >= 2

        run = get_recorded_run(connector)
        assert run["file_count"] >= 2

    def test_handles_extractor_failure(
        self,
        sample_metadata: ExtractionMetadata,
        secret_provider: MockSecretProvider,
    ):
        connector = make_mock_connector()
        failing_extractor = FailingMockExtractor(2, secret_provider)
        runner = LandingRunner(connector=connector, extractors=[failing_extractor])

        with pytest.raises(RuntimeError, match="Extraction failed"):
            runner.run(sample_metadata)

        run = get_recorded_run(connector)
        assert run["status"] == "failed"
        assert "Simulated extraction failure" in run["error_message"]
        assert run["total_record_count"] == 0
        assert run["file_count"] == 0

    def test_records_run_metadata_with_correct_timestamps(
        self,
        sample_metadata: ExtractionMetadata,
        secret_provider: MockSecretProvider,
    ):
        connector = make_mock_connector()
        batch = ExtractionBatch(records=[{"id": 1}])
        mock_extractor = MockExtractor([batch], secret_provider)
        runner = LandingRunner(connector=connector, extractors=[mock_extractor])

        before_run = datetime.now()
        runner.run(sample_metadata)
        after_run = datetime.now()

        run = get_recorded_run(connector)
        started_at = run["started_at"]
        completed_at = run["completed_at"]
        assert before_run <= started_at <= after_run
        assert before_run <= completed_at <= after_run
        assert started_at <= completed_at

    def test_captures_field_metadata_from_first_batch(
        self,
        sample_metadata: ExtractionMetadata,
        secret_provider: MockSecretProvider,
    ):
        connector = make_mock_connector()
        batch1 = ExtractionBatch(records=[{"col1": "a"}, {"col1": "b"}])
        batch2 = ExtractionBatch(records=[{"col1": "c"}, {"col1": "d"}])
        mock_extractor = MockExtractor([batch1, batch2], secret_provider)
        runner = LandingRunner(connector=connector, extractors=[mock_extractor])

        result = runner.run(sample_metadata)

        assert result.records_extracted == 4

        all_written_content = "".join(call[0][1] for call in connector.write_file.call_args_list)
        lines = all_written_content.strip().split("\n")
        assert len(lines) == 4
        for line in lines:
            assert "col1" in line

    def test_unsupported_extractor_type_raises_error(self):
        connector = make_mock_connector()
        runner = LandingRunner(connector=connector, extractors=[])
        unsupported_metadata = ExtractionMetadata(
            entity="test",
            pipeline_group="test",
            extractor="copy_job",
            extraction_mode=ExtractionMode.FULL_REFRESH,
            extractor_config={},
            output_format="jsonl",
        )

        with pytest.raises(ValueError, match="Unsupported extractor type"):
            runner.run(unsupported_metadata)

    def test_multiple_extractions_create_separate_runs(
        self,
        sample_metadata: ExtractionMetadata,
        secret_provider: MockSecretProvider,
    ):
        connector = make_mock_connector()
        batch1 = ExtractionBatch(records=[{"id": 1}])
        batch2 = ExtractionBatch(records=[{"id": 2}])
        mock_extractor1 = MockExtractor([batch1], secret_provider)
        mock_extractor2 = MockExtractor([batch2], secret_provider)
        runner1 = LandingRunner(connector=connector, extractors=[mock_extractor1])
        runner2 = LandingRunner(connector=connector, extractors=[mock_extractor2])

        result1 = runner1.run(sample_metadata)
        result2 = runner2.run(sample_metadata)

        assert result1.run_id != result2.run_id
        assert connector.write_data_to_table.call_count == 2
