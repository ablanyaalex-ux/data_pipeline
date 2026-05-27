import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from importlib.resources import files
from pathlib import Path

import tag_data_engineering.transformations
from tag_data_engineering.connectors.lakehouse_connector import LakehouseConnector
from tag_data_engineering.metadata_schema import METADATA_TABLES
from tag_data_engineering.metadata_schema import PIPELINE_GROUP_RUNS_SCHEMA
from tag_data_engineering.metadata_schema import MetadataTableConfig


@dataclass(frozen=True)
class PipelineGroupConfig:
    pipeline_group: str
    frequency_hours: int
    enabled: bool = True


class SetupRunner:
    def __init__(self, connector: LakehouseConnector, transformations_path: Path | None = None):
        self.connector = connector
        self.transformations_path = Path(str(files(tag_data_engineering.transformations))) if transformations_path is None else transformations_path

    def run(self, entity: str = "metadata", pipeline_group: str = "", orchestrator_run_id: str = "") -> str | None:
        if entity == "metadata":
            self._setup_metadata_tables()
            return self._build_setup_output()
        if entity == "pipeline_group_success":
            if not pipeline_group:
                raise ValueError("pipeline_group is required for setup/pipeline_group_success")
            if not orchestrator_run_id:
                raise ValueError("orchestrator_run_id is required for setup/pipeline_group_success")
            self.record_pipeline_group_success(pipeline_group=pipeline_group, orchestrator_run_id=orchestrator_run_id)
            return None
        raise ValueError(f"Unknown setup entity: {entity}")

    def _setup_metadata_tables(self) -> None:
        print("Setting up metadata tables from Python schema definitions...")
        self.connector.create_schema("_metadata")
        print(f"Found {len(METADATA_TABLES)} table definitions")
        for table_config in METADATA_TABLES:
            self._create_table_if_not_exists(table_config)
        print("Metadata tables ready")

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

    def _build_setup_output(self) -> str:
        orchestrator_run_id = uuid.uuid4().hex
        due_groups = self.get_due_pipeline_groups(now=datetime.now(timezone.utc))
        return json.dumps(
            {
                "orchestrator_run_id": orchestrator_run_id,
                "due_groups": due_groups,
            },
            separators=(",", ":"),
        )

    def get_due_pipeline_groups(self, now: datetime | None = None) -> list[str]:
        now = now or datetime.now(timezone.utc)
        last_success = self._load_last_success_by_group()
        due_groups: list[str] = []
        for config in self.load_pipeline_group_configs():
            if not config.enabled:
                continue
            if config.frequency_hours == 0:
                due_groups.append(config.pipeline_group)
                continue
            completed_at = last_success.get(config.pipeline_group)
            if completed_at is None:
                due_groups.append(config.pipeline_group)
                continue
            if completed_at.tzinfo is None:
                completed_at = completed_at.replace(tzinfo=timezone.utc)
            elapsed_hours = (now - completed_at).total_seconds() / 3600
            if elapsed_hours >= config.frequency_hours:
                due_groups.append(config.pipeline_group)
        return due_groups

    def load_pipeline_group_configs(self) -> list[PipelineGroupConfig]:
        config_file = self.transformations_path / "_pipeline_groups" / "metadata.json"
        if not config_file.exists():
            return []
        data = json.loads(config_file.read_text())
        groups = data.get("groups", data if isinstance(data, list) else [])
        return [
            PipelineGroupConfig(
                pipeline_group=group["pipeline_group"],
                frequency_hours=int(group["frequency_hours"]),
                enabled=bool(group.get("enabled", True)),
            )
            for group in groups
        ]

    def _load_last_success_by_group(self) -> dict[str, datetime]:
        if not self.connector.table_exists(schema="_metadata", table="pipeline_group_runs"):
            return {}
        rows = self.connector.run_sql(
            """
            SELECT pipeline_group, MAX(completed_at) AS completed_at
            FROM _metadata.pipeline_group_runs
            WHERE status = 'completed'
            GROUP BY pipeline_group
            """
        ).collect()
        result: dict[str, datetime] = {}
        for row in rows:
            pipeline_group = row.pipeline_group
            completed_at = row.completed_at
            if completed_at is not None:
                result[pipeline_group] = completed_at
        return result

    def record_pipeline_group_success(self, pipeline_group: str, orchestrator_run_id: str) -> None:
        now = datetime.now(timezone.utc)
        self.connector.write_data_to_table(
            data=[
                (
                    pipeline_group,
                    orchestrator_run_id,
                    now,
                    now,
                    "completed",
                    None,
                )
            ],
            schema=PIPELINE_GROUP_RUNS_SCHEMA,
            table="_metadata.pipeline_group_runs",
            mode="append",
            partition_by=["pipeline_group"],
        )
