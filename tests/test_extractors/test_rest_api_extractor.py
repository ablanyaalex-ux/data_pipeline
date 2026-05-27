from unittest.mock import Mock
from unittest.mock import patch

import pytest

from tag_data_engineering.extractors.rest_api_extractor import RestApiExtractor
from tag_data_engineering.extractors.rest_api_extractor import RestApiExtractorConfig
from tag_data_engineering.models import ExtractionMetadata
from tag_data_engineering.models import ExtractionMode
from tag_data_engineering.secrets.mock_secret_provider import MockSecretProvider


@pytest.fixture
def mock_secret_provider() -> MockSecretProvider:
    """Provides a mock secret provider for testing."""
    return MockSecretProvider({})


class TestRestApiExtractor:
    def test_extractor_type_is_rest_api(self, mock_secret_provider):
        extractor = RestApiExtractor(secret_provider=mock_secret_provider)
        assert extractor.extractor_type == "rest_api"

    def test_custom_timeout_is_set(self, mock_secret_provider):
        extractor = RestApiExtractor(secret_provider=mock_secret_provider, timeout_seconds=60)
        assert extractor.timeout_seconds == 60

    def test_incremental_mode_raises_error_with_helpful_message(self, mock_secret_provider):
        extractor = RestApiExtractor(secret_provider=mock_secret_provider)
        metadata = ExtractionMetadata(
            entity="test_entity",
            pipeline_group="test",
            extraction_mode=ExtractionMode.INCREMENTAL,
            max_file_size_mb=100,
            output_format="jsonl",
            extractor="rest_api",
            extractor_config={
                "base_url": "https://api.example.com",
                "endpoint": "users",
                "results_key": "results",
                "next_key": None,
            },
        )
        with pytest.raises(ValueError) as exc_info:
            list(extractor.extract(metadata))
        error_message = str(exc_info.value)
        assert "REST API extractor does not support incremental extraction mode" in error_message
        assert "test_entity" in error_message
        assert "copy_job" in error_message
        assert "full_refresh" in error_message

    @patch("tag_data_engineering.extractors.rest_api_extractor.requests.get")
    def test_single_page_extraction_without_pagination(self, mock_get, mock_secret_provider):
        extractor = RestApiExtractor(secret_provider=mock_secret_provider)
        mock_response = Mock()
        mock_response.json.return_value = {
            "results": [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
            ],
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        metadata = ExtractionMetadata(
            entity="users",
            pipeline_group="test",
            extraction_mode=ExtractionMode.FULL_REFRESH,
            max_file_size_mb=100,
            output_format="jsonl",
            extractor="rest_api",
            extractor_config={
                "base_url": "https://api.example.com",
                "endpoint": "users",
                "results_key": "results",
                "next_key": None,
            },
        )
        batches = list(extractor.extract(metadata))
        assert len(batches) == 1
        assert len(batches[0].records) == 2
        assert batches[0].records[0]["name"] == "Alice"
        assert batches[0].records[1]["name"] == "Bob"
        mock_get.assert_called_once_with(
            "https://api.example.com/users/",
            headers={},
            timeout=30,
        )

    @patch("tag_data_engineering.extractors.rest_api_extractor.requests.get")
    def test_multi_page_extraction_follows_next_links(self, mock_get, mock_secret_provider):
        extractor = RestApiExtractor(secret_provider=mock_secret_provider)
        page1_response = Mock()
        page1_response.json.return_value = {
            "results": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
            "next": "https://api.example.com/users/?page=2",
        }
        page1_response.raise_for_status = Mock()
        page2_response = Mock()
        page2_response.json.return_value = {
            "results": [{"id": 3, "name": "Charlie"}],
            "next": None,
        }
        page2_response.raise_for_status = Mock()
        mock_get.side_effect = [page1_response, page2_response]
        metadata = ExtractionMetadata(
            entity="users",
            pipeline_group="test",
            extraction_mode=ExtractionMode.FULL_REFRESH,
            max_file_size_mb=100,
            output_format="jsonl",
            extractor="rest_api",
            extractor_config={
                "base_url": "https://api.example.com",
                "endpoint": "users",
                "results_key": "results",
                "next_key": "next",
            },
        )
        batches = list(extractor.extract(metadata))
        assert len(batches) == 2
        assert len(batches[0].records) == 2
        assert len(batches[1].records) == 1
        assert batches[0].records[0]["name"] == "Alice"
        assert batches[1].records[0]["name"] == "Charlie"
        assert mock_get.call_count == 2

    @patch("tag_data_engineering.extractors.rest_api_extractor.requests.get")
    def test_custom_headers_are_passed_to_requests(self, mock_get, mock_secret_provider):
        extractor = RestApiExtractor(secret_provider=mock_secret_provider)
        mock_response = Mock()
        mock_response.json.return_value = {"results": [{"id": 1}]}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        metadata = ExtractionMetadata(
            entity="users",
            pipeline_group="test",
            extraction_mode=ExtractionMode.FULL_REFRESH,
            max_file_size_mb=100,
            output_format="jsonl",
            extractor="rest_api",
            extractor_config={
                "base_url": "https://api.example.com",
                "endpoint": "users",
                "results_key": "results",
                "next_key": None,
                "headers": {
                    "Authorization": "Bearer token123",
                    "X-Custom-Header": "value",
                },
            },
        )
        list(extractor.extract(metadata))
        mock_get.assert_called_once_with(
            "https://api.example.com/users/",
            headers={
                "Authorization": "Bearer token123",
                "X-Custom-Header": "value",
            },
            timeout=30,
        )

    @patch("tag_data_engineering.extractors.rest_api_extractor.requests.get")
    def test_empty_results_returns_no_batches(self, mock_get, mock_secret_provider):
        extractor = RestApiExtractor(secret_provider=mock_secret_provider)
        mock_response = Mock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        metadata = ExtractionMetadata(
            entity="users",
            pipeline_group="test",
            extraction_mode=ExtractionMode.FULL_REFRESH,
            max_file_size_mb=100,
            output_format="jsonl",
            extractor="rest_api",
            extractor_config={
                "base_url": "https://api.example.com",
                "endpoint": "users",
                "results_key": "results",
                "next_key": None,
            },
        )
        batches = list(extractor.extract(metadata))
        assert len(batches) == 0

    @patch("tag_data_engineering.extractors.rest_api_extractor.requests.get")
    def test_missing_results_key_returns_no_batches(self, mock_get, mock_secret_provider):
        extractor = RestApiExtractor(secret_provider=mock_secret_provider)
        mock_response = Mock()
        mock_response.json.return_value = {"data": [{"id": 1}]}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        metadata = ExtractionMetadata(
            entity="users",
            pipeline_group="test",
            extraction_mode=ExtractionMode.FULL_REFRESH,
            max_file_size_mb=100,
            output_format="jsonl",
            extractor="rest_api",
            extractor_config={
                "base_url": "https://api.example.com",
                "endpoint": "users",
                "results_key": "results",
                "next_key": None,
            },
        )
        batches = list(extractor.extract(metadata))
        assert len(batches) == 0

    @patch("tag_data_engineering.extractors.rest_api_extractor.requests.get")
    def test_http_errors_are_propagated(self, mock_get, mock_secret_provider):
        extractor = RestApiExtractor(secret_provider=mock_secret_provider)
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")
        mock_get.return_value = mock_response
        metadata = ExtractionMetadata(
            entity="users",
            pipeline_group="test",
            extraction_mode=ExtractionMode.FULL_REFRESH,
            max_file_size_mb=100,
            output_format="jsonl",
            extractor="rest_api",
            extractor_config={
                "base_url": "https://api.example.com",
                "endpoint": "users",
                "results_key": "results",
                "next_key": None,
            },
        )
        with pytest.raises(Exception, match="404 Not Found"):
            list(extractor.extract(metadata))

    @patch("tag_data_engineering.extractors.rest_api_extractor.requests.get")
    def test_trailing_and_leading_slashes_are_normalized(self, mock_get, mock_secret_provider):
        extractor = RestApiExtractor(secret_provider=mock_secret_provider)
        mock_response = Mock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        metadata = ExtractionMetadata(
            entity="users",
            pipeline_group="test",
            extraction_mode=ExtractionMode.FULL_REFRESH,
            max_file_size_mb=100,
            output_format="jsonl",
            extractor="rest_api",
            extractor_config={
                "base_url": "https://api.example.com/",
                "endpoint": "/users",
                "results_key": "results",
                "next_key": None,
            },
        )
        list(extractor.extract(metadata))
        mock_get.assert_called_once_with(
            "https://api.example.com/users/",
            headers={},
            timeout=30,
        )


class TestRestApiExtractorConfig:
    def test_config_validates_all_fields(self):
        config = RestApiExtractorConfig(
            base_url="https://api.example.com",
            endpoint="users",
            results_key="results",
            next_key="next",
            headers={"Authorization": "Bearer token"},
        )
        assert config.base_url == "https://api.example.com"
        assert config.endpoint == "users"
        assert config.results_key == "results"
        assert config.next_key == "next"
        assert config.headers == {"Authorization": "Bearer token"}

    def test_config_uses_default_values(self):
        config = RestApiExtractorConfig(
            base_url="https://api.example.com",
            endpoint="users",
            results_key="results",
            next_key=None,
        )
        assert config.headers == {}
        assert config.next_key is None

    def test_config_parses_from_dict(self):
        config_dict = {
            "base_url": "https://swapi.dev/api",
            "endpoint": "people",
            "results_key": "results",
            "next_key": "next",
            "headers": {"User-Agent": "test"},
        }
        config = RestApiExtractorConfig.model_validate(config_dict)
        assert config.base_url == "https://swapi.dev/api"
        assert config.endpoint == "people"
        assert config.headers["User-Agent"] == "test"
