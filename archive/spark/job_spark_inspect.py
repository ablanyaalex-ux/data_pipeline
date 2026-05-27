#!/usr/bin/env python3
"""Inspect deployed Spark job and environment configuration."""

import json

import click
import requests
from azure.identity import DefaultAzureCredential

from tag_data_engineering.deployment.fabric_connection import FabricConnection


BASE_URL = "https://api.fabric.microsoft.com/v1"


def inspect_spark_job(fabric_conn: FabricConnection, workspace_id: str, job_name: str, environment_name: str) -> None:
    """Inspect a deployed Spark job and its environment."""
    headers = fabric_conn._get_api_headers()

    # Get environment ID
    print(f"Looking for environment: {environment_name}")
    environment_id = fabric_conn._get_environment_id_by_name(workspace_id=workspace_id, environment_name=environment_name)
    print(f"Found environment ID: {environment_id}")

    # Get job ID
    print(f"Looking for job: {job_name}")
    job_id = fabric_conn._get_spark_job_id_by_name(workspace_id=workspace_id, job_name=job_name)
    print(f"Found job ID: {job_id}")

    print("=" * 80)
    print("DEPLOYMENT INSPECTION")
    print("=" * 80)
    print(f"\nWorkspace: {workspace_id}")
    print(f"Environment: {environment_name} ({environment_id})")
    print(f"Job: {job_name} ({job_id})")

    # Check environment staging libraries
    print("\n" + "=" * 80)
    print("ENVIRONMENT STAGING LIBRARIES")
    print("=" * 80)
    resp = requests.get(f"{BASE_URL}/workspaces/{workspace_id}/environments/{environment_id}/staging/libraries", headers=headers)
    resp.raise_for_status()
    staging_libs = resp.json()

    custom_libs = staging_libs.get("customLibraries", {})
    wheel_files = custom_libs.get("wheelFiles", [])
    print(f"\nWheel files in staging ({len(wheel_files)}):")
    for wheel in wheel_files:
        print(f"  • {wheel}")

    # Check environment published state
    print("\n" + "=" * 80)
    print("ENVIRONMENT PUBLISHED STATE")
    print("=" * 80)
    resp = requests.get(f"{BASE_URL}/workspaces/{workspace_id}/environments/{environment_id}", headers=headers)
    resp.raise_for_status()
    env_data = resp.json()
    publish_details = env_data.get("properties", {}).get("publishDetails", {})
    print(f"\nPublish State: {publish_details.get('state', 'Unknown')}")
    print(f"Target State: {publish_details.get('targetState', 'Unknown')}")

    # Check job definition
    print("\n" + "=" * 80)
    print("SPARK JOB DEFINITION")
    print("=" * 80)
    resp = requests.post(f"{BASE_URL}/workspaces/{workspace_id}/items/{job_id}/getDefinition", headers=headers)
    resp.raise_for_status()
    job_def = resp.json()

    # Parse the definition
    for part in job_def.get("definition", {}).get("parts", []):
        if part.get("path") == "SparkJobDefinitionV1.json":
            import base64

            config_json = base64.b64decode(part.get("payload", "")).decode()
            config = json.loads(config_json)

            print(f"\nExecutable File: {config.get('executableFile', 'Not set')}")
            print(f"Environment ID: {config.get('environmentArtifactId', 'Not set')}")
            print(f"Default Lakehouse: {config.get('defaultLakehouseArtifactId', 'Not set')}")
            print(f"Language: {config.get('language', 'Not set')}")

            # Extract main file name from path
            executable = config.get("executableFile", "")
            if executable:
                main_file_name = executable.split("/")[-1]
                print(f"\nMain File Name: {main_file_name}")

    # List files in OneLake Main directory
    print("\n" + "=" * 80)
    print("ONELAKE MAIN DIRECTORY FILES")
    print("=" * 80)
    url = f"https://onelake.dfs.fabric.microsoft.com/{workspace_id}/{job_id}/Main?resource=filesystem&recursive=false"
    storage_headers = {"Authorization": f"Bearer {fabric_conn._get_storage_token()}"}
    resp = requests.get(url=url, headers=storage_headers)
    resp.raise_for_status()

    files = []
    for path_info in resp.json().get("paths", []):
        full_path = path_info.get("name", "")
        parts = full_path.split("/")
        if len(parts) >= 3 and parts[-2] == "Main":
            files.append(parts[-1])

    print(f"\nFiles in Main directory ({len(files)}):")
    for f in files:
        print(f"  • {f}")

    # Download and show the main file content
    if files:
        print("\n" + "=" * 80)
        print(f"MAIN FILE CONTENT: {files[0]}")
        print("=" * 80)

        file_url = f"https://onelake.dfs.fabric.microsoft.com/{workspace_id}/{job_id}/Main/{files[0]}"
        resp = requests.get(url=file_url, headers=storage_headers)
        resp.raise_for_status()

        content = resp.text
        print(content)

    print("\n" + "=" * 80)
    print("INSPECTION COMPLETE")
    print("=" * 80)


@click.command()
@click.option("--workspace", "-w", required=True, help="Fabric workspace name")
@click.option("--job-name", "-j", required=True, help="Spark job name to inspect")
@click.option("--environment", "-e", required=True, help="Environment name")
def main(workspace: str, job_name: str, environment: str) -> None:
    """Inspect a deployed Spark job and environment configuration."""
    print(f"Inspecting Spark job in workspace: {workspace}")
    print(f"Job: {job_name}")
    print(f"Environment: {environment}")

    credential = DefaultAzureCredential()
    fabric_conn = FabricConnection(credential=credential)

    workspace_id = fabric_conn._get_workspace_id_by_name(workspace_name=workspace)
    print(f"Workspace ID: {workspace_id}")

    inspect_spark_job(fabric_conn, workspace_id, job_name, environment)


if __name__ == "__main__":
    main()
