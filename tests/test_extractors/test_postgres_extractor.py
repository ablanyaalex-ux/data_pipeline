import logging
from datetime import datetime
from datetime import timezone

import pytest

from tag_data_engineering.extractors.postgres_extractor import PostgresExtractor
from tag_data_engineering.extractors.postgres_extractor import PostgresExtractorConfig
from tag_data_engineering.models import ExtractionMetadata
from tag_data_engineering.models import ExtractionMode
from tag_data_engineering.secrets.mock_secret_provider import MockSecretProvider


class _FakePsycopgCursor:
    def __init__(self, captured: dict[str, object], rows: list[tuple[object, ...]], columns: list[str]):
        self._captured = captured
        self._rows = rows
        self._columns = columns
        self._index = 0
        self.itersize: int | None = None
        self.description: list[tuple[str]] | None = None

    def execute(self, query: str) -> None:
        self._captured["query"] = query
        self.description = [(column,) for column in self._columns]

    def fetchone(self):
        if self._index >= len(self._rows):
            return None
        row = self._rows[self._index]
        self._index += 1
        return row

    def __iter__(self):
        while self._index < len(self._rows):
            row = self._rows[self._index]
            self._index += 1
            yield row

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakePsycopgConnection:
    def __init__(self, captured: dict[str, object], rows: list[tuple[object, ...]], columns: list[str]):
        self._captured = captured
        self._rows = rows
        self._columns = columns

    def cursor(self, name: str | None = None, **kwargs):
        self._captured["cursor_name"] = name
        cursor = _FakePsycopgCursor(self._captured, self._rows, self._columns)
        self._captured["cursor"] = cursor
        return cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _full_refresh_metadata(**overrides) -> ExtractionMetadata:
    extractor_config = {
        "source_secret_key": "test-postgres",
        "source_schema": "public",
        "source_table": "tasks",
    }
    extractor_config.update(overrides)
    return ExtractionMetadata(
        entity="cms_tasks",
        pipeline_group="postgres_cms",
        extraction_mode=ExtractionMode.FULL_REFRESH,
        max_file_size_mb=10,
        output_format="jsonl",
        extractor="postgres",
        extractor_config=extractor_config,
    )


def _incremental_metadata(**overrides) -> ExtractionMetadata:
    extractor_config = {
        "source_secret_key": "test-postgres",
        "source_schema": "public",
        "source_table": "tasks",
        "incremental": {
            "column": "updated_at",
            "column_type": "DateTime",
        },
    }
    extractor_config.update(overrides)
    return ExtractionMetadata(
        entity="cms_tasks",
        pipeline_group="postgres_cms",
        extraction_mode=ExtractionMode.INCREMENTAL,
        max_file_size_mb=10,
        output_format="jsonl",
        extractor="postgres",
        extractor_config=extractor_config,
    )


def _composite_incremental_metadata(**overrides) -> ExtractionMetadata:
    extractor_config = {
        "source_secret_key": "test-postgres",
        "source_schema": "public",
        "source_table": "tasks",
        "incremental": {
            "columns": [
                {
                    "name": "updated_at",
                    "type": "DateTime",
                },
                {
                    "name": "id",
                    "type": "Int",
                },
            ]
        },
    }
    extractor_config.update(overrides)
    return ExtractionMetadata(
        entity="cms_tasks",
        pipeline_group="postgres_cms",
        extraction_mode=ExtractionMode.INCREMENTAL,
        max_file_size_mb=10,
        output_format="jsonl",
        extractor="postgres",
        extractor_config=extractor_config,
    )


@pytest.fixture
def mock_secret_provider() -> MockSecretProvider:
    return MockSecretProvider({"test-postgres": '{"host":"localhost","port":"5432","username":"postgres","password":"postgres","database":"cms_prod"}'})


@pytest.fixture(autouse=True)
def stub_register_hstore(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "tag_data_engineering.extractors.postgres_extractor.register_hstore",
        lambda connection, globally=False, unicode=True: None,
    )


def test_postgres_extractor_type_and_config_class():
    extractor = PostgresExtractor(secret_provider=MockSecretProvider({}))

    assert extractor.extractor_type == "postgres"
    assert extractor._config_class is PostgresExtractorConfig


def test_extract_full_refresh_returns_rows_from_psycopg_stream(
    mock_secret_provider: MockSecretProvider,
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, object] = {}
    rows = [
        (1, "Task 1", "2025-01-10T09:15:30+00:00"),
        (2, "Task 2", "2025-01-11T14:42:10+00:00"),
    ]
    columns = ["id", "title", "updated_at"]
    monkeypatch.setattr(
        "tag_data_engineering.extractors.postgres_extractor.psycopg2.connect",
        lambda **kwargs: captured.update({"connect_kwargs": kwargs}) or _FakePsycopgConnection(captured, rows, columns),
    )
    monkeypatch.setattr(
        "tag_data_engineering.extractors.postgres_extractor.register_hstore",
        lambda connection, globally=False, unicode=True: captured.update({"hstore_registered": (connection, globally, unicode)}),
    )

    extractor = PostgresExtractor(secret_provider=mock_secret_provider)
    batches = list(extractor.extract(_full_refresh_metadata()))

    assert len(batches) == 1
    assert [record["id"] for record in batches[0].records] == [1, 2]
    assert batches[0].cursor is None
    assert captured["connect_kwargs"]["host"] == "localhost"
    assert captured["connect_kwargs"]["port"] == "5432"
    assert captured["connect_kwargs"]["user"] == "postgres"
    assert captured["connect_kwargs"]["password"] == "postgres"
    assert captured["connect_kwargs"]["dbname"] == "cms_prod"
    assert captured["connect_kwargs"]["keepalives"] == 1
    assert captured["connect_kwargs"]["keepalives_idle"] == 300
    assert captured["connect_kwargs"]["keepalives_interval"] == 10
    assert captured["connect_kwargs"]["keepalives_count"] == 5
    assert captured["hstore_registered"][1:] == (False, True)


def test_extract_incremental_applies_single_cursor_filter(
    mock_secret_provider: MockSecretProvider,
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, object] = {}
    rows = [(2, "Task 2", "2025-01-11T14:42:10.456000+00:00"), (3, "Task 3", "2025-01-11T14:42:10.456000+00:00")]
    columns = ["id", "title", "updated_at"]
    monkeypatch.setattr(
        "tag_data_engineering.extractors.postgres_extractor.psycopg2.connect",
        lambda **kwargs: _FakePsycopgConnection(captured, rows, columns),
    )

    extractor = PostgresExtractor(secret_provider=mock_secret_provider)
    batches = list(extractor.extract(_incremental_metadata(), cursor={"updated_at": "2025-01-11T14:42:10.456000+00:00"}))

    assert len(batches) == 1
    assert [record["id"] for record in batches[0].records] == [2, 3]
    assert batches[0].cursor == {"updated_at": "2025-01-11T14:42:10.456000+00:00"}
    assert captured["query"] == 'SELECT * FROM "public"."tasks" WHERE ("updated_at" >= \'2025-01-11 14:42:10.456000+00:00\') ORDER BY "updated_at" ASC'


def test_extract_incremental_applies_composite_cursor_filter(
    mock_secret_provider: MockSecretProvider,
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, object] = {}
    rows = [
        (2, "Task 2", "2025-01-11T14:42:10.456000+00:00"),
        (3, "Task 3", "2025-01-11T14:42:10.456000+00:00"),
    ]
    columns = ["id", "title", "updated_at"]
    monkeypatch.setattr(
        "tag_data_engineering.extractors.postgres_extractor.psycopg2.connect",
        lambda **kwargs: _FakePsycopgConnection(captured, rows, columns),
    )

    extractor = PostgresExtractor(secret_provider=mock_secret_provider)
    batches = list(
        extractor.extract(
            _composite_incremental_metadata(),
            cursor={"updated_at": "2025-01-11T14:42:10.456000+00:00", "id": "2"},
        )
    )

    assert len(batches) == 1
    assert [record["id"] for record in batches[0].records] == [2, 3]
    assert batches[0].cursor == {
        "updated_at": "2025-01-11T14:42:10.456000+00:00",
        "id": "3",
    }
    assert captured["query"] == ('SELECT * FROM "public"."tasks" WHERE ("updated_at" > \'2025-01-11 14:42:10.456000+00:00\') OR ("updated_at" = \'2025-01-11 14:42:10.456000+00:00\' AND "id" >= 2) ORDER BY "updated_at" ASC, "id" ASC')


def test_extract_incremental_empty_run_re_emits_cursor(
    mock_secret_provider: MockSecretProvider,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        "tag_data_engineering.extractors.postgres_extractor.psycopg2.connect",
        lambda **kwargs: _FakePsycopgConnection({}, [], ["id", "title", "updated_at"]),
    )

    extractor = PostgresExtractor(secret_provider=mock_secret_provider)
    cursor = {"updated_at": "2025-01-12T00:00:00+00:00"}
    batches = list(extractor.extract(_incremental_metadata(), cursor=cursor))

    assert len(batches) == 1
    assert batches[0].records == []
    assert batches[0].cursor == cursor


def test_extract_serializes_datetime_values(
    mock_secret_provider: MockSecretProvider,
    monkeypatch: pytest.MonkeyPatch,
):
    rows = [(4, "Task 4", datetime(2025, 1, 12, 10, 30, tzinfo=timezone.utc), datetime(2025, 1, 12).date(), float("nan"))]
    columns = ["id", "title", "updated_at", "due_date", "score"]
    monkeypatch.setattr(
        "tag_data_engineering.extractors.postgres_extractor.psycopg2.connect",
        lambda **kwargs: _FakePsycopgConnection({}, rows, columns),
    )

    extractor = PostgresExtractor(secret_provider=mock_secret_provider)
    batches = list(extractor.extract(_incremental_metadata()))

    assert batches[0].records[0]["updated_at"] == "2025-01-12T10:30:00+00:00"
    assert batches[0].records[0]["due_date"] == "2025-01-12"
    assert batches[0].records[0]["score"] is None


def test_extract_preserves_hstore_as_decoded_dict(
    mock_secret_provider: MockSecretProvider,
    monkeypatch: pytest.MonkeyPatch,
):
    rows = [(1, {"message": "Initial task created"}, "2025-01-10T00:00:00+00:00")]
    columns = ["id", "initial_message", "updated_at"]
    monkeypatch.setattr(
        "tag_data_engineering.extractors.postgres_extractor.psycopg2.connect",
        lambda **kwargs: _FakePsycopgConnection({}, rows, columns),
    )
    monkeypatch.setattr(
        "tag_data_engineering.extractors.postgres_extractor.register_hstore",
        lambda connection, globally=False, unicode=True: None,
    )

    extractor = PostgresExtractor(secret_provider=mock_secret_provider)
    batches = list(extractor.extract(_incremental_metadata()))

    assert batches[0].records[0]["initial_message"] == {"message": "Initial task created"}


def test_extract_batches_rows_using_chunk_size(
    mock_secret_provider: MockSecretProvider,
    monkeypatch: pytest.MonkeyPatch,
):
    rows = [
        (1, "Task 1", "2025-01-10T00:00:00+00:00"),
        (2, "Task 2", "2025-01-11T00:00:00+00:00"),
        (3, "Task 3", "2025-01-12T00:00:00+00:00"),
    ]
    columns = ["id", "title", "updated_at"]
    monkeypatch.setattr(
        "tag_data_engineering.extractors.postgres_extractor.psycopg2.connect",
        lambda **kwargs: _FakePsycopgConnection({}, rows, columns),
    )

    extractor = PostgresExtractor(secret_provider=mock_secret_provider, chunk_size=2)
    batches = list(extractor.extract(_full_refresh_metadata()))

    assert len(batches) == 2
    assert [record["id"] for record in batches[0].records] == [1, 2]
    assert [record["id"] for record in batches[1].records] == [3]


def test_extract_uses_named_cursor_and_itersize(
    mock_secret_provider: MockSecretProvider,
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "tag_data_engineering.extractors.postgres_extractor.psycopg2.connect",
        lambda **kwargs: _FakePsycopgConnection(captured, [(1, "Task 1", "2025-01-10T00:00:00+00:00")], ["id", "title", "updated_at"]),
    )

    extractor = PostgresExtractor(secret_provider=mock_secret_provider, chunk_size=1234)
    list(extractor.extract(_full_refresh_metadata()))

    assert isinstance(captured["cursor_name"], str)
    assert captured["cursor_name"].startswith("tasks_")
    assert captured["cursor"].itersize == 1234


def test_extract_logs_progress_and_throughput(
    mock_secret_provider: MockSecretProvider,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    rows = [
        (1, "Task 1", "2025-01-10T00:00:00+00:00"),
        (2, "Task 2", "2025-01-11T00:00:00+00:00"),
        (3, "Task 3", "2025-01-12T00:00:00+00:00"),
    ]
    columns = ["id", "title", "updated_at"]
    monkeypatch.setattr(
        "tag_data_engineering.extractors.postgres_extractor.psycopg2.connect",
        lambda **kwargs: _FakePsycopgConnection({}, rows, columns),
    )

    extractor = PostgresExtractor(secret_provider=mock_secret_provider, chunk_size=2)
    with caplog.at_level(logging.INFO):
        list(extractor.extract(_incremental_metadata(), cursor={"updated_at": "2025-01-10T00:00:00+00:00"}))

    assert "postgres extractor starting incremental extraction for public.tasks" in caplog.text
    assert "postgres extractor executed query for public.tasks in " in caplog.text
    assert "postgres extractor emitting chunk 1 from public.tasks: 2 rows in chunk, 2 rows fetched total, cursor=updated_at=2025-01-11T00:00:00+00:00" in caplog.text
    assert "postgres extractor throughput for public.tasks:" in caplog.text
    assert "postgres extractor completed public.tasks with 3 rows across 2 chunk(s);" in caplog.text
