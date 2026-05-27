#!/usr/bin/env python3
import json
import time

import click
import requests
from azure.identity import DefaultAzureCredential

from tag_data_engineering.deployment.fabric_connection import FabricConnection


BASE_URL = "https://api.fabric.microsoft.com/v1"


def submit_job(workspace_id: str, job_id: str, headers: dict[str, str], command_line_args: str | None = None) -> str:
    url = f"{BASE_URL}/workspaces/{workspace_id}/items/{job_id}/jobs/instances?jobType=sparkjob"

    body = {}
    if command_line_args:
        body = {"executionData": {"commandLineArguments": command_line_args}}

    print(f"POST {url}")
    if body:
        print(f"Body: {json.dumps(body)}")

    resp = requests.post(url=url, headers=headers, json=body)
    resp.raise_for_status()

    location = resp.headers.get("Location") or resp.headers.get("location")
    if not location or "/jobs/instances/" not in location:
        raise RuntimeError(f"Cannot parse job instance ID from Location header: {location}")

    job_instance_id = location.split("/jobs/instances/")[-1].split("?")[0]
    print(f"Location: {location}")
    print("✅ Job submitted successfully!")
    print(f"Job Instance ID: {job_instance_id}")

    return job_instance_id


def get_spark_diagnostics(workspace_id: str, job_id: str, job_instance_id: str, headers: dict[str, str]) -> None:
    """Display Spark job diagnostic information and direct link to view logs in Fabric Portal."""
    print("\n" + "=" * 80)
    print("SPARK JOB DIAGNOSTICS")
    print("=" * 80)

    try:
        # Get Livy sessions
        livy_url = f"{BASE_URL}/workspaces/{workspace_id}/sparkJobDefinitions/{job_id}/livySessions"
        resp = requests.get(livy_url, headers=headers)

        if resp.status_code != 200:
            print("\nUnable to fetch session details")
            print("\nVIEW JOB IN FABRIC PORTAL:")
            print(f"   https://app.fabric.microsoft.com/groups/{workspace_id}/sparkjobdefinitions/{job_id}")
            return

        sessions = resp.json().get("sessions", resp.json().get("value", []))

        if not sessions:
            print("\nNo session information available")
            print("\nVIEW JOB IN FABRIC PORTAL:")
            print(f"   https://app.fabric.microsoft.com/groups/{workspace_id}/sparkjobdefinitions/{job_id}")
            return

        # Get the most recent session
        session = sessions[0]
        livy_id = session.get("livyId") or session.get("id")
        spark_app_id = session.get("sparkApplicationId")
        state = session.get("state")

        # Get detailed session info
        session_detail_url = f"{BASE_URL}/workspaces/{workspace_id}/sparkJobDefinitions/{job_id}/livySessions/{livy_id}"
        session_resp = requests.get(session_detail_url, headers=headers)

        if session_resp.status_code == 200:
            session_detail = session_resp.json()

            print(f"\nSession: {livy_id}")
            print(f"   Application: {spark_app_id}")
            print(f"   State: {state}")
            print(f"   Runtime: {session_detail.get('runtimeVersion')}")
            print(f"\nDuration: {session_detail.get('totalDuration', {}).get('value')} {session_detail.get('totalDuration', {}).get('timeUnit', '')}")
            print(f"   Queued: {session_detail.get('queuedDuration', {}).get('value')}s")
            print(f"   Running: {session_detail.get('runningDuration', {}).get('value')}s")
            print("\nResources:")
            print(f"   Driver: {session_detail.get('driverCores')} cores, {session_detail.get('driverMemory')}")
            print(f"   Executor: {session_detail.get('executorCores')} cores, {session_detail.get('executorMemory')}")
            print(f"   Executors: {session_detail.get('numExecutors')} (max: {session_detail.get('dynamicAllocationMaxExecutors')})")

        # Construct portal URL for detailed logs and Spark UI
        # Tenant ID is known from workspace context
        tenant_id = "b3b5c005-2c13-4fcc-8eb8-8cc6b0854bee"

        print(f"\n{'─' * 80}")
        print("\nVIEW DETAILED LOGS & SPARK UI:")
        portal_url = f"https://app.powerbi.com/workloads/de-ds/monitor/{job_id}/{livy_id}?ctid={tenant_id}&experience=fabric-developer"
        print(f"   {portal_url}")
        print("\n" + "=" * 80)

    except Exception as e:
        print(f"\nError retrieving diagnostics: {e}")
        print("\nVIEW JOB IN FABRIC PORTAL:")
        print(f"   https://app.fabric.microsoft.com/groups/{workspace_id}/sparkjobdefinitions/{job_id}")


def monitor_job(workspace_id: str, job_id: str, job_instance_id: str, headers: dict[str, str], poll_interval: int, timeout_seconds: int) -> str:
    url = f"{BASE_URL}/workspaces/{workspace_id}/items/{job_id}/jobs/instances/{job_instance_id}"
    print(f"\nMonitoring job instance: {job_instance_id}")
    print(f"Polling {url}\n")

    deadline = time.time() + timeout_seconds
    last_status = None

    while time.time() < deadline:
        resp = requests.get(url=url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        status = data.get("status", "Unknown")
        if status != last_status:
            print(f"Status: {status}")
            if "startTimeUtc" in data:
                print(f"  Started: {data['startTimeUtc']}")
            if "endTimeUtc" in data:
                print(f"  Ended: {data['endTimeUtc']}")
            if "failureReason" in data and data["failureReason"]:
                print(f"  Failure: {json.dumps(data['failureReason'], indent=2)}")
            last_status = status

        if status in ("Completed", "Failed", "Cancelled", "Deduped"):
            print(f"\n✅ Job finished with status: {status}")
            return status

        time.sleep(poll_interval)

    print("\n⏱️ Monitoring timeout reached")
    return "Timeout"


@click.command()
@click.option("--workspace", "-w", required=True, help="Fabric workspace name")
@click.option("--job-name", "-j", required=True, help="Spark job name to run")
@click.option("--args", "-a", help="Command-line arguments to pass to the job")
@click.option("--no-monitor", is_flag=True, help="Submit and exit without monitoring")
@click.option("--poll-interval", default=5, help="Seconds between status checks")
@click.option("--timeout", default=6000, help="Maximum seconds to monitor")
def main(workspace: str, job_name: str, args: str | None, no_monitor: bool, poll_interval: int, timeout: int) -> None:
    print(f"🚀 Running Spark Job: {job_name}")
    print(f"📁 Workspace: {workspace}")
    if args:
        print(f"📋 Arguments: {args}")
    print()

    credential = DefaultAzureCredential()
    fabric_conn = FabricConnection(credential=credential)

    print(f"Finding workspace: {workspace}")
    workspace_id = fabric_conn._get_workspace_id_by_name(workspace_name=workspace)
    print(f"Found workspace ID: {workspace_id}")

    job_id = fabric_conn._get_spark_job_id_by_name(workspace_id=workspace_id, job_name=job_name)

    headers = fabric_conn._get_api_headers()
    job_instance_id = submit_job(workspace_id=workspace_id, job_id=job_id, headers=headers, command_line_args=args)

    if no_monitor:
        print(f"\n✅ Job submitted! Instance ID: {job_instance_id}")
        print("Monitor in Fabric portal or re-run without --no-monitor")
        return

    status = monitor_job(workspace_id=workspace_id, job_id=job_id, job_instance_id=job_instance_id, headers=headers, poll_interval=poll_interval, timeout_seconds=timeout)

    # Display diagnostic info and portal link
    get_spark_diagnostics(workspace_id=workspace_id, job_id=job_id, job_instance_id=job_instance_id, headers=headers)

    if status == "Completed":
        print("\n✅ Job completed successfully!")
    elif status == "Failed":
        print("\n❌ Job failed!")
    elif status == "Cancelled":
        print("\n⚠️ Job was cancelled")
    elif status == "Timeout":
        print("\n⏱️ Monitoring timeout - job may still be running")
    else:
        print(f"\n⚠️ Job finished with status: {status}")


if __name__ == "__main__":
    main()
