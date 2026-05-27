from datetime import datetime
from datetime import timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy import text

import tag_data_engineering.extractors.sql_server_extractor as sql_server_extractor_module
from tag_data_engineering.extractors.sql_server_extractor import SqlServerExtractor
from tag_data_engineering.extractors.sql_server_extractor import SqlServerExtractorConfig
from tag_data_engineering.models import ExtractionMetadata
from tag_data_engineering.models import ExtractionMode
from tag_data_engineering.secrets.mock_secret_provider import MockSecretProvider


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def __iter__(self):
        return iter(self._rows)


class _FakeConnection:
    def __init__(self, captured: dict[str, str], rows):
        self._captured = captured
        self._rows = rows

    def execution_options(self, **kwargs):
        return self

    def execute(self, query):
        self._captured["query"] = str(query)
        return _FakeResult(self._rows)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeEngine:
    def __init__(self, captured: dict[str, str], rows):
        self._captured = captured
        self._rows = rows

    def connect(self):
        return _FakeConnection(self._captured, self._rows)


def _full_refresh_metadata(**overrides) -> ExtractionMetadata:
    extractor_config = {
        "source_secret_key": "puzzel-mssql-credentials",
        "source_table": "call_events",
    }
    extractor_config.update(overrides)
    return ExtractionMetadata(
        entity="puzzel_call_events",
        pipeline_group="other",
        extraction_mode=ExtractionMode.FULL_REFRESH,
        max_file_size_mb=10,
        output_format="jsonl",
        extractor="sql_server",
        extractor_config=extractor_config,
    )


def _incremental_metadata(**overrides) -> ExtractionMetadata:
    extractor_config = {
        "source_secret_key": "puzzel-mssql-credentials",
        "source_table": "call_events",
        "incremental": {
            "column": "dte_updated",
            "column_type": "DateTime",
        },
    }
    extractor_config.update(overrides)
    return ExtractionMetadata(
        entity="puzzel_call_events",
        pipeline_group="other",
        extraction_mode=ExtractionMode.INCREMENTAL,
        max_file_size_mb=10,
        output_format="jsonl",
        extractor="sql_server",
        extractor_config=extractor_config,
    )


def _composite_incremental_metadata(**overrides) -> ExtractionMetadata:
    extractor_config = {
        "source_secret_key": "puzzel-mssql-credentials",
        "source_table": "call_events",
        "incremental": {
            "columns": [
                {
                    "name": "dte_updated",
                    "type": "DateTime",
                },
                {
                    "name": "call_sequence",
                    "type": "Int",
                },
            ],
        },
    }
    extractor_config.update(overrides)
    return ExtractionMetadata(
        entity="puzzel_call_events",
        pipeline_group="other",
        extraction_mode=ExtractionMode.INCREMENTAL,
        max_file_size_mb=10,
        output_format="jsonl",
        extractor="sql_server",
        extractor_config=extractor_config,
    )


@pytest.fixture
def sqlite_engine():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text("""
                CREATE TABLE call_events (
                    call_sequence INTEGER PRIMARY KEY,
                    queue_key TEXT,
                    dte_updated TEXT NOT NULL,
                    event_type TEXT NOT NULL
                )
            """)
        )
        connection.execute(
            text("""
                INSERT INTO call_events (call_sequence, queue_key, dte_updated, event_type)
                VALUES
                (1, 'QUEUE-A', '2025-01-10T09:15:30.123000+00:00', 'CONNECT'),
                (2, 'QUEUE-A', '2025-01-11T14:42:10.456000+00:00', 'TRANSFER'),
                (3, 'QUEUE-B', '2025-01-11T14:42:10.456000+00:00', 'DISCONNECT')
            """)
        )
    yield engine
    engine.dispose()


@pytest.fixture
def mock_secret_provider() -> MockSecretProvider:
    return MockSecretProvider(
        {
            "puzzel-mssql-credentials": '{"host":"localhost","port":"1433","username":"sa","password":"YourStrong!Passw0rd","database":"ConnectCallData_26295"}',
            "custom-puzzel-secret": '{"host":"localhost","port":"1433","username":"sa","password":"AnotherStrong!Passw0rd","database":"ConnectCallData_26295"}',
        }
    )


@pytest.fixture
def extractor(sqlite_engine, mock_secret_provider: MockSecretProvider) -> SqlServerExtractor:
    return SqlServerExtractor(secret_provider=mock_secret_provider, engine=sqlite_engine)


def test_sql_server_extractor_type_and_config_class():
    extractor = SqlServerExtractor(secret_provider=MockSecretProvider({}))

    assert extractor.extractor_type == "sql_server"
    assert extractor._config_class is SqlServerExtractorConfig


def test_extract_full_refresh_requires_new_metadata_contract(extractor: SqlServerExtractor):
    batches = list(extractor.extract(_full_refresh_metadata()))

    assert len(batches) == 1
    assert len(batches[0].records) == 3
    assert batches[0].records[0]["call_sequence"] == 1


def test_extract_missing_source_secret_key_fails_fast(sqlite_engine):
    extractor = SqlServerExtractor(secret_provider=MockSecretProvider({}), engine=sqlite_engine)

    with pytest.raises(Exception, match="source_secret_key"):
        list(extractor.extract(_full_refresh_metadata(source_secret_key=None)))


def test_incremental_config_optional_for_full_refresh(extractor: SqlServerExtractor):
    batches = list(extractor.extract(_full_refresh_metadata()))

    assert len(batches) == 1
    assert len(batches[0].records) == 3


def test_extract_incremental_applies_single_cursor_filter(extractor: SqlServerExtractor):
    captured: dict[str, str] = {}
    extractor._engine = _FakeEngine(
        captured,
        [
            {"call_sequence": 2, "dte_updated": "2025-01-11T14:42:10.456000+00:00"},
            {"call_sequence": 3, "dte_updated": "2025-01-11T14:42:10.456000+00:00"},
        ],
    )

    batches = list(
        extractor.extract(
            _incremental_metadata(),
            cursor={"dte_updated": "2025-01-11T14:42:10.456000+00:00"},
        )
    )

    assert len(batches) == 1
    assert [record["call_sequence"] for record in batches[0].records] == [2, 3]
    assert batches[0].cursor == {"dte_updated": "2025-01-11T14:42:10.456000+00:00"}


def test_extract_incremental_applies_composite_cursor_filter(extractor: SqlServerExtractor):
    captured: dict[str, str] = {}
    extractor._engine = _FakeEngine(
        captured,
        [
            {"call_sequence": 2, "dte_updated": "2025-01-11T14:42:10.456000+00:00"},
            {"call_sequence": 3, "dte_updated": "2025-01-11T14:42:10.456000+00:00"},
        ],
    )

    batches = list(
        extractor.extract(
            _composite_incremental_metadata(),
            cursor={
                "dte_updated": "2025-01-11T14:42:10.456000+00:00",
                "call_sequence": "2",
            },
        )
    )

    assert len(batches) == 1
    assert [record["call_sequence"] for record in batches[0].records] == [2, 3]
    assert batches[0].cursor == {
        "dte_updated": "2025-01-11T14:42:10.456000+00:00",
        "call_sequence": "3",
    }


def test_extract_incremental_empty_run_re_emits_cursor(extractor: SqlServerExtractor):
    cursor = {"dte_updated": "2025-01-12T00:00:00+00:00"}
    extractor._engine = _FakeEngine({}, [])

    batches = list(extractor.extract(_incremental_metadata(), cursor=cursor))

    assert len(batches) == 1
    assert batches[0].records == []
    assert batches[0].cursor == cursor


def test_extract_serializes_datetime_values(sqlite_engine, extractor: SqlServerExtractor):
    extractor._engine = _FakeEngine(
        {},
        [
            {
                "call_sequence": 4,
                "queue_key": "QUEUE-C",
                "dte_updated": datetime(2025, 1, 12, 10, 30, tzinfo=timezone.utc),
                "event_type": "CONNECT",
            }
        ],
    )

    batches = list(
        extractor.extract(
            _incremental_metadata(),
            cursor={"dte_updated": "2025-01-12T00:00:00+00:00"},
        )
    )

    assert batches[0].records[0]["dte_updated"] == "2025-01-12T10:30:00+00:00"


def test_engine_factory_reads_single_json_secret(mock_secret_provider: MockSecretProvider, monkeypatch: pytest.MonkeyPatch):
    extractor = SqlServerExtractor(secret_provider=mock_secret_provider)
    captured: dict[str, object] = {}

    def fake_create_engine(url: str, pool_pre_ping: bool):
        captured["url"] = url
        captured["pool_pre_ping"] = pool_pre_ping
        return object()

    monkeypatch.setattr(sql_server_extractor_module, "create_engine", fake_create_engine)

    engine = extractor._get_or_build_engine(
        SqlServerExtractorConfig(
            source_secret_key="puzzel-mssql-credentials",
            source_schema="dbo",
            source_table="call_events",
        )
    )

    assert engine is extractor._engine
    assert captured["pool_pre_ping"] is True
    assert captured["url"] == "mssql+pyodbc://sa:YourStrong!Passw0rd@localhost:1433/ConnectCallData_26295?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes&Encrypt=no"


def test_engine_factory_supports_source_secret_key(mock_secret_provider: MockSecretProvider, monkeypatch: pytest.MonkeyPatch):
    extractor = SqlServerExtractor(secret_provider=mock_secret_provider)
    captured: dict[str, str] = {}

    monkeypatch.setattr(
        sql_server_extractor_module,
        "create_engine",
        lambda url, pool_pre_ping: captured.update({"url": url}) or object(),
    )

    extractor._get_or_build_engine(
        SqlServerExtractorConfig(
            source_secret_key="custom-puzzel-secret",
            source_schema="dbo",
            source_table="call_events",
        )
    )

    assert "AnotherStrong%21Passw0rd" not in captured["url"]
    assert captured["url"].startswith("mssql+pyodbc://sa:AnotherStrong!Passw0rd@localhost:1433/")


def test_engine_factory_reuses_first_built_engine(
    mock_secret_provider: MockSecretProvider,
    monkeypatch: pytest.MonkeyPatch,
):
    extractor = SqlServerExtractor(secret_provider=mock_secret_provider)
    captured_calls: list[dict[str, object]] = []

    def _fake_create_engine(url, **kwargs):
        captured_calls.append({"url": url, "kwargs": kwargs})

        class _DummyEngine:
            pass

        return _DummyEngine()

    monkeypatch.setattr(sql_server_extractor_module, "create_engine", _fake_create_engine)

    extractor._get_or_build_engine(
        SqlServerExtractorConfig(
            source_secret_key="puzzel-mssql-credentials",
            source_schema="dbo",
            source_table="call_events",
        )
    )
    extractor._get_or_build_engine(
        SqlServerExtractorConfig(
            source_secret_key="puzzel-mssql-credentials",
            source_schema="dbo",
            source_table="call_events",
        )
    )

    assert len(captured_calls) == 1
    assert captured_calls[0]["kwargs"] == {"pool_pre_ping": True}


def test_extract_uses_qualified_table_name_in_query(
    mock_secret_provider: MockSecretProvider,
    monkeypatch: pytest.MonkeyPatch,
):
    extractor = SqlServerExtractor(secret_provider=mock_secret_provider)
    captured: dict[str, str] = {}

    monkeypatch.setattr(extractor, "_get_or_build_engine", lambda config: _FakeEngine(captured, []))

    list(extractor.extract(_full_refresh_metadata(source_schema="dbo")))

    assert captured["query"] == "SELECT * FROM [dbo].[call_events]"


def test_extract_uses_incremental_query_string(
    mock_secret_provider: MockSecretProvider,
    monkeypatch: pytest.MonkeyPatch,
):
    extractor = SqlServerExtractor(secret_provider=mock_secret_provider)
    captured: dict[str, str] = {}

    monkeypatch.setattr(extractor, "_get_or_build_engine", lambda config: _FakeEngine(captured, []))

    list(
        extractor.extract(
            _incremental_metadata(source_schema="dbo"),
            cursor={"dte_updated": "2025-01-12T00:00:00+00:00"},
        )
    )

    assert captured["query"] == ("SELECT * FROM [dbo].[call_events] WHERE ([dte_updated] >= CONVERT(datetime2(6), '2025-01-12T00:00:00.000000+00:00', 126)) ORDER BY [dte_updated] ASC")


def test_extract_uses_composite_incremental_query_string(
    mock_secret_provider: MockSecretProvider,
    monkeypatch: pytest.MonkeyPatch,
):
    extractor = SqlServerExtractor(secret_provider=mock_secret_provider)
    captured: dict[str, str] = {}

    monkeypatch.setattr(extractor, "_get_or_build_engine", lambda config: _FakeEngine(captured, []))

    list(
        extractor.extract(
            _composite_incremental_metadata(source_schema="dbo"),
            cursor={
                "dte_updated": "2025-01-12T00:00:00+00:00",
                "call_sequence": "5",
            },
        )
    )

    assert captured["query"] == (
        "SELECT * FROM [dbo].[call_events] WHERE "
        "([dte_updated] > CONVERT(datetime2(6), '2025-01-12T00:00:00.000000+00:00', 126)) OR "
        "([dte_updated] = CONVERT(datetime2(6), '2025-01-12T00:00:00.000000+00:00', 126) AND [call_sequence] >= 5) "
        "ORDER BY [dte_updated] ASC, [call_sequence] ASC"
    )
