#!/usr/bin/env python3
"""Run a Notebook in Microsoft Fabric.

This script triggers a notebook run with parameters, useful for testing
notebooks that are normally run via pipelines.
"""

import time

import click
import requests
from azure.identity import DefaultAzureCredential

from tag_data_engineering.deployment.fabric_connection import FabricConnection


BASE_URL = "https://api.fabric.microsoft.com/v1"


def find_notebook_id(
    fabric_conn: FabricConnection,
    workspace_id: str,
    notebook_name: str,
) -> str:
    """Find Notebook by name."""
    headers = fabric_conn._get_api_headers()
    resp = requests.get(
        f"{BASE_URL}/workspaces/{workspace_id}/items?type=Notebook",
        headers=headers,
    )
    resp.raise_for_status()

    for item in resp.json().get("value", []):
        if item["displayName"] == notebook_name:
            return item["id"]
    raise ValueError(f"Notebook not found: {notebook_name}")


def find_lakehouse_id(
    fabric_conn: FabricConnection,
    workspace_id: str,
    lakehouse_name: str,
) -> str:
    """Find Lakehouse by name."""
    headers = fabric_conn._get_api_headers()
    resp = requests.get(
        f"{BASE_URL}/workspaces/{workspace_id}/items?type=Lakehouse",
        headers=headers,
    )
    resp.raise_for_status()

    for item in resp.json().get("value", []):
        if item["displayName"] == lakehouse_name:
            return item["id"]
    raise ValueError(f"Lakehouse not found: {lakehouse_name}")


def run_notebook(
    fabric_conn: FabricConnection,
    workspace_id: str,
    notebook_id: str,
    lakehouse_id: str,
    lakehouse_name: str,
    parameters: dict | None = None,
    use_starter_pool: bool = True,
) -> str:
    """Run a notebook and return the run ID.

    Note: This uses the Fabric REST API to run the notebook on-demand.
    Reference: https://learn.microsoft.com/en-us/fabric/data-engineering/notebook-public-api

    Args:
        fabric_conn: Authenticated FabricConnection
        workspace_id: Workspace ID
        notebook_id: Notebook ID
        lakehouse_id: Lakehouse ID
        lakehouse_name: Lakehouse name
        parameters: Optional parameters to pass to notebook
        use_starter_pool: Whether to use starter pool (set False for custom environments)
    """
    headers = fabric_conn._get_api_headers()

    # Build the execution request payload
    # Fabric expects parameters inside executionData as {parameterName: {value, type}}
    # Reference: https://learn.microsoft.com/en-us/fabric/data-engineering/notebook-public-api#run-a-notebook-on-demand
    payload = {"executionData": {}}

    if parameters:
        payload["executionData"]["parameters"] = {k: {"value": v, "type": "string"} for k, v in parameters.items()}

    # Configuration for the run - specify lakehouse
    # Note: useStarterPool must be False for custom environments with non-default configs
    payload["executionData"]["configuration"] = {
        "useStarterPool": use_starter_pool,
        "defaultLakehouse": {
            "name": lakehouse_name,
            "id": lakehouse_id,
            "workspaceId": workspace_id,
        },
    }

    print("Starting notebook run...")
    if parameters:
        print(f"  Parameters: {parameters}")
    print(f"  Lakehouse: {lakehouse_name}")
    print(f"  Using starter pool: {use_starter_pool}")

    # Use the Jobs API to run notebook
    resp = requests.post(
        f"{BASE_URL}/workspaces/{workspace_id}/items/{notebook_id}/jobs/instances?jobType=RunNotebook",
        headers=headers,
        json=payload if payload else None,
    )

    if resp.status_code == 202:
        # Accepted - get the location for polling
        location = resp.headers.get("Location", "")
        retry_after = int(resp.headers.get("Retry-After", "10"))

        print("✅ Notebook run started")
        print(f"  Polling interval: {retry_after}s")

        if location:
            return location
        else:
            print("Warning: No location header returned for polling")
            return ""
    else:
        print(f"Error: {resp.status_code}")
        print(f"Response: {resp.text}")
        resp.raise_for_status()
        return ""


def poll_notebook_run(
    fabric_conn: FabricConnection,
    location: str,
    timeout_minutes: int = 30,
) -> dict:
    """Poll for notebook run completion."""
    headers = fabric_conn._get_api_headers()

    start_time = time.time()
    timeout_seconds = timeout_minutes * 60

    print(f"\nWaiting for notebook to complete (timeout: {timeout_minutes}m)...")

    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            raise TimeoutError(f"Notebook run timed out after {timeout_minutes} minutes")

        resp = requests.get(location, headers=headers)

        if resp.status_code == 200:
            result = resp.json()
            status = result.get("status", "Unknown")

            if status == "Completed":
                print("\n✅ Notebook completed successfully!")
                return result
            elif status == "Failed":
                error = result.get("failureReason", {})
                print("\n❌ Notebook failed!")
                print(f"  Error: {error.get('message', 'Unknown error')}")
                return result
            elif status == "Cancelled":
                print("\n⚠️ Notebook was cancelled")
                return result
            else:
                # Still running
                mins = int(elapsed // 60)
                secs = int(elapsed % 60)
                print(f"  [{mins:02d}:{secs:02d}] Status: {status}...", end="\r")

        time.sleep(10)


@click.command()
@click.option("--workspace", "-w", required=True, help="Fabric workspace name")
@click.option("--notebook", "-n", required=True, help="Notebook name")
@click.option("--lakehouse", "-k", required=True, help="Lakehouse name")
@click.option("--layer", "-l", required=True, help="Layer (landing, bronze, silver, gold)")
@click.option("--entity", "-e", required=True, help="Entity name (e.g., people, complaints)")
@click.option("--timeout", "-t", default=1, help="Timeout in minutes (default: 1)")
@click.option("--no-wait", is_flag=True, help="Don't wait for completion")
@click.option("--no-starter-pool", is_flag=True, help="Don't use starter pool (required for custom environments)")
def main(workspace: str, notebook: str, lakehouse: str, layer: str, entity: str, timeout: int, no_wait: bool, no_starter_pool: bool) -> None:
    """Run a Fabric Notebook with parameters.

    Example:
        python scripts/job_notebook_run.py -w TAG_Prod_DE -n run_transformation -k TAG_DE_Lakehouse -l landing -e people

    For notebooks with custom environments (non-default executor/driver configs):
        python scripts/job_notebook_run.py -w TAG_Prod_DE -n run_transformation -k TAG_DE_Lakehouse -l landing -e people --no-starter-pool
    """
    print("=" * 80)
    print("NOTEBOOK RUN")
    print("=" * 80)
    print(f"Workspace: {workspace}")
    print(f"Notebook: {notebook}")
    print(f"Lakehouse: {lakehouse}")
    print(f"Parameters: layer={layer}, entity={entity}")
    if no_starter_pool:
        print("Starter pool: DISABLED (custom environment)")
    print()

    # Authenticate
    print("Authenticating with Azure...")
    credential = DefaultAzureCredential()
    fabric_conn = FabricConnection(credential=credential)

    # Get workspace ID
    print(f"\nFinding workspace: {workspace}")
    workspace_id = fabric_conn._get_workspace_id_by_name(workspace_name=workspace)
    print(f"Found workspace ID: {workspace_id}")

    # Find notebook
    print(f"Finding notebook: {notebook}")
    notebook_id = find_notebook_id(fabric_conn, workspace_id, notebook)
    print(f"Found notebook ID: {notebook_id}")

    # Find lakehouse
    print(f"Finding lakehouse: {lakehouse}")
    lakehouse_id = find_lakehouse_id(fabric_conn, workspace_id, lakehouse)
    print(f"Found lakehouse ID: {lakehouse_id}")

    # Run notebook with parameters
    parameters = {
        "layer": layer,
        "entity": entity,
    }

    location = run_notebook(
        fabric_conn=fabric_conn,
        workspace_id=workspace_id,
        notebook_id=notebook_id,
        lakehouse_id=lakehouse_id,
        lakehouse_name=lakehouse,
        parameters=parameters,
        use_starter_pool=not no_starter_pool,
    )

    if no_wait:
        print("\n--no-wait specified, not waiting for completion")
        print(f"Poll URL: {location}")
        return

    if location:
        result = poll_notebook_run(
            fabric_conn=fabric_conn,
            location=location,
            timeout_minutes=timeout,
        )

        print("\n" + "=" * 80)
        print("RUN DETAILS")
        print("=" * 80)
        print(f"Status: {result.get('status', 'Unknown')}")
        if result.get("startTimeUtc"):
            print(f"Start Time: {result['startTimeUtc']}")
        if result.get("endTimeUtc"):
            print(f"End Time: {result['endTimeUtc']}")


if __name__ == "__main__":
    main()
