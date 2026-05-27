import pytest

from tag_data_engineering.metadata_schema import METADATA_TABLES
from tag_data_engineering.runners.setup_runner import SetupRunner
from tests.conftest import make_mock_connector


@pytest.fixture
def connector():
    return make_mock_connector()


@pytest.fixture
def setup_runner(connector) -> SetupRunner:
    return SetupRunner(connector=connector)


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
