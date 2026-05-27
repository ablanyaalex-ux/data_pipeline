import json
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from unittest.mock import Mock

import pytest

from tag_data_engineering.metadata_schema import METADATA_TABLES
from tag_data_engineering.runners.setup_runner import SetupRunner
from tests.conftest import make_mock_connector
from tests.conftest import make_row


@pytest.fixture
def connector():
    return make_mock_connector()


@pytest.fixture
def setup_runner(connector) -> SetupRunner:
    return SetupRunner(connector=connector)


@pytest.fixture
def configured_setup_runner(tmp_path, connector) -> SetupRunner:
    config_dir = tmp_path / "_pipeline_groups"
    config_dir.mkdir()
    (config_dir / "metadata.json").write_text(
        json.dumps(
            {
                "groups": [
                    {"pipeline_group": "cms", "frequency_hours": 0, "enabled": True},
                    {"pipeline_group": "weekly_blob", "frequency_hours": 168, "enabled": True},
                    {"pipeline_group": "disabled", "frequency_hours": 0, "enabled": False},
                ]
            }
        )
    )
    return SetupRunner(connector=connector, transformations_path=tmp_path)


class TestSetupRunner:
    def test_creates_metadata_schema(self, setup_runner, connector):
        setup_runner.run(entity="metadata")
        connector.create_schema.assert_called_with("_metadata")

    def test_setup_is_idempotent(self, setup_runner, connector):
        setup_runner.run(entity="metadata")
        setup_runner.run(entity="metadata")
        assert connector.create_schema.call_count == 2

    def test_creates_all_metadata_tables(self, setup_runner, connector):
        setup_runner.run(entity="metadata")
        written_tables = [c.kwargs["table"] for c in connector.write_data_to_table.call_args_list]
        for table_config in METADATA_TABLES:
            assert f"_metadata.{table_config.name}" in written_tables

    def test_new_table_uses_ignore_mode(self, setup_runner, connector):
        connector.table_exists.return_value = False
        setup_runner.run(entity="metadata")
        for table_config in METADATA_TABLES:
            connector.write_data_to_table.assert_any_call(
                data=[],
                schema=table_config.schema_definition,
                table=f"_metadata.{table_config.name}",
                mode="ignore",
                partition_by=table_config.partition_by,
            )

    def test_existing_table_uses_merge_schema(self, setup_runner, connector):
        connector.table_exists.return_value = True
        setup_runner.run(entity="metadata")
        for table_config in METADATA_TABLES:
            connector.write_data_to_table.assert_any_call(
                data=[],
                schema=table_config.schema_definition,
                table=f"_metadata.{table_config.name}",
                mode="append",
                options={"mergeSchema": "true"},
            )

    def test_unknown_setup_entity_raises_error(self, setup_runner):
        with pytest.raises(ValueError, match="Unknown setup entity: invalid"):
            setup_runner.run(entity="invalid")

    def test_frequency_zero_runs_every_time(self, configured_setup_runner, connector):
        connector.table_exists.return_value = True
        connector.run_sql.return_value = Mock(
            collect=Mock(
                return_value=[
                    make_row(pipeline_group="cms", completed_at=datetime.now(timezone.utc)),
                    make_row(pipeline_group="weekly_blob", completed_at=datetime.now(timezone.utc)),
                ]
            )
        )

        due_groups = configured_setup_runner.get_due_pipeline_groups(now=datetime.now(timezone.utc))

        assert "cms" in due_groups

    def test_weekly_group_runs_when_last_success_is_old(self, configured_setup_runner, connector):
        now = datetime(2026, 5, 27, tzinfo=timezone.utc)
        connector.table_exists.return_value = True
        connector.run_sql.return_value = Mock(collect=Mock(return_value=[make_row(pipeline_group="weekly_blob", completed_at=now - timedelta(hours=169))]))

        due_groups = configured_setup_runner.get_due_pipeline_groups(now=now)

        assert "weekly_blob" in due_groups

    def test_group_with_no_success_runs_immediately(self, configured_setup_runner, connector):
        connector.table_exists.return_value = True
        connector.run_sql.return_value = Mock(collect=Mock(return_value=[]))

        due_groups = configured_setup_runner.get_due_pipeline_groups(now=datetime(2026, 5, 27, tzinfo=timezone.utc))

        assert "weekly_blob" in due_groups

    def test_disabled_group_never_runs(self, configured_setup_runner, connector):
        connector.table_exists.return_value = False

        due_groups = configured_setup_runner.get_due_pipeline_groups(now=datetime(2026, 5, 27, tzinfo=timezone.utc))

        assert "disabled" not in due_groups

    def test_setup_metadata_returns_due_groups_json(self, configured_setup_runner, connector):
        connector.table_exists.return_value = False

        result = configured_setup_runner.run(entity="metadata")

        payload = json.loads(result)
        assert payload["orchestrator_run_id"]
        assert "cms" in payload["due_groups"]
        assert "weekly_blob" in payload["due_groups"]

    def test_records_pipeline_group_success(self, setup_runner, connector):
        setup_runner.run(entity="pipeline_group_success", pipeline_group="cms", orchestrator_run_id="run-1")

        connector.write_data_to_table.assert_called_once()
        kwargs = connector.write_data_to_table.call_args.kwargs
        assert kwargs["table"] == "_metadata.pipeline_group_runs"
        assert kwargs["data"][0][0] == "cms"
        assert kwargs["data"][0][1] == "run-1"
        assert kwargs["data"][0][4] == "completed"
