#!/usr/bin/env python3
"""Inspect a deployed Fabric pipeline definition to verify externalService is set."""

import base64
import json
import os

import click
from azure.identity import ClientSecretCredential
from azure.identity import DefaultAzureCredential

from tag_data_engineering.deployment.fabric_connection import FabricConnection


@click.command()
@click.option("--workspace", "-w", required=True, help="Fabric workspace name")
@click.option("--pipeline", "-p", required=True, help="Pipeline name to inspect")
def main(workspace: str, pipeline: str) -> None:
    tenant_id = os.getenv("APP_TENANT_ID")
    client_id = os.getenv("APP_ID")
    client_secret = os.getenv("APP_CLIENT_SECRET")

    if tenant_id and client_id and client_secret:
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )
    else:
        credential = DefaultAzureCredential()

    fabric_conn = FabricConnection(credential=credential)
    workspace_id = fabric_conn._get_workspace_id_by_name(workspace_name=workspace)
    pipeline_id = fabric_conn.find_pipeline(workspace_id, pipeline)
    if not pipeline_id:
        print(f"Pipeline '{pipeline}' not found")
        return

    response = fabric_conn._request(
        method="POST",
        url=f"{fabric_conn.BASE_URL}/workspaces/{workspace_id}/items/{pipeline_id}/getDefinition",
    )
    result = response.json()
    for part in result.get("definition", {}).get("parts", []):
        if part.get("path") == "pipeline-content.json":
            payload = json.loads(base64.b64decode(part["payload"]).decode())
            activities = payload.get("properties", {}).get("activities", [])
            print(f"Pipeline: {pipeline} ({pipeline_id})")
            print(f"Activities: {len(activities)}")
            print("-" * 60)
            for act in activities:
                name = act.get("name", "?")
                act_type = act.get("type", "?")
                ext_svc = act.get("externalService")
                if ext_svc:
                    print(f"  ✅ {name} ({act_type}) -> externalService.connectionId = {ext_svc.get('connectionId')}")
                else:
                    print(f"  ❌ {name} ({act_type}) -> NO externalService")


if __name__ == "__main__":
    main()
