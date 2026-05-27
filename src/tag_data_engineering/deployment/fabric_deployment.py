import json
import time
from pathlib import Path

from tag_data_engineering.deployment.fabric_connection import FabricConnection
from tag_data_engineering.deployment.fabric_serialization import serialize_copyjob_to_fabric
from tag_data_engineering.deployment.fabric_serialization import serialize_pipeline_to_fabric
from tag_data_engineering.extractors.copyjob_extractor import CopyJobExtractorConfig
from tag_data_engineering.models import ExtractionMetadata
from tag_data_engineering.pipeline.models import Layer
from tag_data_engineering.pipeline.models import PipelineActivity
from tag_data_engineering.pipeline.models import PipelineDefinition


# Path to notebook templates
_NOTEBOOK_TEMPLATES_PATH = Path(__file__).parent.parent.parent.parent / "jobs" / "notebook"


def deploy_fabric_pipeline(
    fabric_conn: FabricConnection,
    workspace_id: str,
    notebook_id: str,
    lakehouse_id: str,
    pipeline: PipelineDefinition,
    copyjob_ids: dict[str, str] | None = None,
    schedule_cron: str | None = None,
) -> str:
    fabric_json = serialize_pipeline_to_fabric(
        pipeline=pipeline,
        workspace_id=workspace_id,
        notebook_id=notebook_id,
        lakehouse_id=lakehouse_id,
        fabric_conn=fabric_conn,
        copyjob_ids=copyjob_ids,
    )
    pipeline_id = fabric_conn.find_pipeline(workspace_id, pipeline.name)
    if not pipeline_id:
        pipeline_id = fabric_conn.create_pipeline(workspace_id, pipeline.name)
    schedule_config = None
    if schedule_cron:
        schedule_config = fabric_conn.build_schedule_config(
            schedule_cron=schedule_cron,
            timezone="GMT Standard Time",
        )
    fabric_conn.update_pipeline_definition(
        workspace_id,
        pipeline_id,
        fabric_json,
        schedule_config=schedule_config,
    )
    return pipeline_id


def deploy_fabric_copyjob(
    fabric_conn: FabricConnection,
    workspace_id: str,
    lakehouse_id: str,
    activity: PipelineActivity,
) -> str:
    if activity.layer != Layer.LANDING_COPYJOB:
        raise ValueError(f"Activity {activity.name} is not a Copy Job activity")
    if not isinstance(activity.metadata, ExtractionMetadata):
        raise ValueError(f"Expected ExtractionMetadata for Copy Job activity {activity.name}")
    if activity.metadata.extractor != "copy_job":
        raise ValueError(f"Expected ExtractionMetadata.extractor == copy_job for Copy Job activity {activity.name}")
    config = CopyJobExtractorConfig.model_validate(activity.metadata.extractor_config)
    definition = serialize_copyjob_to_fabric(
        config=config,
        workspace_id=workspace_id,
        lakehouse_id=lakehouse_id,
        entity_name=activity.entity,
        fabric_conn=fabric_conn,
    )
    existing = fabric_conn.find_copyjob(workspace_id, activity.name)
    if existing:
        fabric_conn.update_copyjob(
            workspace_id=workspace_id,
            copyjob_id=existing["id"],
            copyjob_name=activity.name,
            copyjob_definition=definition,
        )
        return existing["id"]
    copyjob_id = fabric_conn.create_copyjob(
        workspace_id=workspace_id,
        copyjob_name=activity.name,
        copyjob_definition=definition,
    )
    time.sleep(2)  # Give Fabric a moment
    return copyjob_id


def deploy_fabric_notebook(
    fabric_conn: FabricConnection,
    workspace_id: str,
    lakehouse_id: str,
    lakehouse_name: str,
    environment_id: str,
    notebook_name: str,
    key_vault_url: str,
    sql_endpoint_id: str = "",
) -> str:
    template_path = _NOTEBOOK_TEMPLATES_PATH / f"{notebook_name}.ipynb"
    if not template_path.exists():
        raise FileNotFoundError(f"Notebook template not found: {template_path}")
    with open(template_path) as f:
        notebook_template = json.load(f)
    notebook_json = json.dumps(notebook_template)
    notebook_json = notebook_json.replace("{{LAKEHOUSE_ID}}", lakehouse_id)
    notebook_json = notebook_json.replace("{{LAKEHOUSE_NAME}}", lakehouse_name)
    notebook_json = notebook_json.replace("{{WORKSPACE_ID}}", workspace_id)
    notebook_json = notebook_json.replace("{{ENVIRONMENT_ID}}", environment_id)
    notebook_json = notebook_json.replace("{{KEY_VAULT_URL}}", key_vault_url)
    notebook_json = notebook_json.replace("{{SQL_ENDPOINT_ID}}", sql_endpoint_id)
    notebook_content = json.loads(notebook_json)
    notebook_id = fabric_conn.find_notebook(workspace_id, notebook_name)
    if not notebook_id:
        notebook_id = fabric_conn.create_notebook(workspace_id, notebook_name)
        time.sleep(3)  # Wait for notebook to be ready
    fabric_conn.update_notebook_definition(
        workspace_id=workspace_id,
        notebook_id=notebook_id,
        notebook_content=notebook_content,
    )
    return notebook_id
