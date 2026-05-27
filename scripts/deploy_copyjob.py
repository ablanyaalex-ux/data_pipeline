#!/usr/bin/env python3
"""Deploy a single Copy Job to Microsoft Fabric."""

import os

import click
from azure.identity import ClientSecretCredential
from azure.identity import DefaultAzureCredential

from tag_data_engineering.deployment.fabric_connection import FabricConnection
from tag_data_engineering.deployment.fabric_deployment import deploy_fabric_copyjob
from tag_data_engineering.pipeline.models import Layer
from tag_data_engineering.pipeline.pipeline_discoverer import PipelineDiscoverer


@click.command()
@click.option("--workspace", "-w", required=True, help="Fabric workspace name")
@click.option("--lakehouse", "-l", required=True, help="Lakehouse name")
@click.option("--entity", "-e", default="verint_activity_mapping", help="Entity name to deploy (default: verint_activity_mapping)")
def main(workspace: str, lakehouse: str, entity: str) -> None:
    print("=" * 80)
    print(f"COPY JOB DEPLOYMENT: {entity}")
    print("=" * 80)

    # Discover the pipeline to find the copy job activity
    print(f"Discovering pipeline activities for: {entity}")
    discoverer = PipelineDiscoverer()
    pipeline_def = discoverer.build_pipeline(name="temp", add_setup=False)

    # Find the LANDING_COPYJOB activity for this entity
    copyjob_activity = None
    for activity in pipeline_def.activities:
        if activity.layer == Layer.LANDING_COPYJOB and activity.entity == entity:
            copyjob_activity = activity
            break

    if not copyjob_activity:
        print(f"ERROR: No copy job found for entity '{entity}'")
        print("Available copy job entities:")
        for a in pipeline_def.activities:
            if a.layer == Layer.LANDING_COPYJOB:
                print(f"  - {a.entity}")
        return

    print(f"Found copy job: {copyjob_activity.name}")

    # Authenticate (same pattern as pipeline_deploy.py)
    print("\nAuthenticating with Azure...")
    tenant_id = os.getenv("APP_TENANT_ID")
    client_id = os.getenv("APP_ID")
    client_secret = os.getenv("APP_CLIENT_SECRET")

    if tenant_id and client_id and client_secret:
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )
        print("Authenticated as service principal (APP_ID)")
    else:
        credential = DefaultAzureCredential()
        print("Authenticated using default credentials (your personal identity)")

    fabric_conn = FabricConnection(credential=credential)

    # Get IDs (same pattern as pipeline_deploy.py)
    print(f"\nFinding workspace: {workspace}")
    workspace_id = fabric_conn._get_workspace_id_by_name(workspace_name=workspace)
    print(f"Found workspace ID: {workspace_id}")

    print(f"Finding lakehouse: {lakehouse}")
    lakehouse_id = fabric_conn._get_lakehouse_id_by_name(
        workspace_id=workspace_id,
        lakehouse_name=lakehouse,
    )
    print(f"Found lakehouse ID: {lakehouse_id}")

    # Deploy the Copy Job
    print("\n" + "=" * 80)
    print("DEPLOYING COPY JOB")
    print("=" * 80)
    print(f"Deploying: {copyjob_activity.name}")

    copyjob_id = deploy_fabric_copyjob(
        fabric_conn=fabric_conn,
        workspace_id=workspace_id,
        lakehouse_id=lakehouse_id,
        activity=copyjob_activity,
    )

    print("\n" + "=" * 80)
    print("DEPLOYMENT COMPLETE!")
    print("=" * 80)
    print(f"Copy Job Name: {copyjob_activity.name}")
    print(f"Copy Job ID:   {copyjob_id}")


if __name__ == "__main__":
    main()


# to run this script locally:

# $env:APP_TENANT_ID="b3b5c005-2c13-4fcc-8eb8-8cc6b0854bee"; $env:APP_ID="2aee0365-21e4-4ba3-9944-85e403349b92"; $env:APP_CLIENT_SECRET="nCxxxxx"; python scripts/deploy_copyjob.py -w Exploration_BI -l Exploration_BI_Lakehouse -e verint_activity_mapping
