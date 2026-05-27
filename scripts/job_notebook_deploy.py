#!/usr/bin/env python3
"""Deploy Notebook to Microsoft Fabric.

This approach uses Notebooks instead of Spark Job Definitions because:
1. Notebooks can use High Concurrency sessions (shared warm compute)
2. Much faster startup time (~30s vs ~5 minutes for SJDs)
3. Better for development iteration

The deployed notebook:
- Has parameters cell for pipeline parameterization (layer, entity)
- Uses a custom Environment with pre-installed wheel (no pip install at runtime)
- Runs the same transformation logic as the Spark job
"""

import os

import click
from azure.identity import ClientSecretCredential
from azure.identity import DefaultAzureCredential

from tag_data_engineering.deployment.build_utils import build_wheel
from tag_data_engineering.deployment.build_utils import clean_build_artifacts
from tag_data_engineering.deployment.fabric_connection import FabricConnection
from tag_data_engineering.deployment.fabric_deployment import deploy_fabric_notebook


@click.command()
@click.option("--workspace", "-w", required=True, help="Fabric workspace name")
@click.option("--job-name", "-j", required=True, help="Notebook name (same as Spark job name)")
@click.option("--lakehouse", "-l", required=True, help="Default lakehouse name")
@click.option("--environment", "-e", required=True, help="Environment name (wheel is installed here)")
@click.option("--dry-run", is_flag=True, help="Print notebook content without deploying")
def main(workspace: str, job_name: str, lakehouse: str, environment: str, dry_run: bool) -> None:
    """Deploy a Notebook to Microsoft Fabric.

    This is faster than Spark Job Definitions because Notebooks can use
    High Concurrency sessions with shared warm compute (~30s startup vs ~5min).

    The notebook:
    - Has parameters cell for pipeline parameterization (layer, entity)
    - Uses a custom Environment with pre-installed wheel (required)
    - Runs the same transformation logic as the Spark job

    Example:
        python scripts/job_notebook_deploy.py -w TAG_Prod_DE -j run_transformation -l TAG_DE_Lakehouse -e data_pipeline
    """
    print("=" * 80)
    print("NOTEBOOK DEPLOYMENT")
    print("=" * 80)
    print(f"Workspace: {workspace}")
    print(f"Notebook name: {job_name}")
    print(f"Lakehouse: {lakehouse}")
    print(f"Environment: {environment}")
    print()

    # Clean build artifacts and build wheel
    clean_build_artifacts()
    wheel_file = build_wheel()

    if dry_run:
        print("\n" + "=" * 80)
        print("DRY RUN - Would deploy notebook with these settings:")
        print("=" * 80)
        print(f"Notebook: {job_name}")
        print(f"Lakehouse: {lakehouse}")
        print(f"Environment: {environment}")
        print("(Use without --dry-run to actually deploy)")
        return

    # Authenticate
    print("\nAuthenticating with Azure...")

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

    # Get IDs
    print(f"\nFinding workspace: {workspace}")
    workspace_id = fabric_conn._get_workspace_id_by_name(workspace_name=workspace)
    print(f"Found workspace ID: {workspace_id}")

    print(f"Finding lakehouse: {lakehouse}")
    lakehouse_id = fabric_conn._get_lakehouse_id_by_name(
        workspace_id=workspace_id,
        lakehouse_name=lakehouse,
    )
    print(f"Found lakehouse ID: {lakehouse_id}")

    print(f"Finding SQL endpoint for lakehouse: {lakehouse}")
    sql_endpoint_id = fabric_conn._get_sql_endpoint_id_by_lakehouse_name(
        workspace_id=workspace_id,
        lakehouse_name=lakehouse,
    )
    print(f"Found SQL endpoint ID: {sql_endpoint_id}")

    # Find environment and deploy wheel
    environment_id = fabric_conn.find_environment(workspace_id=workspace_id, environment_name=environment)

    fabric_conn.deploy_wheel_to_environment(
        workspace_id=workspace_id,
        environment_id=environment_id,
        wheel_file=wheel_file,
    )

    # Deploy notebook
    notebook_id = deploy_fabric_notebook(
        fabric_conn=fabric_conn,
        workspace_id=workspace_id,
        lakehouse_id=lakehouse_id,
        lakehouse_name=lakehouse,
        environment_id=environment_id,
        notebook_name=job_name,
        sql_endpoint_id=sql_endpoint_id,
    )

    print("\n" + "=" * 80)
    print("✅ DEPLOYMENT COMPLETE!")
    print("=" * 80)
    print(f"Notebook ID: {notebook_id}")
    print(f"Notebook Name: {job_name}")
    print(f"Lakehouse: {lakehouse} ({lakehouse_id})")
    print(f"Environment: {environment} ({environment_id})")
    print()
    print("To run the notebook:")
    print("  1. Open in Fabric UI and run manually, OR")
    print(f"  2. Use: python scripts/job_notebook_run.py -w {workspace} -n {job_name} -k {lakehouse} -l <layer> -e <entity>")


if __name__ == "__main__":
    main()
