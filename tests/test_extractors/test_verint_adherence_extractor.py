"""
Unit tests for VerintAdherenceExtractor

Tests cover:
1. Configuration validation (env-based)
2. Rolling date window logic
3. Employee list retrieval from Entra ID
4. Cursor handling
5. Error handling for incremental mode
"""

from datetime import datetime
from datetime import timedelta
from datetime import timezone
from unittest.mock import Mock
from unittest.mock import patch

import pytest

from tag_data_engineering.connectors.lakehouse_connector import LakehouseConnector
from tag_data_engineering.extractors.verint_adherence_extractor import VerintAdherenceExtractor
from tag_data_engineering.extractors.verint_adherence_extractor import VerintExtractorCursor
from tag_data_engineering.models import ExtractionMetadata
from tag_data_engineering.models import ExtractionMode
from tag_data_engineering.secrets.mock_secret_provider import MockSecretProvider


# Constants used in tests
ROLLING_WINDOW_DAYS = 30


@pytest.fixture
def secret_provider() -> MockSecretProvider:
    return MockSecretProvider(
        {
            "verint-prod-api-credentials": '{"api_key":"test-key-id","api_secret":"dGVzdC1hcGkta2V5"}',
        }
    )


@pytest.fixture
def mock_connector() -> Mock:
    return Mock(spec=LakehouseConnector)


class TestVerintExtractorCursor:
    """Test VerintExtractorCursor model."""

    def test_cursor_with_datetime(self):
        """Test cursor with last_run_time set."""
        dt = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        cursor = VerintExtractorCursor(last_run_time=dt)

        assert cursor.last_run_time == dt

    def test_cursor_without_datetime(self):
        """Test cursor with None last_run_time."""
        cursor = VerintExtractorCursor(last_run_time=None)

        assert cursor.last_run_time is None

    def test_cursor_from_dict(self):
        """Test cursor deserialization from dict."""
        data = {"last_run_time": "2025-01-15T10:30:00+00:00"}
        cursor = VerintExtractorCursor(**{"last_run_time": datetime.fromisoformat(data["last_run_time"])})

        assert cursor.last_run_time.year == 2025


class TestVerintExtractorRollingWindow:
    """Test rolling date window logic."""

    def test_iter_rolling_day_slices_no_last_run(self, secret_provider):
        """Test rolling slices without a last run time (default window)."""
        extractor = VerintAdherenceExtractor(secret_provider=secret_provider, connector=mock_connector)

        slices = list(extractor._iter_rolling_day_slices(None))

        # Should produce ROLLING_WINDOW_DAYS slices
        assert len(slices) == ROLLING_WINDOW_DAYS

    def test_iter_rolling_day_slices_with_recent_run(self, secret_provider):
        """Test rolling slices with a recent last run time."""
        extractor = VerintAdherenceExtractor(secret_provider=secret_provider, connector=mock_connector)
        # Last run was 5 days ago
        last_run = datetime.now(timezone.utc) - timedelta(days=5)

        slices = list(extractor._iter_rolling_day_slices(last_run))

        # Should extend window by days since last run
        expected_days = ROLLING_WINDOW_DAYS + 5
        assert len(slices) == expected_days

    def test_iter_rolling_day_slices_format(self, secret_provider):
        """Test that slices are in correct format."""
        extractor = VerintAdherenceExtractor(secret_provider=secret_provider, connector=mock_connector)

        slices = list(extractor._iter_rolling_day_slices(None))

        for start, end in slices:
            # Check format is ISO8601
            assert start.endswith("Z")
            assert end.endswith("Z")
            # Parse to validate
            datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ")
            datetime.strptime(end, "%Y-%m-%dT%H:%M:%SZ")

    def test_iter_rolling_day_slices_consecutive(self, secret_provider):
        """Test that slices are consecutive days."""
        extractor = VerintAdherenceExtractor(secret_provider=secret_provider, connector=mock_connector)

        slices = list(extractor._iter_rolling_day_slices(None))

        for i in range(len(slices) - 1):
            # End of current slice should equal start of next
            assert slices[i][1] == slices[i + 1][0]


class TestVerintExtractorProperties:
    """Test basic extractor properties."""

    def test_extractor_type(self, secret_provider):
        """Test extractor type property."""
        extractor = VerintAdherenceExtractor(secret_provider=secret_provider, connector=mock_connector)
        assert extractor.extractor_type == "verint_adherence"

    def test_timeout_configuration(self, secret_provider):
        """Test custom timeout configuration."""
        extractor = VerintAdherenceExtractor(secret_provider=secret_provider, connector=mock_connector, timeout_seconds=60)
        assert extractor.timeout_seconds == 60

    def test_default_timeout(self, secret_provider):
        """Test default timeout."""
        extractor = VerintAdherenceExtractor(secret_provider=secret_provider, connector=mock_connector)
        assert extractor.timeout_seconds == 30


class TestVerintExtractorIncrementalMode:
    """Test incremental mode support."""

    @patch.object(VerintAdherenceExtractor, "_get_employees_from_lakehouse")
    @patch.object(VerintAdherenceExtractor, "_extract_batch")
    def test_incremental_mode_works(self, mock_extract_batch, mock_get_employees, secret_provider, mock_connector):
        """Test that incremental extraction mode works."""
        mock_get_employees.return_value = ["user1@example.com"]
        mock_extract_batch.return_value = [{"id": 1}]

        extractor = VerintAdherenceExtractor(secret_provider=secret_provider, connector=mock_connector)
        metadata = ExtractionMetadata(
            entity="test", pipeline_group="test", extraction_mode=ExtractionMode.INCREMENTAL, max_file_size_mb=100, output_format="jsonl", extractor="verint_adherence", extractor_config={"base_url": "https://test.verint.com"}
        )

        # Should not raise - incremental is now supported
        batches = list(extractor.extract(metadata))
        assert len(batches) > 0


class TestVerintExtractorCursorIntegration:
    """Test cursor integration in extract method."""

    @patch.object(VerintAdherenceExtractor, "_get_employees_from_lakehouse")
    @patch.object(VerintAdherenceExtractor, "_extract_batch")
    def test_extract_uses_cursor_last_run_time(self, mock_extract_batch, mock_get_employees, secret_provider, mock_connector):
        """Test that extract() uses cursor's last_run_time."""
        mock_get_employees.return_value = ["user1@example.com"]
        mock_extract_batch.return_value = [{"id": 1}]

        extractor = VerintAdherenceExtractor(secret_provider=secret_provider, connector=mock_connector)
        metadata = ExtractionMetadata(
            entity="test", pipeline_group="test", extraction_mode=ExtractionMode.INCREMENTAL, max_file_size_mb=100, output_format="jsonl", extractor="verint_adherence", extractor_config={"base_url": "https://test.verint.com"}
        )

        # Cursor with last run 10 days ago (dict format as passed by landing_runner)
        last_run = datetime.now(timezone.utc) - timedelta(days=10)
        cursor = {"last_run_time": last_run.isoformat()}

        list(extractor.extract(metadata, cursor=cursor))

        # Should have extended window
        expected_days = ROLLING_WINDOW_DAYS + 10
        assert mock_extract_batch.call_count == expected_days

    @patch.object(VerintAdherenceExtractor, "_get_employees_from_lakehouse")
    @patch.object(VerintAdherenceExtractor, "_extract_batch")
    def test_extract_yields_cursor_on_final_batch(self, mock_extract_batch, mock_get_employees, secret_provider, mock_connector):
        """Test that extract() yields cursor on the final batch."""
        mock_get_employees.return_value = ["user1@example.com"]
        mock_extract_batch.return_value = [{"id": 1}]

        extractor = VerintAdherenceExtractor(secret_provider=secret_provider, connector=mock_connector)
        metadata = ExtractionMetadata(
            entity="test", pipeline_group="test", extraction_mode=ExtractionMode.FULL_REFRESH, max_file_size_mb=100, output_format="jsonl", extractor="verint_adherence", extractor_config={"base_url": "https://test.verint.com"}
        )

        batches = list(extractor.extract(metadata))

        # Final batch should have cursor set
        final_batch = batches[-1]
        assert final_batch.cursor is not None
        assert "last_run_time" in final_batch.cursor
