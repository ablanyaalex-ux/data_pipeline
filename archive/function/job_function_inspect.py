"""Inspect a User Data Function definition."""

import base64
import json
import time

import click
import requests
from azure.identity import DefaultAzureCredential

from tag_data_engineering.deployment.fabric_connection import FabricConnection


BASE_URL = "https://api.fabric.microsoft.com/v1"


def inspect_function(fabric_conn: FabricConnection, workspace_id: str, function_name: str) -> None:
    """Inspect a User Data Function."""
    headers = fabric_conn._get_api_headers()

    # Find function
    print(f"Looking for function: {function_name}")
    response = requests.get(f"{BASE_URL}/workspaces/{workspace_id}/items?type=UserDataFunction", headers=headers)
    response.raise_for_status()

    function_id = None
    for item in response.json()["value"]:
        if item["displayName"] == function_name:
            function_id = item["id"]
            break

    if not function_id:
        raise RuntimeError(f"Function '{function_name}' not found")

    print(f"Found function ID: {function_id}")

    # Get function definition using the correct endpoint
    print("\nGetting function definition...")
    response = requests.post(f"{BASE_URL}/workspaces/{workspace_id}/UserDataFunctions/{function_id}/getDefinition", headers=headers, json={})

    print(f"Response status: {response.status_code}")

    if response.status_code == 202:
        location = response.headers.get("Location", "")
        if "/operations/" in location:
            operation_id = location.split("/operations/")[-1]
            print(f"⏳ Waiting for definition retrieval (operation: {operation_id})...")

            for _ in range(30):
                time.sleep(2)
                op_resp = requests.get(f"{BASE_URL}/operations/{operation_id}", headers=headers)
                op_resp.raise_for_status()
                op_result = op_resp.json()
                status = op_result.get("status", "")

                if status == "Succeeded":
                    print("✅ Definition retrieved successfully!")

                    # Get result from operation
                    result_url = f"{BASE_URL}/operations/{operation_id}/result"
                    result_resp = requests.get(result_url, headers=headers)
                    result_resp.raise_for_status()
                    definition = result_resp.json()

                    # Check for definition parts
                    if definition and "definition" in definition and "parts" in definition["definition"]:
                        for part in definition["definition"]["parts"]:
                            path = part.get("path", "")

                            if path == "definition.json":
                                print("\n" + "=" * 80)
                                print("DEFINITION.JSON")
                                print("=" * 80)
                                payload = base64.b64decode(part["payload"]).decode()
                                definition_json = json.loads(payload)
                                print(json.dumps(definition_json, indent=2))

                                # Highlight connected data sources
                                if "connectedDataSources" in definition_json:
                                    print("\n" + "=" * 80)
                                    print("CONNECTED DATA SOURCES")
                                    print("=" * 80)
                                    if definition_json["connectedDataSources"]:
                                        for conn in definition_json["connectedDataSources"]:
                                            print(f"\n  Alias: {conn.get('alias', 'N/A')}")
                                            print(f"  Artifact Type: {conn.get('artifactType', 'N/A')}")
                                            print(f"  Artifact ID: {conn.get('artifactId', 'N/A')}")
                                            print(f"  Workspace ID: {conn.get('workspaceId', 'N/A')}")
                                    else:
                                        print("⚠️  NO CONNECTED DATA SOURCES FOUND!")

                            elif path == "function_app.py":
                                print("\n" + "=" * 80)
                                print("FUNCTION_APP.PY (DEPLOYED CODE)")
                                print("=" * 80)
                                payload = base64.b64decode(part["payload"]).decode()
                                print(payload)

                            elif path == ".resources/functions.json":
                                print("\n" + "=" * 80)
                                print("FUNCTIONS.JSON")
                                print("=" * 80)
                                payload = base64.b64decode(part["payload"]).decode()
                                functions_json = json.loads(payload)
                                print(json.dumps(functions_json, indent=2))

                            elif path.startswith("privateLibraries/"):
                                print(f"\n  📦 Found library: {path}")
                    break
                elif status == "Failed":
                    print(f"❌ Failed to get definition: {json.dumps(op_result, indent=2)}")
                    break


@click.command()
@click.option("--workspace", "-w", required=True, help="Fabric workspace name")
@click.option("--function-name", "-f", required=True, help="Function name to inspect")
def main(workspace: str, function_name: str) -> None:
    """Inspect a User Data Function."""
    print(f"Inspecting function in workspace: {workspace}")

    credential = DefaultAzureCredential()
    fabric_conn = FabricConnection(credential=credential)

    workspace_id = fabric_conn._get_workspace_id_by_name(workspace_name=workspace)
    print(f"Workspace ID: {workspace_id}")

    inspect_function(fabric_conn, workspace_id, function_name)


if __name__ == "__main__":
    main()
