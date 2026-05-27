from tag_data_engineering.connectors.lakehouse_connector import LakehouseConnector
from tag_data_engineering.metadata_schema import METADATA_TABLES
from tag_data_engineering.metadata_schema import MetadataTableConfig


class SetupRunner:
    def __init__(self, connector: LakehouseConnector):
        self.connector = connector

    def run(self, entity: str = "metadata") -> None:
        if entity == "metadata":
            self._setup_metadata_tables()
        else:
            raise ValueError(f"Unknown setup entity: {entity}")

    def _setup_metadata_tables(self) -> None:
        print("Setting up metadata tables from Python schema definitions...")
        self.connector.create_schema("_metadata")
        print(f"Found {len(METADATA_TABLES)} table definitions")
        for table_config in METADATA_TABLES:
            self._create_table_if_not_exists(table_config)
        print("✅ Metadata tables ready")

    def _create_table_if_not_exists(self, config: MetadataTableConfig) -> None:
        schema = config.schema_definition
        table_exists = self.connector.table_exists(schema="_metadata", table=config.name)
        if not table_exists:
            self.connector.write_data_to_table(
                data=[],
                schema=schema,
                table=f"_metadata.{config.name}",
                mode="ignore",
                partition_by=config.partition_by,
            )
        else:
            self.connector.write_data_to_table(
                data=[],
                schema=schema,
                table=f"_metadata.{config.name}",
                mode="append",
                options={"mergeSchema": "true"},
            )
        print(f"  _metadata.{config.name}: ready")
