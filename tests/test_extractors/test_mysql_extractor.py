from datetime import datetime
from datetime import timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy import text

import tag_data_engineering.extractors.mysql_extractor as mysql_extractor_module
from tag_data_engineering.extractors.mysql_extractor import MySqlExtractor
from tag_data_engineering.extractors.mysql_extractor import MySqlExtractorConfig
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
        "source_secret_key": "lumin-prod-aws-popla-mysql-credentials",
        "source_database": "casedb",
        "source_table": "case_audit",
    }
    extractor_config.update(overrides)
    return ExtractionMetadata(
        entity="popla_case_audits",
        pipeline_group="other",
        extraction_mode=ExtractionMode.FULL_REFRESH,
        max_file_size_mb=10,
        output_format="jsonl",
        extractor="mysql",
        extractor_config=extractor_config,
    )


def _incremental_metadata(**overrides) -> ExtractionMetadata:
    extractor_config = {
        "source_secret_key": "lumin-prod-aws-popla-mysql-credentials",
        "source_database": "casedb",
        "source_table": "case_audit",
        "incremental": {
            "column": "timestamp",
            "column_type": "DateTime",
        },
    }
    extractor_config.update(overrides)
    return ExtractionMetadata(
        entity="popla_case_audits",
        pipeline_group="other",
        extraction_mode=ExtractionMode.INCREMENTAL,
        max_file_size_mb=10,
        output_format="jsonl",
        extractor="mysql",
        extractor_config=extractor_config,
    )


def _composite_incremental_metadata(**overrides) -> ExtractionMetadata:
    extractor_config = {
        "source_secret_key": "lumin-prod-aws-popla-mysql-credentials",
        "source_database": "casedb",
        "source_table": "case_audit",
        "incremental": {
            "columns": [
                {
                    "name": "timestamp",
                    "type": "DateTime",
                },
                {
                    "name": "id",
                    "type": "Int",
                },
            ],
        },
    }
    extractor_config.update(overrides)
    return ExtractionMetadata(
        entity="popla_case_audits",
        pipeline_group="other",
        extraction_mode=ExtractionMode.INCREMENTAL,
        max_file_size_mb=10,
        output_format="jsonl",
        extractor="mysql",
        extractor_config=extractor_config,
    )


@pytest.fixture
def sqlite_engine():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("ATTACH DATABASE ':memory:' AS casedb"))
        connection.execute(
            text("""
                CREATE TABLE casedb.case_audit (
                    id INTEGER PRIMARY KEY,
                    case_verification_code TEXT,
                    actioned_by TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    description TEXT NOT NULL,
                    event_type TEXT,
                    draft_case_id TEXT
                )
            """)
        )
        connection.execute(
            text("""
                INSERT INTO casedb.case_audit (id, case_verification_code, actioned_by, timestamp, description, event_type, draft_case_id)
                VALUES
                (1, 'ABC1234567', 'system', '2025-01-10T09:15:30.123000+00:00', 'Case created', 'CREATE', NULL),
                (2, 'ABC1234567', 'assessor01', '2025-01-11T14:42:10.456000+00:00', 'Status updated', 'STATUS_CHANGE', '550e8400-e29b-41d4-a716-446655440000'),
                (3, 'XYZ9876543', 'assessor02', '2025-01-11T14:42:10.456000+00:00', 'Further update', 'STATUS_CHANGE', NULL)
            """)
        )
    yield engine
    engine.dispose()


@pytest.fixture
def mock_secret_provider() -> MockSecretProvider:
    return MockSecretProvider(
        {
            "lumin-prod-aws-cms-mysql-credentials": '{"host":"localhost","port":"3306","username":"root","password":"root","database":"cms_prod"}',
            "lumin-prod-aws-popla-mysql-credentials": '{"host":"localhost","port":"3306","username":"root","password":"root","database":"popla_prod"}',
            "custom-popla-secret": '{"host":"localhost","port":"3306","username":"root","password":"root","database":"popla_prod"}',
        }
    )


@pytest.fixture
def extractor(sqlite_engine, mock_secret_provider: MockSecretProvider) -> MySqlExtractor:
    return MySqlExtractor(secret_provider=mock_secret_provider, engine=sqlite_engine)


def test_extract_full_refresh_requires_new_metadata_contract(extractor: MySqlExtractor):
    batches = list(extractor.extract(_full_refresh_metadata()))

    assert len(batches) == 1
    assert len(batches[0].records) == 3
    assert batches[0].records[0]["id"] == 1


def test_extract_missing_source_secret_key_fails_fast(sqlite_engine):
    extractor = MySqlExtractor(secret_provider=MockSecretProvider({}), engine=sqlite_engine)

    with pytest.raises(Exception, match="source_secret_key"):
        list(extractor.extract(_full_refresh_metadata(source_secret_key=None)))


def test_incremental_config_optional_for_full_refresh(extractor: MySqlExtractor):
    batches = list(extractor.extract(_full_refresh_metadata()))

    assert len(batches) == 1
    assert len(batches[0].records) == 3


def test_extract_incremental_applies_single_cursor_filter(extractor: MySqlExtractor):
    batches = list(
        extractor.extract(
            _incremental_metadata(),
            cursor={"timestamp": "2025-01-11T14:42:10.456000+00:00"},
        )
    )

    assert len(batches) == 1
    assert [record["id"] for record in batches[0].records] == [2, 3]
    assert batches[0].cursor == {"timestamp": "2025-01-11T14:42:10.456000+00:00"}


def test_extract_incremental_applies_composite_cursor_filter(extractor: MySqlExtractor):
    batches = list(
        extractor.extract(
            _composite_incremental_metadata(),
            cursor={
                "timestamp": "2025-01-11T14:42:10.456000+00:00",
                "id": "2",
            },
        )
    )

    assert len(batches) == 1
    assert [record["id"] for record in batches[0].records] == [2, 3]
    assert batches[0].cursor == {
        "timestamp": "2025-01-11T14:42:10.456000+00:00",
        "id": "3",
    }


def test_extract_incremental_empty_run_re_emits_cursor(extractor: MySqlExtractor):
    cursor = {"timestamp": "2025-01-12T00:00:00+00:00"}

    batches = list(extractor.extract(_incremental_metadata(), cursor=cursor))

    assert len(batches) == 1
    assert batches[0].records == []
    assert batches[0].cursor == cursor


def test_extract_serializes_datetime_values(sqlite_engine, extractor: MySqlExtractor):
    with sqlite_engine.begin() as connection:
        connection.execute(
            text("""
                INSERT INTO casedb.case_audit (id, case_verification_code, actioned_by, timestamp, description, event_type, draft_case_id)
                VALUES (:id, :code, :actioned_by, :timestamp, :description, :event_type, :draft_case_id)
            """),
            {
                "id": 4,
                "code": "LMN1111111",
                "actioned_by": "system",
                "timestamp": datetime(2025, 1, 12, 10, 30, tzinfo=timezone.utc).isoformat(),
                "description": "Serialized row",
                "event_type": "CREATE",
                "draft_case_id": None,
            },
        )

    batches = list(
        extractor.extract(
            _incremental_metadata(),
            cursor={"timestamp": "2025-01-12T00:00:00+00:00"},
        )
    )

    assert batches[0].records[0]["timestamp"] == "2025-01-12T10:30:00+00:00"


def test_engine_factory_reads_single_json_secret(mock_secret_provider: MockSecretProvider):
    extractor = MySqlExtractor(secret_provider=mock_secret_provider)

    engine = extractor._get_or_build_engine(
        MySqlExtractorConfig(
            source_secret_key="lumin-prod-aws-popla-mysql-credentials",
            source_database="popla_prod",
            source_table="case_audit",
        )
    )

    assert engine.url.host == "localhost"
    assert engine.url.port == 3306
    assert engine.url.username == "root"
    assert engine.url.password == "root"
    assert engine.url.database == "popla_prod"


def test_engine_factory_supports_source_secret_key(mock_secret_provider: MockSecretProvider):
    extractor = MySqlExtractor(secret_provider=mock_secret_provider)

    engine = extractor._get_or_build_engine(
        MySqlExtractorConfig(
            source_secret_key="custom-popla-secret",
            source_database="popla_prod",
            source_table="case_audit",
        )
    )

    assert engine.url.host == "localhost"
    assert engine.url.port == 3306
    assert engine.url.username == "root"
    assert engine.url.password == "root"
    assert engine.url.database == "popla_prod"


def test_engine_factory_supports_default_secret_key(mock_secret_provider: MockSecretProvider):
    extractor = MySqlExtractor(secret_provider=mock_secret_provider)

    engine = extractor._get_or_build_engine(
        MySqlExtractorConfig(
            source_secret_key="lumin-prod-aws-popla-mysql-credentials",
            source_database="popla_prod",
            source_table="case_audit",
        )
    )

    assert engine.url.host == "localhost"
    assert engine.url.port == 3306
    assert engine.url.username == "root"
    assert engine.url.password == "root"
    assert engine.url.database == "popla_prod"


def test_engine_factory_reuses_first_built_engine(
    mock_secret_provider: MockSecretProvider,
    monkeypatch: pytest.MonkeyPatch,
):
    extractor = MySqlExtractor(secret_provider=mock_secret_provider)
    captured_calls: list[dict[str, object]] = []

    def _fake_create_engine(url, **kwargs):
        captured_calls.append({"url": url, "kwargs": kwargs})

        class _DummyEngine:
            pass

        return _DummyEngine()

    monkeypatch.setattr(mysql_extractor_module, "create_engine", _fake_create_engine)

    extractor._get_or_build_engine(
        MySqlExtractorConfig(
            source_secret_key="lumin-prod-aws-popla-mysql-credentials",
            source_database="popla_prod",
            source_table="case_audit",
        )
    )
    extractor._get_or_build_engine(
        MySqlExtractorConfig(
            source_secret_key="lumin-prod-aws-popla-mysql-credentials",
            source_database="popla_prod",
            source_table="case_audit",
        )
    )

    assert len(captured_calls) == 1
    assert captured_calls[0]["kwargs"] == {"pool_pre_ping": True}


def test_extract_uses_qualified_table_name_in_query(
    mock_secret_provider: MockSecretProvider,
    monkeypatch: pytest.MonkeyPatch,
):
    extractor = MySqlExtractor(secret_provider=mock_secret_provider)
    captured: dict[str, str] = {}

    monkeypatch.setattr(extractor, "_get_or_build_engine", lambda config: _FakeEngine(captured, []))

    list(
        extractor.extract(
            ExtractionMetadata(
                entity="popla_case_audits",
                pipeline_group="other",
                extraction_mode=ExtractionMode.FULL_REFRESH,
                max_file_size_mb=10,
                output_format="jsonl",
                extractor="mysql",
                extractor_config={
                    "source_secret_key": "lumin-prod-aws-popla-mysql-credentials",
                    "source_database": "oso_api_production",
                    "source_table": "case_audit",
                },
            )
        )
    )

    assert captured["query"] == "SELECT * FROM `oso_api_production`.`case_audit`"


def test_extract_uses_incremental_query_string(
    mock_secret_provider: MockSecretProvider,
    monkeypatch: pytest.MonkeyPatch,
):
    extractor = MySqlExtractor(secret_provider=mock_secret_provider)
    captured: dict[str, str] = {}

    monkeypatch.setattr(extractor, "_get_or_build_engine", lambda config: _FakeEngine(captured, []))

    list(
        extractor.extract(
            _incremental_metadata(source_database="oso_api_production"),
            cursor={"timestamp": "2025-01-12T00:00:00+00:00"},
        )
    )

    assert captured["query"] == ("SELECT * FROM `oso_api_production`.`case_audit` WHERE (`timestamp` >= '2025-01-12 00:00:00+00:00') ORDER BY `timestamp` ASC")


def test_extract_uses_composite_incremental_query_string(
    mock_secret_provider: MockSecretProvider,
    monkeypatch: pytest.MonkeyPatch,
):
    extractor = MySqlExtractor(secret_provider=mock_secret_provider)
    captured: dict[str, str] = {}

    monkeypatch.setattr(extractor, "_get_or_build_engine", lambda config: _FakeEngine(captured, []))

    list(
        extractor.extract(
            _composite_incremental_metadata(source_database="oso_api_production"),
            cursor={
                "timestamp": "2025-01-12T00:00:00+00:00",
                "id": "5",
            },
        )
    )

    assert captured["query"] == ("SELECT * FROM `oso_api_production`.`case_audit` WHERE (`timestamp` > '2025-01-12 00:00:00+00:00') OR (`timestamp` = '2025-01-12 00:00:00+00:00' AND `id` >= 5) ORDER BY `timestamp` ASC, `id` ASC")
