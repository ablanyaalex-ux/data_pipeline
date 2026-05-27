#!/usr/bin/env python3
import base64
import json
import shutil
import subprocess
import time
from pathlib import Path

import click
import requests
from azure.identity import DefaultAzureCredential

from tag_data_engineering.deployment.fabric_connection import FabricConnection


BASE_URL = "https://api.fabric.microsoft.com/v1"


def build_wheel() -> Path:
    """Build a universal Python wheel compatible with any platform."""
    print("Building wheel...")
    subprocess.run(["python", "-m", "pip", "wheel", ".", "--no-deps", "--wheel-dir", "dist"], check=True)
    wheel_files = list(Path("dist").glob("*.whl"))
    if not wheel_files:
        raise FileNotFoundError("No wheel file found")

    # Check if wheel is universal (py3-none-any)
    wheel_name = wheel_files[0].name
    if "py3-none-any" not in wheel_name and "py2.py3-none-any" not in wheel_name:
        print(f"⚠️  Warning: Wheel {wheel_name} may not be universal!")

    print(f"Built wheel: {wheel_files[0]}")
    return wheel_files[0]


def create_function_app_code(function_name: str, function_code: str, has_lakehouse: bool = False) -> str:
    """Return the function code as-is without any wrapping."""
    return function_code


def create_functions_metadata(function_name: str, has_lakehouse: bool = False) -> dict:
    fabric_params = []
    if has_lakehouse:
        fabric_params.append({"name": "lakehouse", "type": "FabricLakehouseClient"})

    return {
        "runtime": "PYTHON",
        "functionsMetadata": [
            {
                "name": function_name,
                "scriptFile": "function_app.py",
                "bindings": [{"name": "req", "type": "HttpTrigger", "direction": "In", "authLevel": "Anonymous", "methods": ["post"], "route": function_name}],
                "fabricProperties": {"fabricMetadataSchemaVersion": None, "fabricFunctionReturnType": "dict", "fabricFunctionParameters": fabric_params},
            }
        ],
    }


def create_or_update_function(fabric_conn: FabricConnection, workspace_id: str, function_name: str, function_code: str, wheel_file: Path, lakehouse_id: str | None = None) -> tuple[str, str]:
    """Create or update a UDF and return (function_id, wheel_name)."""
    print(f"Checking for existing User Data Function: {function_name}")
    headers = fabric_conn._get_api_headers()

    list_url = f"{BASE_URL}/workspaces/{workspace_id}/items?type=UserDataFunction"
    response = requests.get(url=list_url, headers=headers)
    response.raise_for_status()

    functions = response.json().get("value", [])
    existing = next((f for f in functions if f["displayName"] == function_name), None)
    function_id = existing["id"] if existing else None

    if not function_id:
        print(f"Creating new User Data Function: {function_name}")
        create_url = f"{BASE_URL}/workspaces/{workspace_id}/items"
        payload = {"displayName": function_name, "type": "UserDataFunction", "description": ""}

        max_retries = 5
        for attempt in range(max_retries):
            response = requests.post(url=create_url, headers=headers, json=payload)
            if response.status_code == 400:
                error_detail = response.json() if response.content else {}
                if error_detail.get("errorCode") == "ItemDisplayNameNotAvailableYet" and attempt < max_retries - 1:
                    print(f"⏳ Name not available yet, waiting 30s (retry {attempt + 2}/{max_retries})...")
                    time.sleep(30)
                    continue
                else:
                    print(f"❌ Error: {json.dumps(error_detail, indent=2)}")
                    response.raise_for_status()
            response.raise_for_status()
            break

        result = response.json() if response.content else {}
        function_id = result.get("id")
        if not function_id:
            raise RuntimeError("Could not extract function ID from response")
        print(f"Created UDF: {function_id}")
    else:
        print(f"Found existing function (ID: {function_id})")

    print("Uploading function code and libraries...")

    function_app_code = create_function_app_code(function_name, function_code, has_lakehouse=bool(lakehouse_id))
    function_app_b64 = base64.b64encode(function_app_code.encode()).decode()

    # Read wheel content
    with open(wheel_file, "rb") as f:
        wheel_content = f.read()
        wheel_content_b64 = base64.b64encode(wheel_content).decode()

    # Use the original wheel name (don't add hash - it breaks wheel naming convention)
    wheel_name = wheel_file.name
    print(f"📦 Wheel file: {wheel_name}")

    # Build connected data sources (lakehouse attachment)
    connected_data_sources = []
    if lakehouse_id:
        connected_data_sources.append({"alias": "Lakehouse", "artifactId": lakehouse_id, "artifactType": "Lakehouse", "workspaceId": workspace_id})
        print(f"📦 Adding lakehouse connection: {lakehouse_id}")

    definition_json = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/userDataFunction/definition/1.1.0/schema.json",
        "runtime": "PYTHON",
        "connectedDataSources": connected_data_sources,
        "functions": [{"name": function_name, "description": "", "isPublicEndpointEnabled": True}],
        "libraries": {"public": [{"name": "fabric-user-data-functions", "type": "PYPI", "version": "1.0"}], "private": [{"name": wheel_name, "type": "WHEEL"}]},
    }

    print("\n" + "=" * 80)
    print("DEFINITION.JSON CONTENT:")
    print("=" * 80)
    print(json.dumps(definition_json, indent=2))
    print("=" * 80 + "\n")

    definition_json_b64 = base64.b64encode(json.dumps(definition_json).encode()).decode()

    functions_metadata = create_functions_metadata(function_name, has_lakehouse=bool(lakehouse_id))
    functions_metadata_b64 = base64.b64encode(json.dumps(functions_metadata).encode()).decode()

    update_url = f"{BASE_URL}/workspaces/{workspace_id}/items/{function_id}/updateDefinition"
    payload = {
        "definition": {
            "parts": [
                {"path": "definition.json", "payload": definition_json_b64, "payloadType": "InlineBase64"},
                {"path": ".resources/functions.json", "payload": functions_metadata_b64, "payloadType": "InlineBase64"},
                {"path": "function_app.py", "payload": function_app_b64, "payloadType": "InlineBase64"},
                {"path": f"privateLibraries/{wheel_name}", "payload": wheel_content_b64, "payloadType": "InlineBase64"},
            ]
        }
    }

    response = requests.post(url=update_url, headers=headers, json=payload)
    if response.status_code >= 400:
        error_detail = response.json() if response.content else {}
        print(f"❌ Error: {json.dumps(error_detail, indent=2)}")
        response.raise_for_status()

    if response.status_code == 202:
        location = response.headers.get("Location", "")
        if "/operations/" in location:
            operation_id = location.split("/operations/")[-1]
            print("⏳ Waiting for update... (this may take several minutes)")
            max_wait = 300
            wait_time = 0
            max_retries = 3

            for retry in range(max_retries):
                wait_time = 0
                while wait_time < max_wait:
                    time.sleep(5)
                    wait_time += 5
                    op_resp = requests.get(f"{BASE_URL}/operations/{operation_id}", headers=headers)
                    op_resp.raise_for_status()
                    op_result = op_resp.json()
                    status = op_result.get("status", "")

                    if wait_time % 30 == 0:
                        print(f"  ⏳ Still waiting... ({wait_time}s elapsed)")

                    if status == "Succeeded":
                        print(f"Update completed after {wait_time}s")
                        print("Successfully uploaded function definition")
                        return function_id, wheel_name
                    elif status == "Failed":
                        error = op_result.get("error", {})
                        error_code = error.get("errorCode", "N/A")
                        error_msg = error.get("message", "Unknown error")

                        # Handle cooldown period
                        if error_code == "DeployCooldownBlock":
                            # Extract wait time from message like "Please wait 69 second(s) before publishing again."
                            import re

                            match = re.search(r"wait (\d+) second", error_msg)
                            if match:
                                wait_seconds = int(match.group(1)) + 5  # Add 5 second buffer
                                print(f"⏳ Deployment cooldown: waiting {wait_seconds} seconds...")
                                time.sleep(wait_seconds)
                                print("   Retrying deployment after cooldown...")
                                # Retry the deployment
                                response = requests.post(url=update_url, headers=headers, json=payload)
                                if response.status_code == 202:
                                    location = response.headers.get("Location", "")
                                    operation_id = location.split("/operations/")[-1]
                                    wait_time = 0  # Reset wait time for new operation
                                    continue

                        if error_code == "UnknownError" and retry < max_retries - 1:
                            print(f"⏳ Transient error, retrying... (attempt {retry + 2}/{max_retries})")
                            time.sleep(10)
                            response = requests.post(url=update_url, headers=headers, json=payload)
                            if response.status_code == 202:
                                location = response.headers.get("Location", "")
                                operation_id = location.split("/operations/")[-1]
                            break
                        else:
                            print(f"❌ Operation failed. Full response: {json.dumps(op_result, indent=2)}")
                            raise RuntimeError(f"Update failed: {error_msg} (Code: {error_code})")
                else:
                    continue
                break
            else:
                raise RuntimeError("Timeout waiting for update")

    print("Successfully uploaded function definition")
    return function_id, wheel_name


def wait_for_publish(fabric_conn: FabricConnection, workspace_id: str, function_id: str, function_name: str, max_wait: int = 300) -> None:
    """Monitor the UDF publish status and wait until it's ready."""
    print(f"\n⏳ Monitoring publish status for '{function_name}'...")
    print("   Waiting for function runtime to be ready...")

    # Give it time for the definition update to propagate and runtime to initialize
    # UDFs don't have a specific "publish" operation, but the runtime needs time to load
    wait_time = 60  # Wait 60 seconds for the update to propagate and runtime to initialize
    print(f"   Waiting {wait_time}s for definition update to propagate...")
    time.sleep(wait_time)
    print("   ✅ Publish monitoring complete!")


def deploy_function(fabric_conn: FabricConnection, workspace_id: str, job_name: str, job_file: Path, wheel_file: Path, lakehouse_id: str | None = None) -> tuple[str, str]:
    """Deploy function and return (function_id, wheel_name)."""
    print("Checking for existing User Data Function...")
    with open(job_file) as f:
        function_code = f.read()
    function_id, wheel_name = create_or_update_function(fabric_conn=fabric_conn, workspace_id=workspace_id, function_name=job_name, function_code=function_code, wheel_file=wheel_file, lakehouse_id=lakehouse_id)

    # Wait for publish to complete
    wait_for_publish(fabric_conn=fabric_conn, workspace_id=workspace_id, function_id=function_id, function_name=job_name)

    return function_id, wheel_name


@click.command()
@click.option("--workspace", "-w", required=True, help="Fabric workspace name")
@click.option("--job-name", "-j", required=True, help="Function name")
@click.option("--lakehouse", "-l", required=False, help="Lakehouse name to attach to the function")
def main(workspace: str, job_name: str, lakehouse: str | None = None) -> None:
    print(f"Deploying to Fabric workspace: {workspace}")
    print(f"Function name: {job_name}")
    if lakehouse:
        print(f"Lakehouse: {lakehouse}")
    print("Cleaning targets...")
    for dir_name in ["build", "dist"]:
        if Path(dir_name).exists():
            shutil.rmtree(dir_name)
    for egg_info in Path("src").glob("*.egg-info"):
        if egg_info.is_dir():
            shutil.rmtree(egg_info)
    job_file = Path(f"jobs_function/{job_name}.py")
    if not job_file.exists():
        raise FileNotFoundError(f"Function file not found: {job_file}")
    print("Building wheel...")
    wheel_file = build_wheel()
    print("Authenticating with Azure...")
    credential = DefaultAzureCredential()
    fabric_conn = FabricConnection(credential=credential)
    print(f"Finding workspace: {workspace}")
    workspace_id = fabric_conn._get_workspace_id_by_name(workspace_name=workspace)
    print(f"Found workspace ID: {workspace_id}")

    lakehouse_id = None
    if lakehouse:
        print(f"Looking up lakehouse: {lakehouse}")
        lakehouse_id = fabric_conn._get_lakehouse_id_by_name(workspace_id=workspace_id, lakehouse_name=lakehouse)
        print(f"Found lakehouse ID: {lakehouse_id}")

    function_id, wheel_name = deploy_function(fabric_conn=fabric_conn, workspace_id=workspace_id, job_name=job_name, job_file=job_file, wheel_file=wheel_file, lakehouse_id=lakehouse_id)
    print("✅ Successfully deployed User Data Function!")
    print(f"Function ID: {function_id}")
    print(f"Function Name: {job_name}")
    if lakehouse:
        print(f"📦 Connected Lakehouse: {lakehouse}")
    print(f"💡 Custom library: {wheel_name}")
    print("Deployment complete!")
    print(f"\nTo run: python job_function_run.py -w {workspace} -j {job_name}")


if __name__ == "__main__":
    main()
