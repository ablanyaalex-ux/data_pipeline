#!/usr/bin/env python3
"""Run a Fabric Data Pipeline.

This script triggers a pipeline run and optionally monitors it until completion.

Usage:
    python scripts/pipeline_run.py -w TAG_Prod_DE -p data_pipeline_orchestrator
    python scripts/pipeline_run.py -w TAG_Prod_DE -p data_pipeline_orchestrator --no-monitor
"""

import json
import os
import time

import click
import requests
from azure.identity import ClientSecretCredential
from azure.identity import DefaultAzureCredential

from tag_data_engineering.deployment.fabric_connection import FabricConnection


BASE_URL = "https://api.fabric.microsoft.com/v1"


def submit_pipeline(workspace_id: str, pipeline_id: str, headers: dict[str, str]) -> str:
    """Submit a pipeline for execution.

    Args:
        workspace_id: Fabric workspace ID
        pipeline_id: Pipeline item ID
        headers: API headers with auth token

    Returns:
        Job instance ID for monitoring
    """
    url = f"{BASE_URL}/workspaces/{workspace_id}/items/{pipeline_id}/jobs/instances?jobType=Pipeline"

    print(f"POST {url}")

    resp = requests.post(url=url, headers=headers)
    resp.raise_for_status()

    location = resp.headers.get("Location") or resp.headers.get("location")
    if not location or "/jobs/instances/" not in location:
        raise RuntimeError(f"Cannot parse job instance ID from Location header: {location}")

    job_instance_id = location.split("/jobs/instances/")[-1].split("?")[0]
    print(f"Location: {location}")
    print("✅ Pipeline submitted successfully!")
    print(f"Job Instance ID: {job_instance_id}")

    return job_instance_id


def monitor_pipeline(
    workspace_id: str,
    pipeline_id: str,
    job_instance_id: str,
    headers: dict[str, str],
    poll_interval: int,
    timeout_seconds: int,
) -> str:
    """Monitor a pipeline run until completion.

    Args:
        workspace_id: Fabric workspace ID
        pipeline_id: Pipeline item ID
        job_instance_id: Job instance ID to monitor
        headers: API headers with auth token
        poll_interval: Seconds between status checks
        timeout_seconds: Maximum time to wait

    Returns:
        Final status string
    """
    url = f"{BASE_URL}/workspaces/{workspace_id}/items/{pipeline_id}/jobs/instances/{job_instance_id}"
    portal_url = get_pipeline_portal_url(workspace_id, pipeline_id, job_instance_id)

    print(f"\nMonitoring pipeline instance: {job_instance_id}")
    print(f"Portal URL: {portal_url}")
    print()

    deadline = time.time() + timeout_seconds
    last_status = None
    consecutive_errors = 0
    max_consecutive_errors = 10  # Increased tolerance

    # Wait longer for the job to be registered in the API
    print("Waiting 30s for job to initialize in Fabric...")
    time.sleep(30)

    while time.time() < deadline:
        try:
            resp = requests.get(url=url, headers=headers)

            # Handle NotFound - the job may not be registered yet
            if resp.status_code == 404:
                consecutive_errors += 1
                if consecutive_errors <= max_consecutive_errors:
                    print(f"  API not ready yet (attempt {consecutive_errors}/{max_consecutive_errors}), waiting...")
                    time.sleep(poll_interval)
                    continue
                else:
                    print(f"\n⚠️ API monitoring unavailable after {max_consecutive_errors} attempts")
                    print("The pipeline is likely still running - check the portal:")
                    print(f"  {portal_url}")
                    return "MonitoringUnavailable"

            resp.raise_for_status()
            consecutive_errors = 0  # Reset on success
            data = resp.json()

            status = data.get("status", "Unknown")
            start_time = data.get("startTimeUtc", "")
            end_time = data.get("endTimeUtc", "")

            # Calculate elapsed time
            elapsed_str = ""
            if start_time:
                try:
                    from datetime import datetime
                    from datetime import timezone

                    start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                    now = datetime.now(timezone.utc)
                    elapsed = (now - start_dt).total_seconds()
                    mins, secs = divmod(int(elapsed), 60)
                    elapsed_str = f" (elapsed: {mins}m {secs}s)"
                except Exception:
                    pass

            if status != last_status:
                print(f"Status: {status}{elapsed_str}")
                if start_time:
                    print(f"  Started: {start_time}")
                if end_time:
                    print(f"  Ended: {end_time}")
                if "failureReason" in data and data["failureReason"]:
                    print(f"  Failure: {json.dumps(data['failureReason'], indent=2)}")
                last_status = status
            else:
                # Same status, just show elapsed time
                print(f"  Still {status}...{elapsed_str}")

            if status in ("Completed", "Failed", "Cancelled", "Deduped"):
                print(f"\n✅ Pipeline finished with status: {status}")
                return status

        except requests.exceptions.HTTPError as e:
            consecutive_errors += 1
            print(f"  HTTP error: {e}")
            if consecutive_errors > max_consecutive_errors:
                print("\n⚠️ Too many errors, stopping monitor")
                return "Error"

        time.sleep(poll_interval)

    print("\n⏱️ Monitoring timeout reached")
    return "Timeout"


def get_pipeline_portal_url(workspace_id: str, pipeline_id: str, job_instance_id: str | None = None) -> str:
    """Get the Power BI portal URL to view the pipeline run.

    Args:
        workspace_id: Fabric workspace ID
        pipeline_id: Pipeline item ID
        job_instance_id: Optional job instance ID for specific run

    Returns:
        Portal URL for viewing the pipeline
    """
    # Use the powerbi.com URL format which works better for pipeline runs
    if job_instance_id:
        return f"https://app.powerbi.com/workloads/data-pipeline/artifactAuthor/workspaces/{workspace_id}/pipelines/{pipeline_id}/{job_instance_id}?experience=power-bi"
    return f"https://app.powerbi.com/workloads/data-pipeline/artifactAuthor/workspaces/{workspace_id}/pipelines/{pipeline_id}?experience=power-bi"


@click.command()
@click.option("--workspace", "-w", required=True, help="Fabric workspace name")
@click.option("--pipeline", "-p", required=True, help="Pipeline name to run")
@click.option("--no-monitor", is_flag=True, help="Submit and exit without monitoring")
@click.option("--poll-interval", default=10, help="Seconds between status checks (default: 10)")
@click.option("--timeout", default=3600, help="Maximum seconds to monitor (default: 3600)")
def main(workspace: str, pipeline: str, no_monitor: bool, poll_interval: int, timeout: int) -> None:
    """Run a Fabric Data Pipeline."""
    print("=" * 80)
    print("PIPELINE RUN")
    print("=" * 80)
    print(f"Workspace: {workspace}")
    print(f"Pipeline: {pipeline}")
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

    print(f"Finding workspace: {workspace}")
    workspace_id = fabric_conn._get_workspace_id_by_name(workspace_name=workspace)
    print(f"Found workspace ID: {workspace_id}")

    # Find pipeline by name
    print(f"Finding pipeline: {pipeline}")
    headers = fabric_conn._get_api_headers()
    pipelines_url = f"{BASE_URL}/workspaces/{workspace_id}/items?type=DataPipeline"
    resp = requests.get(pipelines_url, headers=headers)
    resp.raise_for_status()

    pipeline_id = None
    for item in resp.json().get("value", []):
        if item["displayName"] == pipeline:
            pipeline_id = item["id"]
            break

    if not pipeline_id:
        raise click.ClickException(f"Pipeline '{pipeline}' not found in workspace '{workspace}'")

    print(f"Found pipeline ID: {pipeline_id}")
    print()

    # Submit pipeline
    job_instance_id = submit_pipeline(workspace_id=workspace_id, pipeline_id=pipeline_id, headers=headers)

    # Show portal link
    portal_url = get_pipeline_portal_url(workspace_id, pipeline_id, job_instance_id)
    print("\nView in Power BI Portal:")
    print(f"  {portal_url}")

    if no_monitor:
        print(f"\n✅ Pipeline submitted! Instance ID: {job_instance_id}")
        print("Monitor in Fabric portal or re-run without --no-monitor")
        return

    status = monitor_pipeline(
        workspace_id=workspace_id,
        pipeline_id=pipeline_id,
        job_instance_id=job_instance_id,
        headers=headers,
        poll_interval=poll_interval,
        timeout_seconds=timeout,
    )

    print()
    print("=" * 80)
    if status == "Completed":
        print("✅ Pipeline completed successfully!")
    elif status == "Failed":
        print("❌ Pipeline failed!")
        print(f"\nView details: {portal_url}")
    elif status == "Cancelled":
        print("⚠️ Pipeline was cancelled")
    elif status in ("Timeout", "MonitoringUnavailable"):
        print("ℹ️  Pipeline was submitted successfully")
        print("    API monitoring is unavailable - the pipeline may still be running.")
        print(f"\nView status in portal: {portal_url}")
    else:
        print(f"ℹ️  Pipeline status: {status}")
        print(f"\nView in portal: {portal_url}")
    print("=" * 80)


if __name__ == "__main__":
    main()
