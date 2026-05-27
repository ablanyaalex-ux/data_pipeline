#!/usr/bin/env python3
"""
Deploy a Fabric Data Pipeline that orchestrates the full medallion architecture.

This script:
1. Deploys a single Spark Job Definition (run_transformation) that handles all layers
2. Creates or updates a pipeline with activities for all layers:
   - Landing: Extract from source APIs to Files/
   - Bronze: Merge landing files to bronze tables
   - Silver: Transform bronze to silver
   - Gold: Build dimensions and facts

Execution order:
Landing → Bronze → Silver → Gold (dimensions) → Gold (facts)

All activities use the same Spark Job Definition with different arguments:
    run_transformation.py <layer> <entity>
"""

import base64
import json
import shutil
from pathlib import Path

import click
import requests
from azure.identity import DefaultAzureCredential
from Exploration.krishan.archive.spark.job_spark_deploy import build_wheel
from Exploration.krishan.archive.spark.job_spark_deploy import deploy_environment
from Exploration.krishan.archive.spark.job_spark_deploy import deploy_spark_job

from tag_data_engineering.deployment.fabric_connection import FabricConnection


BASE_URL = "https://api.fabric.microsoft.com/v1"

# Paths
SCRIPTS_PATH = Path(__file__).parent
PROJECT_PATH = SCRIPTS_PATH.parent
TRANSFORMATIONS_PATH = PROJECT_PATH / "src" / "tag_data_engineering" / "transformations"
JOBS_PATH = PROJECT_PATH / "jobs" / "spark"

# Single Spark Job Definition for all layers
SPARK_JOB_NAME = "run_transformation"
SPARK_JOB_FILE = JOBS_PATH / "run_transformation.py"


def get_entities_for_layer(layer: str) -> list[str]:
    """Get all entities for a given layer by reading the transformations folder."""
    layer_path = TRANSFORMATIONS_PATH / layer
    if not layer_path.exists():
        return []
    entities = []
    for entity_path in layer_path.iterdir():
        if entity_path.is_dir() and not entity_path.name.startswith("_"):
            entities.append(entity_path.name)
    return sorted(entities)


def get_landing_entities() -> list[str]:
    """Get all landing entities."""
    return get_entities_for_layer("landing")


def get_bronze_entities() -> list[str]:
    """Get all bronze entities."""
    return get_entities_for_layer("bronze")


def get_bronze_entity_dependencies() -> dict[str, str]:
    """Get the landing entity each bronze entity depends on.

    Returns a dict mapping bronze entity name to landing entity name.
    This is read from the bronze metadata.json files.
    """
    bronze_path = TRANSFORMATIONS_PATH / "bronze"
    if not bronze_path.exists():
        return {}

    dependencies = {}
    for entity_path in bronze_path.iterdir():
        if entity_path.is_dir() and not entity_path.name.startswith("_"):
            metadata_file = entity_path / "metadata.json"
            if metadata_file.exists():
                metadata = json.loads(metadata_file.read_text())
                # Bronze metadata has 'entity' field pointing to landing entity
                landing_entity = metadata.get("entity")
                if landing_entity:
                    dependencies[entity_path.name] = landing_entity
    return dependencies


def get_silver_entity_dependencies() -> dict[str, list[str]]:
    """Get the bronze tables each silver entity depends on.

    Returns a dict mapping silver entity name to list of bronze activity names.
    Dependencies are read from the 'dependencies' field in silver metadata.json files.
    Format in metadata: ["bronze.people", "bronze.films"] -> ["bronze_people", "bronze_films"]
    """
    silver_path = TRANSFORMATIONS_PATH / "silver"
    if not silver_path.exists():
        return {}

    dependencies = {}
    for entity_path in silver_path.iterdir():
        if entity_path.is_dir() and not entity_path.name.startswith("_"):
            metadata_file = entity_path / "metadata.json"
            if metadata_file.exists():
                metadata = json.loads(metadata_file.read_text())
                deps = metadata.get("dependencies", [])
                # Convert "bronze.people" -> "bronze_people"
                activity_deps = []
                for dep in deps:
                    if "." in dep:
                        schema, table = dep.split(".", 1)
                        activity_deps.append(f"{schema}_{table}")
                    else:
                        activity_deps.append(dep)
                dependencies[entity_path.name] = activity_deps
    return dependencies


def get_silver_entities() -> list[str]:
    """Get all silver entities."""
    return get_entities_for_layer("silver")


def get_gold_entities() -> list[str]:
    """Get all gold entities."""
    return get_entities_for_layer("gold")


def get_gold_entity_dependencies() -> dict[str, list[str]]:
    """Get the silver tables each gold entity depends on.

    Returns a dict mapping gold entity name to list of silver activity names.
    Dependencies are read from the 'dependencies' field in gold metadata.json files.
    Format in metadata: ["silver.people", "silver.films"] -> ["silver_people", "silver_films"]
    """
    gold_path = TRANSFORMATIONS_PATH / "gold"
    if not gold_path.exists():
        return {}

    dependencies = {}
    for entity_path in gold_path.iterdir():
        if entity_path.is_dir() and not entity_path.name.startswith("_"):
            metadata_file = entity_path / "metadata.json"
            if metadata_file.exists():
                metadata = json.loads(metadata_file.read_text())
                deps = metadata.get("dependencies", [])
                # Convert "silver.people" -> "silver_people"
                activity_deps = []
                for dep in deps:
                    if "." in dep:
                        schema, table = dep.split(".", 1)
                        activity_deps.append(f"{schema}_{table}")
                    else:
                        activity_deps.append(dep)
                dependencies[entity_path.name] = activity_deps
    return dependencies


def find_existing_pipeline_id(fabric_conn: FabricConnection, workspace_id: str, pipeline_name: str) -> str | None:
    """Find an existing pipeline by name."""
    headers = fabric_conn._get_api_headers()
    resp = requests.get(f"{BASE_URL}/workspaces/{workspace_id}/items?type=DataPipeline", headers=headers)
    resp.raise_for_status()
    for item in resp.json().get("value", []):
        if item["displayName"] == pipeline_name:
            print(f"Found existing pipeline: {pipeline_name} (ID: {item['id']})")
            return item["id"]
    return None


def create_pipeline(fabric_conn: FabricConnection, workspace_id: str, pipeline_name: str) -> str:
    """Create a new pipeline."""
    print(f"Creating new pipeline: {pipeline_name}")
    headers = fabric_conn._get_api_headers()
    payload = {
        "displayName": pipeline_name,
        "type": "DataPipeline",
    }
    resp = requests.post(f"{BASE_URL}/workspaces/{workspace_id}/items", headers=headers, json=payload)
    resp.raise_for_status()
    pipeline_id = resp.json()["id"]
    print(f"Created pipeline: {pipeline_id}")
    return pipeline_id


def build_pipeline_definition(
    workspace_id: str,
    job_definition_id: str,
    lakehouse_id: str,
    environment_id: str,
) -> dict:
    """
    Build the pipeline definition with activities for all medallion layers.

    All activities use the same Spark Job Definition with different arguments.

    Execution order:
    1. Landing layer - extract from APIs (all run in parallel)
    2. Bronze layer - merge landing files (depends on all landing completing)
    3. Silver layer - transform bronze (depends on all bronze completing)
    4. Gold layer - dimensions first, then facts (depends on all silver completing)
    """
    activities = []

    # Landing layer - all run in parallel
    landing_entities = get_landing_entities()
    for entity in landing_entities:
        activity_name = f"landing_{entity}"
        activity = build_activity(
            activity_name=activity_name,
            workspace_id=workspace_id,
            job_definition_id=job_definition_id,
            lakehouse_id=lakehouse_id,
            environment_id=environment_id,
            layer="landing",
            entity=entity,
            depends_on_all=None,  # Landing runs in parallel
        )
        activities.append(activity)

    # Bronze layer - each bronze entity depends on its specific landing entity
    bronze_entities = get_bronze_entities()
    bronze_dependencies = get_bronze_entity_dependencies()
    for entity in bronze_entities:
        activity_name = f"bronze_{entity}"
        # Get the specific landing entity this bronze depends on
        landing_entity = bronze_dependencies.get(entity)
        depends_on = [f"landing_{landing_entity}"] if landing_entity else None
        activity = build_activity(
            activity_name=activity_name,
            workspace_id=workspace_id,
            job_definition_id=job_definition_id,
            lakehouse_id=lakehouse_id,
            environment_id=environment_id,
            layer="bronze",
            entity=entity,
            depends_on_all=depends_on,
        )
        activities.append(activity)

    # Silver layer - depends on specific bronze tables from metadata
    silver_entities = get_silver_entities()
    silver_dependencies = get_silver_entity_dependencies()
    for entity in silver_entities:
        activity_name = f"silver_{entity}"
        # Get specific dependencies for this silver entity, or fall back to all bronze
        deps = silver_dependencies.get(entity)
        if not deps:
            # Fall back to all bronze if no dependencies specified
            deps = [f"bronze_{e}" for e in bronze_entities] if bronze_entities else None
        activity = build_activity(
            activity_name=activity_name,
            workspace_id=workspace_id,
            job_definition_id=job_definition_id,
            lakehouse_id=lakehouse_id,
            environment_id=environment_id,
            layer="silver",
            entity=entity,
            depends_on_all=deps,
        )
        activities.append(activity)

    # Gold layer - depends on specific silver tables from metadata
    gold_entities = get_gold_entities()
    gold_dependencies = get_gold_entity_dependencies()
    silver_activity_names = [f"silver_{e}" for e in silver_entities]
    for entity in gold_entities:
        activity_name = f"gold_{entity}"
        # Get specific dependencies for this gold entity, or fall back to all silver
        deps = gold_dependencies.get(entity)
        if not deps:
            # Fall back to all silver if no dependencies specified
            deps = silver_activity_names if silver_entities else None
        activity = build_activity(
            activity_name=activity_name,
            workspace_id=workspace_id,
            job_definition_id=job_definition_id,
            lakehouse_id=lakehouse_id,
            environment_id=environment_id,
            layer="gold",
            entity=entity,
            depends_on_all=deps,
        )
        activities.append(activity)

    pipeline_definition = {
        "properties": {
            "activities": activities,
        }
    }

    return pipeline_definition


def build_activity(
    activity_name: str,
    workspace_id: str,
    job_definition_id: str,
    lakehouse_id: str,
    environment_id: str,
    layer: str,
    entity: str,
    depends_on_all: list[str] | None = None,
) -> dict:
    """Build a pipeline activity for any medallion layer.

    Args:
        activity_name: Name of the activity
        workspace_id: Fabric workspace ID
        job_definition_id: Spark Job Definition ID for run_transformation
        lakehouse_id: Lakehouse ID
        environment_id: Environment ID
        layer: Layer name (landing, bronze, silver, gold)
        entity: Entity/table name
        depends_on_all: List of activity names this depends on (all must succeed)
    """
    activity = {
        "name": activity_name,
        "type": "FabricSparkJobDefinition",
        "dependsOn": [],
        "policy": {
            "timeout": "0.12:00:00",
            "retry": 0,
            "retryIntervalInSeconds": 30,
            "secureOutput": False,
            "secureInput": False,
        },
        "typeProperties": {
            "sparkJobDefinitionId": job_definition_id,
            "workspaceId": workspace_id,
            "commandLineArguments": f"{layer} {entity}",
            "defaultLakehouse": {
                "workspaceId": workspace_id,
                "artifactId": lakehouse_id,
            },
            "environment": {
                "workspaceId": workspace_id,
                "artifactId": environment_id,
            },
        },
    }

    # Handle dependencies
    if depends_on_all:
        activity["dependsOn"] = [
            {
                "activity": dep,
                "dependencyConditions": ["Succeeded"],
            }
            for dep in depends_on_all
        ]

    return activity


def update_pipeline_definition(
    fabric_conn: FabricConnection,
    workspace_id: str,
    pipeline_id: str,
    pipeline_name: str,
    pipeline_definition: dict,
) -> None:
    """Update the pipeline definition."""
    print("Updating pipeline definition...")
    headers = fabric_conn._get_api_headers()

    payload = {
        "definition": {
            "parts": [
                {
                    "path": "pipeline-content.json",
                    "payload": base64.b64encode(json.dumps(pipeline_definition).encode()).decode(),
                    "payloadType": "InlineBase64",
                },
            ],
        },
    }

    resp = requests.post(
        f"{BASE_URL}/workspaces/{workspace_id}/items/{pipeline_id}/updateDefinition",
        headers=headers,
        json=payload,
    )
    resp.raise_for_status()
    print("Pipeline definition updated successfully")


def get_spark_job_definition_id(fabric_conn: FabricConnection, workspace_id: str, job_name: str) -> str | None:
    """Get the ID of a Spark Job Definition, or None if not found."""
    try:
        return fabric_conn._get_spark_job_id_by_name(workspace_id=workspace_id, job_name=job_name)
    except RuntimeError:
        return None


def clean_build_artifacts() -> None:
    """Clean build artifacts before building wheel."""
    for dir_name in ["build", "dist"]:
        dir_path = PROJECT_PATH / dir_name
        if dir_path.exists():
            shutil.rmtree(dir_path)
    for egg_info in (PROJECT_PATH / "src").glob("*.egg-info"):
        if egg_info.is_dir():
            shutil.rmtree(egg_info)


@click.command()
@click.option("--workspace", "-w", required=True, help="Fabric workspace name")
@click.option("--pipeline-name", "-p", required=True, help="Pipeline name to create/update")
@click.option("--lakehouse", "-l", required=True, help="Lakehouse name")
@click.option("--environment", "-e", required=True, help="Environment name")
def main(workspace: str, pipeline_name: str, lakehouse: str, environment: str) -> None:
    """Deploy a Fabric Data Pipeline with Spark Job Definitions for full medallion architecture."""
    print(f"Deploying pipeline to workspace: {workspace}")
    print(f"Pipeline name: {pipeline_name}")
    print(f"Lakehouse: {lakehouse}")
    print(f"Environment: {environment}")

    # Authenticate
    print("\nAuthenticating with Azure...")
    credential = DefaultAzureCredential()
    fabric_conn = FabricConnection(credential=credential)

    # Get workspace ID
    print(f"\nFinding workspace: {workspace}")
    workspace_id = fabric_conn._get_workspace_id_by_name(workspace_name=workspace)
    print(f"Found workspace ID: {workspace_id}")

    # Get Lakehouse ID
    print(f"\nFinding lakehouse: {lakehouse}")
    lakehouse_id = fabric_conn._get_lakehouse_id_by_name(workspace_id=workspace_id, lakehouse_name=lakehouse)
    print(f"Found lakehouse ID: {lakehouse_id}")

    # Get Environment ID
    print(f"\nFinding environment: {environment}")
    environment_id = fabric_conn._get_environment_id_by_name(workspace_id=workspace_id, environment_name=environment)
    print(f"Found environment ID: {environment_id}")

    # Clean and build wheel (shared by both jobs)
    print("\n" + "=" * 80)
    print("BUILDING WHEEL")
    print("=" * 80)

    print("Cleaning build artifacts...")
    clean_build_artifacts()

    print("Building wheel...")
    wheel_file = build_wheel()
    print(f"Built wheel: {wheel_file}")

    # Deploy environment ONCE (upload wheel and publish)
    print("\n" + "=" * 80)
    print("DEPLOYING ENVIRONMENT")
    print("=" * 80)

    deploy_environment(
        fabric_conn=fabric_conn,
        workspace_id=workspace_id,
        environment_id=environment_id,
        wheel_file=wheel_file,
    )
    print(f"✅ Environment deployed: {environment}")

    # Deploy single Spark Job Definition for all layers
    print("\n" + "=" * 80)
    print("DEPLOYING SPARK JOB")
    print("=" * 80)

    if not SPARK_JOB_FILE.exists():
        raise FileNotFoundError(f"Job file not found: {SPARK_JOB_FILE}")

    job_id = deploy_spark_job(
        fabric_conn=fabric_conn,
        workspace_id=workspace_id,
        environment_id=environment_id,
        lakehouse_id=lakehouse_id,
        job_name=SPARK_JOB_NAME,
        job_file=SPARK_JOB_FILE,
    )
    print(f"✅ Spark Job deployed: {job_id}")

    # Find or create pipeline
    print("\n" + "=" * 80)
    print("DEPLOYING PIPELINE")
    print("=" * 80)

    print(f"Checking for existing pipeline: {pipeline_name}")
    pipeline_id = find_existing_pipeline_id(fabric_conn, workspace_id, pipeline_name)
    if not pipeline_id:
        pipeline_id = create_pipeline(fabric_conn, workspace_id, pipeline_name)

    # Build pipeline definition
    print("\nBuilding pipeline definition...")
    landing_entities = get_landing_entities()
    bronze_entities = get_bronze_entities()
    silver_entities = get_silver_entities()
    gold_entities = get_gold_entities()

    print(f"Landing entities ({len(landing_entities)}): {', '.join(landing_entities)}")
    print(f"Bronze entities ({len(bronze_entities)}): {', '.join(bronze_entities)}")
    print(f"Silver entities ({len(silver_entities)}): {', '.join(silver_entities)}")
    print(f"Gold entities ({len(gold_entities)}): {', '.join(gold_entities)}")

    pipeline_definition = build_pipeline_definition(
        workspace_id=workspace_id,
        job_definition_id=job_id,
        lakehouse_id=lakehouse_id,
        environment_id=environment_id,
    )
    total_activities = len(pipeline_definition["properties"]["activities"])
    print(f"Total activities: {total_activities}")

    # Update pipeline
    update_pipeline_definition(
        fabric_conn=fabric_conn,
        workspace_id=workspace_id,
        pipeline_id=pipeline_id,
        pipeline_name=pipeline_name,
        pipeline_definition=pipeline_definition,
    )

    print("\n" + "=" * 80)
    print("✅ DEPLOYMENT COMPLETE!")
    print("=" * 80)
    print(f"Spark Job: {SPARK_JOB_NAME} ({job_id})")
    print(f"Pipeline: {pipeline_name} ({pipeline_id})")
    print(f"Total Activities: {total_activities}")
    print(f"  - Landing: {len(landing_entities)}")
    print(f"  - Bronze: {len(bronze_entities)}")
    print(f"  - Silver: {len(silver_entities)}")
    print(f"  - Gold: {len(gold_entities)}")


if __name__ == "__main__":
    main()
