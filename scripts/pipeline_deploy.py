#!/usr/bin/env python3
"""Deploy Fabric Data Pipelines using sub-pipelines for the full medallion architecture.

This script:
1. Deploys a Notebook (run_transformation) that handles all layers
2. Publishes the wheel to an Environment (for High Concurrency support)
3. Deploys Copy Jobs for landing entities that use copy_job extractor
4. Deploys sub-pipelines grouped by layer and source (pipeline_group):
   - landing_{group}, bronze_{group}, silver_{group}, gold_all
5. Deploys an orchestrator pipeline that invokes sub-pipelines:
   - setup_metadata → invoke landing/bronze/silver chains per group (parallel) → invoke gold

Sub-pipelines keep each pipeline under Fabric's 80-activity limit.

WHY WE USE ENVIRONMENTS INSTEAD OF PIP INSTALL:
- %pip install is NOT supported in High Concurrency mode (the fast warm pools)
- %pip install is disabled by default in pipeline runs
- Even if enabled via _inlineInstallationEnabled, it still blocks High Concurrency
- Environment approach: publish wheel once (5-15 min), then all runs use it instantly
- This is Microsoft's recommended approach for production pipelines

Benefits of Notebooks over Spark Job Definitions:
- Can use High Concurrency sessions (warm pools) - requires Environment
- Faster startup time (~30s vs ~5 minutes)
- Better for development iteration
"""

import os

import click
from azure.identity import ClientSecretCredential
from azure.identity import DefaultAzureCredential

from tag_data_engineering.deployment.build_utils import build_wheel
from tag_data_engineering.deployment.build_utils import clean_build_artifacts
from tag_data_engineering.deployment.fabric_connection import FabricConnection
from tag_data_engineering.deployment.fabric_deployment import deploy_fabric_copyjob
from tag_data_engineering.deployment.fabric_deployment import deploy_fabric_notebook
from tag_data_engineering.deployment.fabric_deployment import deploy_fabric_pipeline
from tag_data_engineering.pipeline.models import Layer
from tag_data_engineering.pipeline.pipeline_discoverer import PipelineDiscoverer


@click.command()
@click.option("--workspace", "-w", required=True, help="Fabric workspace name")
@click.option("--pipeline-name", "-p", required=True, help="Pipeline name to create/update")
@click.option("--lakehouse", "-l", required=True, help="Lakehouse name")
@click.option("--environment", "-e", required=True, help="Environment name (wheel is installed here)")
@click.option("--key-vault-url", "-k", required=True, help="Azure Key Vault URL (e.g., 'https://my-vault.vault.azure.net/')")
@click.option("--notebook-name", "-n", default="run_transformation", help="Notebook name (default: run_transformation)")
@click.option("--update-env/--no-update-env", default=True, help="Update the environment with the new wheel (default: True)")
@click.option("--dry-run", is_flag=True, default=False, help="Print pipeline definition without deploying")
@click.option("--schedule", "-s", default=None, help="Create a schedule using cron syntax (e.g., '0 6 * * *' for 6am daily)")
def main(
    workspace: str,
    pipeline_name: str,
    lakehouse: str,
    environment: str,
    key_vault_url: str,
    notebook_name: str,
    update_env: bool,
    dry_run: bool,
    schedule: str | None,
) -> None:
    print("Building sub-pipeline definitions...")
    discoverer = PipelineDiscoverer()
    subpipelines = discoverer.build_subpipelines(base_name=pipeline_name)

    # Dry-run mode: print all sub-pipelines and orchestrator, then exit
    if dry_run:
        print("\n" + "=" * 80)
        print("DRY RUN - Sub-Pipeline Definitions")
        print("=" * 80)
        total_activities = 0
        for sub_def in subpipelines.values():
            count = len(sub_def.activities)
            total_activities += count
            print(f"\n📦 {sub_def.name} ({count} activities)")
            print("-" * 40)
            for activity in sub_def.activities:
                deps = activity.dependencies if activity.dependencies else ["(none)"]
                print(f"  {activity.name}")
                print(f"    → depends on: {', '.join(deps)}")

        # Show orchestrator with placeholder IDs
        for key, sub_def in subpipelines.items():
            sub_def.deployed_id = f"<{key}_id>"
        orchestrator_def = discoverer.build_orchestrator(
            name=f"{pipeline_name}_orchestrator",
            subpipelines=subpipelines,
        )
        orchestrator_count = len(orchestrator_def.activities)
        print(f"\n🎯 {orchestrator_def.name} ({orchestrator_count} activities)")
        print("-" * 40)
        for activity in orchestrator_def.activities:
            deps = activity.dependencies if activity.dependencies else ["(none)"]
            print(f"  {activity.name}")
            print(f"    → depends on: {', '.join(deps)}")

        print(f"\nTotal: {len(subpipelines)} sub-pipelines + 1 orchestrator = {len(subpipelines) + 1} pipelines")
        print(f"Total activities across sub-pipelines: {total_activities}")
        print(f"Orchestrator activities: {orchestrator_count}")
        print(f"Max activities in a single pipeline: {max(len(s.activities) for s in subpipelines.values())}")

        print("\n" + "=" * 80)
        print("DRY RUN COMPLETE - No changes made")
        print("=" * 80)
        return

    print("=" * 80)
    print("NOTEBOOK PIPELINE DEPLOYMENT")
    print("=" * 80)
    print(f"Workspace: {workspace}")
    print(f"Pipeline name: {pipeline_name}")
    print(f"Lakehouse: {lakehouse}")
    print(f"Environment: {environment}")
    print(f"Notebook: {notebook_name}")
    print()

    # Authenticate
    print("Authenticating with Azure...")

    # Try to authenticate as service principal first
    tenant_id = os.getenv("APP_TENANT_ID")
    client_id = os.getenv("APP_ID")
    client_secret = os.getenv("APP_CLIENT_SECRET")

    if tenant_id and client_id and client_secret:
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )
        print("✅ Authenticated as service principal (APP_ID)")
    else:
        credential = DefaultAzureCredential()
        print("⚠️  Authenticated using default credentials (your personal identity)")

    fabric_conn = FabricConnection(credential=credential)

    # Get workspace ID
    print(f"Finding workspace: {workspace}")
    workspace_id = fabric_conn._get_workspace_id_by_name(workspace_name=workspace)
    print(f"Found workspace ID: {workspace_id}")

    # Get Lakehouse ID
    print(f"Finding lakehouse: {lakehouse}")
    lakehouse_id = fabric_conn._get_lakehouse_id_by_name(workspace_id=workspace_id, lakehouse_name=lakehouse)
    print(f"Found lakehouse ID: {lakehouse_id}")

    # Get SQL Endpoint ID
    print(f"Finding SQL endpoint for lakehouse: {lakehouse}")
    sql_endpoint_id = fabric_conn._get_sql_endpoint_id_by_lakehouse_name(workspace_id=workspace_id, lakehouse_name=lakehouse)
    print(f"Found SQL endpoint ID: {sql_endpoint_id}")

    # Get Environment ID
    print(f"Finding environment: {environment}")
    environment_id = fabric_conn.find_environment(workspace_id=workspace_id, environment_name=environment)

    # Clean and build wheel
    print("\n" + "=" * 80)
    print("BUILDING WHEEL")
    print("=" * 80)
    clean_build_artifacts()
    wheel_file = build_wheel()

    # Deploy wheel to Environment
    fabric_conn.deploy_wheel_to_environment(
        workspace_id=workspace_id,
        environment_id=environment_id,
        wheel_file=wheel_file,
        force=update_env,
    )

    # Deploy notebook (with environment attached)
    print("\n" + "=" * 80)
    print("DEPLOYING NOTEBOOK")
    print("=" * 80)
    notebook_id = deploy_fabric_notebook(
        fabric_conn=fabric_conn,
        workspace_id=workspace_id,
        lakehouse_id=lakehouse_id,
        lakehouse_name=lakehouse,
        environment_id=environment_id,
        notebook_name=notebook_name,
        key_vault_url=key_vault_url,
        sql_endpoint_id=sql_endpoint_id,
    )
    print(f"✅ Notebook deployed: {notebook_name} ({notebook_id})")

    # Deploy Copy Jobs if any and collect their IDs
    copyjob_ids: dict[str, str] = {}
    all_copyjob_activities = [a for sub_def in subpipelines.values() for a in sub_def.activities if a.layer == Layer.LANDING_COPYJOB]
    if all_copyjob_activities:
        print("\n" + "=" * 80)
        print("DEPLOYING COPY JOBS")
        print("=" * 80)
        for activity in all_copyjob_activities:
            copyjob_id = deploy_fabric_copyjob(
                fabric_conn=fabric_conn,
                workspace_id=workspace_id,
                lakehouse_id=lakehouse_id,
                activity=activity,
            )
            copyjob_ids[activity.name] = copyjob_id

    # Deploy sub-pipelines and set their deployed IDs
    print("\n" + "=" * 80)
    print("DEPLOYING SUB-PIPELINES")
    print("=" * 80)
    for sub_def in subpipelines.values():
        print(f"Deploying sub-pipeline: {sub_def.name} ({len(sub_def.activities)} activities)")
        # Only pass copyjob_ids for sub-pipelines that have copy job activities
        sub_copyjob_ids = {a.name: copyjob_ids[a.name] for a in sub_def.activities if a.layer == Layer.LANDING_COPYJOB and a.name in copyjob_ids} or None
        sub_def.deployed_id = deploy_fabric_pipeline(
            fabric_conn=fabric_conn,
            workspace_id=workspace_id,
            notebook_id=notebook_id,
            lakehouse_id=lakehouse_id,
            pipeline=sub_def,
            copyjob_ids=sub_copyjob_ids,
        )
        print(f"  ✅ {sub_def.name} ({sub_def.deployed_id})")

    # Build and deploy orchestrator
    print("\n" + "=" * 80)
    print("DEPLOYING ORCHESTRATOR")
    print("=" * 80)
    orchestrator_name = f"{pipeline_name}_orchestrator"
    orchestrator_def = discoverer.build_orchestrator(
        name=orchestrator_name,
        subpipelines=subpipelines,
    )
    print(f"Deploying orchestrator: {orchestrator_name} ({len(orchestrator_def.activities)} activities)")
    orchestrator_id = deploy_fabric_pipeline(
        fabric_conn=fabric_conn,
        workspace_id=workspace_id,
        notebook_id=notebook_id,
        lakehouse_id=lakehouse_id,
        pipeline=orchestrator_def,
        schedule_cron=schedule,
    )
    print(f"  ✅ {orchestrator_name} ({orchestrator_id})")

    # Print summary
    print("\n" + "=" * 80)
    print("✅ DEPLOYMENT COMPLETE!")
    print("=" * 80)
    print(f"Schedule: {schedule}")
    print(f"Notebook: {notebook_name} ({notebook_id})")
    print(f"Environment: {environment} ({environment_id})")
    print()
    print("Sub-pipelines:")
    for sub_def in subpipelines.values():
        print(f"  - {sub_def.name}: {len(sub_def.activities)} activities ({sub_def.deployed_id})")
    print(f"Orchestrator: {orchestrator_name} ({orchestrator_id})")
    print(f"  - {len(orchestrator_def.activities)} activities (1 setup + {len(orchestrator_def.activities) - 1} invoke)")
    print(f"Total: {len(subpipelines)} sub-pipelines + 1 orchestrator = {len(subpipelines) + 1} pipelines")
    max_activities = max(len(s.activities) for s in subpipelines.values())
    print(f"Max activities in a single pipeline: {max_activities}")


if __name__ == "__main__":
    main()
