import json
from datetime import datetime
from datetime import timedelta
from datetime import timezone

import pytest

from tag_data_engineering.metadata_schema import METADATA_TABLES
from tag_data_engineering.runners.setup_runner import SetupRunner
from tests.conftest import MockDataFrame
from tests.conftest import make_mock_connector
from tests.conftest import make_row


@pytest.fixture
def connector():
    return make_mock_connector()


@pytest.fixture
def setup_runner(connector, tmp_path) -> SetupRunner:
    groups_dir = tmp_path / "_pipeline_groups"
    groups_dir.mkdir(parents=True, exist_ok=True)
    (groups_dir / "metadata.json").write_text(
        json.dumps(
            {
                "groups": [
                    {"pipeline_group": "cms", "frequency_hours": 0, "enabled": True},
                    {"pipeline_group": "weekly_blob", "frequency_hours": 168, "enabled": True},
                    {"pipeline_group": "disabled_group", "frequency_hours": 0, "enabled": False},
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

    def test_setup_metadata_returns_due_groups_json(self, setup_runner, connector):
        connector.table_exists.side_effect = lambda schema, table: table == "pipeline_group_runs"
        connector.run_sql.return_value = MockDataFrame(
            rows=[
                make_row(
                    pipeline_group="weekly_blob",
                    completed_at=datetime.now(timezone.utc) - timedelta(days=8),
                )
            ]
        )

        output = setup_runner.run(entity="metadata")

        assert output is not None
        result = json.loads(output)
        assert "orchestrator_run_id" in result
        assert set(result["due_groups"]) == {"cms", "weekly_blob"}
        assert "disabled_group" not in result["due_groups"]

    def test_setup_pipeline_group_success_writes_run(self, setup_runner, connector):
        setup_runner.run(
            entity="pipeline_group_success",
            pipeline_group="weekly_blob",
            orchestrator_run_id="orch-123",
        )

        write_call = connector.write_data_to_table.call_args
        assert write_call.kwargs["table"] == "_metadata.pipeline_group_runs"
        assert write_call.kwargs["mode"] == "append"
        assert write_call.kwargs["partition_by"] == ["pipeline_group"]
        assert write_call.kwargs["data"][0][0] == "weekly_blob"
        assert write_call.kwargs["data"][0][1] == "orch-123"

    def test_setup_pipeline_group_success_requires_parameters(self, setup_runner):
        with pytest.raises(ValueError, match="pipeline_group is required"):
            setup_runner.run(entity="pipeline_group_success", orchestrator_run_id="orch-123")
        with pytest.raises(ValueError, match="orchestrator_run_id is required"):
            setup_runner.run(entity="pipeline_group_success", pipeline_group="weekly_blob")
