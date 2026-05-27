#!/usr/bin/env python3
"""Deploy Spark Job Definitions to Microsoft Fabric.

This module provides functions for:
1. Building and uploading wheel files to Fabric environments
2. Creating and configuring Spark Job Definitions
3. Deploying jobs with proper separation of environment and job concerns
"""

import base64
import json
import shutil
import time
from datetime import datetime
from pathlib import Path

import click
import requests
from azure.identity import DefaultAzureCredential

from tag_data_engineering.deployment.build_utils import build_wheel
from tag_data_engineering.deployment.fabric_connection import FabricConnection


BASE_URL = "https://api.fabric.microsoft.com/v1"


def find_existing_job_id(fabric_conn: FabricConnection, workspace_id: str, job_name: str) -> str | None:
    try:
        job_id = fabric_conn._get_spark_job_id_by_name(workspace_id=workspace_id, job_name=job_name)
        print(f"Found existing job: {job_name} (ID: {job_id})")
        return job_id
    except RuntimeError:
        return None


def create_spark_job_definition(fabric_conn: FabricConnection, workspace_id: str, job_name: str) -> str:
    print(f"Creating new Spark Job Definition: {job_name}")
    headers = fabric_conn._get_api_headers()
    initial_config = {
        "executableFile": None,
        "defaultLakehouseArtifactId": "",
        "mainClass": "",
        "additionalLakehouseIds": [],
        "retryPolicy": None,
        "commandLineArguments": "",
        "additionalLibraryUris": [],
        "language": "",
        "environmentArtifactId": None,
    }
    payload = {
        "displayName": job_name,
        "type": "SparkJobDefinition",
        "definition": {
            "format": "SparkJobDefinitionV1",
            "parts": [{"path": "SparkJobDefinitionV1.json", "payload": base64.b64encode(json.dumps(initial_config).encode()).decode(), "payloadType": "InlineBase64"}],
        },
    }
    resp = requests.post(url=f"{BASE_URL}/workspaces/{workspace_id}/items", headers=headers, json=payload)
    resp.raise_for_status()
    job_id = resp.json()["id"]
    print(f"Created SJD: {job_id}")
    return job_id


def list_files_in_onelake(fabric_conn: FabricConnection, workspace_id: str, job_id: str, subfolder: str) -> list[str]:
    url = f"https://onelake.dfs.fabric.microsoft.com/{workspace_id}/{job_id}/{subfolder}?resource=filesystem&recursive=false"
    headers = {"Authorization": f"Bearer {fabric_conn._get_storage_token()}"}
    resp = requests.get(url=url, headers=headers)
    resp.raise_for_status()
    files = []
    for path_info in resp.json().get("paths", []):
        full_path = path_info.get("name", "")
        parts = full_path.split("/")
        if len(parts) >= 3 and parts[-2] == subfolder:
            files.append(parts[-1])
    return files


def delete_old_main_files(fabric_conn: FabricConnection, workspace_id: str, job_id: str, job_name: str) -> None:
    files = list_files_in_onelake(fabric_conn=fabric_conn, workspace_id=workspace_id, job_id=job_id, subfolder="Main")
    files_to_delete = [f for f in files if f.startswith(job_name) and f.endswith(".py")]
    if not files_to_delete:
        print("No old main files found")
        return
    print(f"Found {len(files_to_delete)} old main file(s) to delete")
    endpoint = f"https://onelake.dfs.fabric.microsoft.com/{workspace_id}/{job_id}"
    headers = {"Authorization": f"Bearer {fabric_conn._get_storage_token()}"}
    for filename in files_to_delete:
        resp = requests.delete(url=f"{endpoint}/Main/{filename}", headers=headers)
        resp.raise_for_status()
        print(f"Deleted old file: {filename}")


def upload_file_to_onelake(fabric_conn: FabricConnection, workspace_id: str, job_id: str, subfolder: str, filename: str, content: bytes) -> None:
    endpoint = f"https://onelake.dfs.fabric.microsoft.com/{workspace_id}/{job_id}"
    headers = {"Authorization": f"Bearer {fabric_conn._get_storage_token()}"}
    resp = requests.put(url=f"{endpoint}/{subfolder}/{filename}?resource=file", headers=headers)
    resp.raise_for_status()
    append_headers = headers.copy()
    append_headers["Content-Type"] = "text/plain" if filename.endswith(".py") else "application/octet-stream"
    resp = requests.patch(url=f"{endpoint}/{subfolder}/{filename}?position=0&action=append", data=content, headers=append_headers)
    resp.raise_for_status()
    resp = requests.patch(url=f"{endpoint}/{subfolder}/{filename}?position={len(content)}&action=flush", headers=append_headers)
    resp.raise_for_status()
    print(f"Successfully uploaded: {subfolder}/{filename} ({len(content)} bytes)")


def update_job_definition(fabric_conn: FabricConnection, workspace_id: str, job_id: str, job_name: str, main_file_path: str, environment_id: str, lakehouse_id: str | None) -> None:
    headers = fabric_conn._get_api_headers()
    config = {
        "executableFile": main_file_path,
        "defaultLakehouseArtifactId": lakehouse_id or "",
        "mainClass": "",
        "additionalLakehouseIds": [],
        "retryPolicy": None,
        "commandLineArguments": "",
        "additionalLibraryUris": [],
        "language": "Python",
        "environmentArtifactId": environment_id,
    }
    payload = {
        "displayName": job_name,
        "type": "SparkJobDefinition",
        "definition": {
            "format": "SparkJobDefinitionV1",
            "parts": [{"path": "SparkJobDefinitionV1.json", "payload": base64.b64encode(json.dumps(config).encode()).decode(), "payloadType": "InlineBase64"}],
        },
    }
    resp = requests.post(url=f"{BASE_URL}/workspaces/{workspace_id}/items/{job_id}/updateDefinition", headers=headers, json=payload)
    resp.raise_for_status()


def deploy_spark_job(
    fabric_conn: FabricConnection,
    workspace_id: str,
    environment_id: str,
    lakehouse_id: str,
    job_name: str,
    job_file: Path,
) -> str:
    """Deploy a Spark Job Definition (without updating environment).

    This function creates or updates a Spark Job Definition with:
    - Main Python file uploaded to OneLake
    - Configuration pointing to the environment and lakehouse

    Note: Call deploy_environment() separately before deploying jobs
    to ensure the wheel is installed.

    Args:
        fabric_conn: Fabric connection
        workspace_id: Workspace ID
        environment_id: Environment ID (must already have wheel deployed)
        lakehouse_id: Default lakehouse ID
        job_name: Name for the job definition
        job_file: Path to the Python job file

    Returns:
        ID of the deployed job definition
    """
    print(f"\nDeploying Spark Job: {job_name}")

    # Find or create job definition
    job_id = find_existing_job_id(fabric_conn=fabric_conn, workspace_id=workspace_id, job_name=job_name)
    if not job_id:
        job_id = create_spark_job_definition(fabric_conn=fabric_conn, workspace_id=workspace_id, job_name=job_name)
        print("Waiting for SJD to be ready...")
        time.sleep(5)

    # Upload main file
    print("Uploading main file to OneLake...")
    delete_old_main_files(fabric_conn=fabric_conn, workspace_id=workspace_id, job_id=job_id, job_name=job_name)

    with open(job_file) as f:
        job_content = f.read()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    main_file_name = f"{job_name}_{timestamp}.py"

    upload_file_to_onelake(
        fabric_conn=fabric_conn,
        workspace_id=workspace_id,
        job_id=job_id,
        subfolder="Main",
        filename=main_file_name,
        content=job_content.encode(),
    )

    main_file_path = f"abfss://{workspace_id}@onelake.dfs.fabric.microsoft.com/{job_id}/Main/{main_file_name}"

    # Update job configuration
    print("Updating job configuration...")
    update_job_definition(
        fabric_conn=fabric_conn,
        workspace_id=workspace_id,
        job_id=job_id,
        job_name=job_name,
        main_file_path=main_file_path,
        environment_id=environment_id,
        lakehouse_id=lakehouse_id,
    )

    print(f"✅ Deployed: {job_name} ({job_id})")
    return job_id


@click.command()
@click.option("--workspace", "-w", required=True, help="Fabric workspace name")
@click.option("--job-name", "-j", required=True, help="Spark job name")
@click.option("--environment", "-e", required=True, help="Fabric environment name")
@click.option("--lakehouse", "-l", required=True, help="Default lakehouse name")
def main(workspace: str, job_name: str, environment: str, lakehouse: str) -> None:
    """Deploy a single Spark Job Definition to Fabric."""
    print(f"Deploying to Fabric workspace: {workspace}")
    print(f"Job name: {job_name}")
    print(f"Environment: {environment}")
    print(f"Default lakehouse: {lakehouse}")

    # Clean build artifacts
    print("\nCleaning build artifacts...")
    for dir_name in ["build", "dist"]:
        if Path(dir_name).exists():
            shutil.rmtree(dir_name)
    for egg_info in Path("src").glob("*.egg-info"):
        if egg_info.is_dir():
            shutil.rmtree(egg_info)

    # Find job file
    job_file = Path(f"jobs/spark/{job_name}.py")
    if not job_file.exists():
        # Try alternate location
        job_file = Path(f"jobs_spark/{job_name}.py")
    if not job_file.exists():
        raise FileNotFoundError(f"Job file not found: {job_file}")

    # Build wheel
    print("\nBuilding wheel...")
    wheel_file = build_wheel()

    # Authenticate
    print("\nAuthenticating with Azure...")
    credential = DefaultAzureCredential()
    fabric_conn = FabricConnection(credential=credential)

    # Get IDs
    print(f"\nFinding workspace: {workspace}")
    workspace_id = fabric_conn._get_workspace_id_by_name(workspace_name=workspace)
    print(f"Found workspace ID: {workspace_id}")

    print(f"Finding environment: {environment}")
    environment_id = fabric_conn._get_environment_id_by_name(workspace_id=workspace_id, environment_name=environment)
    print(f"Found environment ID: {environment_id}")

    print(f"Finding lakehouse: {lakehouse}")
    lakehouse_id = fabric_conn._get_lakehouse_id_by_name(workspace_id=workspace_id, lakehouse_name=lakehouse)
    print(f"Found lakehouse ID: {lakehouse_id}")

    # Deploy environment (once)
    fabric_conn.deploy_wheel_to_environment(
        workspace_id=workspace_id,
        environment_id=environment_id,
        wheel_file=wheel_file,
    )

    # Deploy job
    job_id = deploy_spark_job(
        fabric_conn=fabric_conn,
        workspace_id=workspace_id,
        environment_id=environment_id,
        lakehouse_id=lakehouse_id,
        job_name=job_name,
        job_file=job_file,
    )

    print("\n" + "=" * 80)
    print("✅ DEPLOYMENT COMPLETE!")
    print("=" * 80)
    print(f"Job ID: {job_id}")
    print(f"Job Name: {job_name}")
    print(f"Environment: {environment} ({environment_id})")
    print(f"Lakehouse: {lakehouse} ({lakehouse_id})")
    print(f"Custom library: {wheel_file.name}")


if __name__ == "__main__":
    main()
