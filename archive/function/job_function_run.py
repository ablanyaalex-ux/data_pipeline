#!/usr/bin/env python3
import json
import re
import time
from datetime import datetime
from datetime import timezone

import click
import requests
from azure.identity import DefaultAzureCredential

from tag_data_engineering.deployment.fabric_connection import FabricConnection


BASE_URL = "https://api.fabric.microsoft.com/v1"


def get_function_id_by_name(fabric_conn: FabricConnection, workspace_id: str, function_name: str) -> str:
    headers = fabric_conn._get_api_headers()
    url = f"{BASE_URL}/workspaces/{workspace_id}/items?type=UserDataFunction"
    response = requests.get(url=url, headers=headers)
    response.raise_for_status()
    functions = response.json().get("value", [])
    function = next((f for f in functions if f["displayName"] == function_name), None)
    if not function:
        raise RuntimeError(f"User Data Function '{function_name}' not found in workspace")
    return function["id"]


def invoke_function(credential: DefaultAzureCredential, workspace_id: str, function_id: str, function_name: str, parameters: dict[str, str] | None = None) -> dict:
    """Invoke a UDF with exponential backoff retry for rate limiting."""
    powerbi_scope = "https://analysis.windows.net/powerbi/api/.default"
    workspace_clean = workspace_id.replace("-", "")
    url = f"https://{workspace_clean}.za6.userdatafunctions.fabric.microsoft.com/v1/workspaces/{workspace_id}/userDataFunctions/{function_id}/functions/{function_name}/invoke"
    body = parameters if parameters else {}

    print(f"Invoking function: {function_name}")

    # Exponential backoff parameters
    retry_count = 0
    base_delay = 2  # Start with 2 seconds
    max_delay = 300  # Cap at 5 minutes

    while True:
        token = credential.get_token(powerbi_scope).token
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        response = requests.post(url=url, headers=headers, json=body)
        result = response.json() if response.content else {}

        # Check for rate limiting (429)
        if response.status_code == 429:
            retry_count += 1
            delay = min(base_delay * (2 ** (retry_count - 1)), max_delay)

            # Try to extract the retry-after header
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    delay = int(retry_after)
                except ValueError:
                    pass

            # Check if there's a message with "blocked until" timestamp
            error_message = result.get("message", "")
            if "blocked by the upstream service until" in error_message.lower():
                # Parse the timestamp: "Request is blocked by the upstream service until: 10/28/2025 8:26:56 PM (UTC)"
                match = re.search(r"until:\s*(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}\s+[AP]M)", error_message)
                if match:
                    blocked_until_str = match.group(1)
                    try:
                        # Parse the timestamp
                        blocked_until = datetime.strptime(blocked_until_str, "%m/%d/%Y %I:%M:%S %p")
                        blocked_until = blocked_until.replace(tzinfo=timezone.utc)
                        now = datetime.now(timezone.utc)

                        # Calculate seconds until unblocked + 10 second buffer
                        seconds_until_unblocked = (blocked_until - now).total_seconds() + 10

                        if seconds_until_unblocked > 0:
                            delay = int(seconds_until_unblocked)
                            print(f"⏳ Rate limited until {blocked_until_str} UTC")
                            print(f"   Current time: {now.strftime('%m/%d/%Y %I:%M:%S %p')} UTC")
                            print(f"   Waiting {delay} seconds (with 10s buffer)...")
                        else:
                            print(f"⏳ Rate limit should have expired, retrying in {delay} seconds...")
                    except Exception as e:
                        print(f"⏳ Rate limited: {error_message}")
                        print(f"   Could not parse timestamp ({e}), using exponential backoff: {delay}s")
                else:
                    print(f"⏳ Rate limited: {error_message}")
                    print(f"   Using exponential backoff: {delay}s")
            else:
                print(f"⏳ Rate limited (429). Retry #{retry_count}")
                print(f"   Waiting {delay} seconds before retry...")

            time.sleep(delay)
            continue

        # If not rate limited, break out of retry loop
        break

    # Process the response
    status = result.get("status", "")
    print(f"Status: {status}")

    # Always show logs section if present
    logs = result.get("logs")
    if not logs and isinstance(result.get("output"), dict):
        logs = result.get("output", {}).get("logs")
    if logs:
        print("\n--- Function Logs ---")
        print(logs)
        print("--- End Logs ---\n")

    if result.get("errors"):
        print("❌ Errors:")
        for error in result.get("errors", []):
            print(f"  - {error.get('errorCode', 'Unknown')}: {error.get('message', 'No message')}")
            if error.get("properties"):
                print(f"    Properties: {json.dumps(error['properties'], indent=6)}")

    if result.get("output"):
        print(f"Output: {json.dumps(result['output'], indent=2)}")

    # Also print the full response for debugging if not succeeded
    if status != "Succeeded":
        print("\n--- Full Response ---")
        print(json.dumps(result, indent=2))
        print("--- End Response ---")

    if response.status_code != 200:
        print(f"\n❌ Failed to invoke function. Status code: {response.status_code}")
        response.raise_for_status()
    return result


def run_function(workspace: str, job_name: str, args: str | None = None) -> None:
    print(f"Running User Data Function: {job_name}")
    print(f"Workspace: {workspace}\n")
    credential = DefaultAzureCredential()
    fabric_conn = FabricConnection(credential=credential)
    print(f"Finding workspace: {workspace}")
    workspace_id = fabric_conn._get_workspace_id_by_name(workspace_name=workspace)
    print(f"Found workspace ID: {workspace_id}")
    function_id = get_function_id_by_name(fabric_conn=fabric_conn, workspace_id=workspace_id, function_name=job_name)
    print(f"Found function ID: {function_id}")
    parameters = None
    if args:
        parameters = json.loads(args)
    result = invoke_function(credential=credential, workspace_id=workspace_id, function_id=function_id, function_name=job_name, parameters=parameters)
    status = result.get("status", "")
    if status == "Succeeded":
        print("\n✅ Function completed successfully!")
    else:
        print(f"\n⚠️ Function finished with status: {status}")


@click.command()
@click.option("--workspace", "-w", required=True, help="Fabric workspace name")
@click.option("--job-name", "-j", required=True, help="Function name to run")
@click.option("--args", "-a", help="JSON string of parameters to pass to function")
def main(workspace: str, job_name: str, args: str | None) -> None:
    run_function(workspace=workspace, job_name=job_name, args=args)


if __name__ == "__main__":
    main()
