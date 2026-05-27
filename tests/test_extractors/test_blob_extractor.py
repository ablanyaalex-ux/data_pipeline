from datetime import datetime
from datetime import timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tag_data_engineering.extractors.blob_extractor import BlobExtractor
from tag_data_engineering.extractors.blob_extractor import BlobSourceConfig
from tag_data_engineering.extractors.blob_extractor import BlobSourceFactory
from tag_data_engineering.models import ExtractionMetadata
from tag_data_engineering.models import ExtractionMode
from tag_data_engineering.secrets.mock_secret_provider import MockSecretProvider


def test_blob_source_config_requires_url_or_keyvault():
    with pytest.raises(ValueError, match="Field required"):
        BlobSourceConfig.model_validate(
            {
                "source_container": "ingest-data",
                "source_folder": "finance_monthly_budgets",
            }
        )


def test_build_uses_resolved_blob_account_url(monkeypatch: pytest.MonkeyPatch):
    fake_blob_service_client = Mock()
    monkeypatch.setattr(
        "tag_data_engineering.extractors.blob_extractor.BlobServiceClient",
        fake_blob_service_client,
    )

    factory = BlobSourceFactory(
        secret_provider=MockSecretProvider(
            secrets={
                "tenant-id": "tenant",
                "de-sp-credentials": '{"client_id":"client","client_secret":"secret"}',
                "hierarchy-storage-credentials": '{"account_name":"myhrreportexports"}',
            }
        )
    )

    factory.build(
        BlobSourceConfig(
            source_container="cascadereportuploads",
            source_folder="DataEngineering/Hierarchy",
            blob_account_url_keyvault="hierarchy-storage-credentials",
        )
    )

    assert fake_blob_service_client.call_args.kwargs["account_url"] == "https://myhrreportexports.blob.core.windows.net"


def _make_csv_content(rows: list[dict]) -> str:
    headers = list(rows[0].keys())
    lines = [",".join(headers)]
    for row in rows:
        values = ["" if row[header] is None else str(row[header]) for header in headers]
        lines.append(",".join(values))
    return "\n".join(lines)


def _make_metadata(entity: str, source_container: str, source_folder: str, blob_account_url_keyvault: str) -> ExtractionMetadata:
    return ExtractionMetadata(
        entity=entity,
        pipeline_group="other",
        extraction_mode=ExtractionMode.INCREMENTAL,
        max_file_size_mb=100,
        output_format="jsonl",
        extractor="blob",
        extractor_config={
            "source_container": source_container,
            "source_folder": source_folder,
            "blob_account_url_keyvault": blob_account_url_keyvault,
        },
    )


def test_extract_initial_load_includes_all_files_and_filename_for_keyvault_config():
    metadata = _make_metadata(
        entity="finance_monthly_budgets",
        source_container="ingest-data",
        source_folder="finance_monthly_budgets",
        blob_account_url_keyvault="data-ingest-storage-credentials",
    )
    blob_source = Mock()
    blob_source.list_objects.return_value = [
        SimpleNamespace(
            object_name="finance_monthly_budgets/a.csv",
            last_modified=datetime(2025, 1, 1, 8, 0, tzinfo=timezone.utc),
        ),
        SimpleNamespace(
            object_name="finance_monthly_budgets/b.csv",
            last_modified=datetime(2025, 1, 2, 8, 0, tzinfo=timezone.utc),
        ),
    ]
    blob_source.read_object.side_effect = [
        _make_csv_content(
            [
                {
                    "Year": "2026",
                    "Month": "2026-01-01 00:00:00",
                    "Label": "Communications",
                    "CaseStatus": "Fcast_AddChecks",
                    "CaseVolume": "1985.1",
                }
            ]
        ),
        _make_csv_content(
            [
                {
                    "Year": "2026",
                    "Month": "2026-02-01 00:00:00",
                    "Label": "Communications",
                    "CaseStatus": "Fcast_AddChecks",
                    "CaseVolume": "1670.1",
                }
            ]
        ),
    ]
    blob_source_factory = Mock()
    blob_source_factory.build.return_value = blob_source
    extractor = BlobExtractor(
        secret_provider=MockSecretProvider(secrets={}),
        blob_source_factory=blob_source_factory,
    )

    batches = list(extractor.extract(metadata))

    assert len(batches) == 1
    assert batches[0].records[0]["source_file_name"] == "a.csv"
    assert batches[0].records[0]["Year"] == "2026"
    assert batches[0].records[1]["source_file_name"] == "b.csv"
    assert batches[0].records[1]["Month"] == "2026-02-01 00:00:00"
    blob_source_factory.build.assert_called_once_with(BlobSourceConfig.model_validate(metadata.extractor_config))
    assert batches[-1].cursor == {
        "last_modified": "2025-01-02T08:00:00Z",
        "last_object_name": "finance_monthly_budgets/b.csv",
    }


def test_extract_initial_load_includes_all_files_and_filename_for_hierarchy_blob_config():
    metadata = _make_metadata(
        entity="myhr_hierarchy_history",
        source_container="ingestedfiles",
        source_folder="myhr_hierarchy",
        blob_account_url_keyvault="hierarchy-storage-credentials",
    )
    blob_source = Mock()
    blob_source.list_objects.return_value = [
        SimpleNamespace(
            object_name="myhr_hierarchy/a.csv",
            last_modified=datetime(2025, 1, 1, 8, 0, tzinfo=timezone.utc),
        ),
        SimpleNamespace(
            object_name="myhr_hierarchy/b.csv",
            last_modified=datetime(2025, 1, 2, 8, 0, tzinfo=timezone.utc),
        ),
    ]
    blob_source.read_object.side_effect = [
        _make_csv_content([{"Employee Id": "123"}]),
        _make_csv_content([{"Employee Id": "456"}]),
    ]
    blob_source_factory = Mock()
    blob_source_factory.build.return_value = blob_source
    extractor = BlobExtractor(
        secret_provider=MockSecretProvider(secrets={}),
        blob_source_factory=blob_source_factory,
    )

    batches = list(extractor.extract(metadata))

    assert len(batches) == 1
    assert batches[0].records[0]["source_file_name"] == "a.csv"
    assert batches[0].records[0]["Employee Id"] == "123"
    assert batches[0].records[1]["source_file_name"] == "b.csv"
    assert batches[0].records[1]["Employee Id"] == "456"
    blob_source_factory.build.assert_called_once_with(BlobSourceConfig.model_validate(metadata.extractor_config))
    assert batches[-1].cursor == {
        "last_modified": "2025-01-02T08:00:00Z",
        "last_object_name": "myhr_hierarchy/b.csv",
    }


def test_extract_incremental_uses_last_modified_cursor_and_tie_breaker():
    metadata = _make_metadata(
        entity="finance_monthly_budgets",
        source_container="ingest-data",
        source_folder="finance_monthly_budgets",
        blob_account_url_keyvault="data-ingest-storage-credentials",
    )
    blob_source = Mock()
    blob_source.list_objects.return_value = [
        SimpleNamespace(
            object_name="finance_monthly_budgets/a.csv",
            last_modified=datetime(2025, 1, 2, 8, 0, tzinfo=timezone.utc),
        ),
        SimpleNamespace(
            object_name="finance_monthly_budgets/b.csv",
            last_modified=datetime(2025, 1, 2, 8, 0, tzinfo=timezone.utc),
        ),
        SimpleNamespace(
            object_name="finance_monthly_budgets/c.csv",
            last_modified=datetime(2025, 1, 3, 8, 0, tzinfo=timezone.utc),
        ),
    ]
    blob_source.read_object.side_effect = [
        _make_csv_content([{"Year": "2026"}]),
        _make_csv_content([{"Year": "2027"}]),
    ]
    blob_source_factory = Mock()
    blob_source_factory.build.return_value = blob_source
    extractor = BlobExtractor(
        secret_provider=MockSecretProvider(secrets={}),
        blob_source_factory=blob_source_factory,
    )

    batches = list(
        extractor.extract(
            metadata,
            cursor={
                "last_modified": "2025-01-02T08:00:00Z",
                "last_object_name": "finance_monthly_budgets/a.csv",
            },
        )
    )

    assert len(batches) == 1
    assert [record["source_file_name"] for record in batches[0].records] == ["b.csv", "c.csv"]
    assert batches[-1].cursor == {
        "last_modified": "2025-01-03T08:00:00Z",
        "last_object_name": "finance_monthly_budgets/c.csv",
    }


def test_extract_uses_file_encoding_when_specified():
    metadata = ExtractionMetadata(
        entity="finance_monthly_budgets",
        pipeline_group="other",
        extraction_mode=ExtractionMode.INCREMENTAL,
        max_file_size_mb=100,
        output_format="jsonl",
        extractor="blob",
        extractor_config={
            "source_container": "ingest-data",
            "source_folder": "finance_monthly_budgets",
            "blob_account_url_keyvault": "data-ingest-storage-credentials",
            "file_encoding": "cp1252",
        },
    )
    blob_source = Mock()
    blob_source.list_objects.return_value = [
        SimpleNamespace(
            object_name="finance_monthly_budgets/a.csv",
            last_modified=datetime(2025, 1, 1, 8, 0, tzinfo=timezone.utc),
        ),
    ]
    blob_source.read_object.return_value = _make_csv_content([{"Label": "Budget"}]).encode("cp1252")
    blob_source_factory = Mock()
    blob_source_factory.build.return_value = blob_source
    extractor = BlobExtractor(
        secret_provider=MockSecretProvider(secrets={}),
        blob_source_factory=blob_source_factory,
    )

    batches = list(extractor.extract(metadata))

    assert len(batches) == 1
    assert batches[0].records[0]["Label"] == "Budget"
    blob_source.read_object.assert_called_once_with("ingest-data", "finance_monthly_budgets/a.csv")


def test_extract_emits_empty_batch_to_preserve_cursor_when_no_new_files():
    metadata = _make_metadata(
        entity="myhr_hierarchy_history",
        source_container="ingestedfiles",
        source_folder="myhr_hierarchy",
        blob_account_url_keyvault="hierarchy-storage-credentials",
    )
    blob_source = Mock()
    blob_source.list_objects.return_value = [
        SimpleNamespace(
            object_name="myhr_hierarchy/a.csv",
            last_modified=datetime(2025, 1, 1, 8, 0, tzinfo=timezone.utc),
        ),
    ]
    blob_source_factory = Mock()
    blob_source_factory.build.return_value = blob_source
    extractor = BlobExtractor(
        secret_provider=MockSecretProvider(secrets={}),
        blob_source_factory=blob_source_factory,
    )

    batches = list(
        extractor.extract(
            metadata,
            cursor={
                "last_modified": "2025-01-01T08:00:00Z",
                "last_object_name": "myhr_hierarchy/a.csv",
            },
        )
    )

    assert len(batches) == 1
    assert batches[0].records == []
    assert batches[0].cursor == {
        "last_modified": "2025-01-01T08:00:00Z",
        "last_object_name": "myhr_hierarchy/a.csv",
    }
