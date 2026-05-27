import base64
import json
import time
from pathlib import Path

import requests
from azure.core.credentials import TokenCredential


class FabricConnection:
    BASE_URL = "https://api.fabric.microsoft.com/v1"

    def __init__(
        self,
        credential: TokenCredential,
    ) -> None:
        self.credential = credential
        self.access_token: str | None = None
        self.storage_token: str | None = None

    def _get_access_token(self) -> str:
        if self.access_token is not None:
            return self.access_token
        access_token = self.credential.get_token("https://api.fabric.microsoft.com/.default").token
        return access_token

    def _get_storage_token(self) -> str:
        if self.storage_token is not None:
            return self.storage_token
        storage_token = self.credential.get_token("https://storage.azure.com/.default").token
        self.storage_token = storage_token
        return storage_token

    def _get_api_headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json",
        }
        return headers

    def _request(
        self,
        method: str,
        url: str,
        json: dict | None = None,
        params: dict | None = None,
        files: dict | None = None,
        overwrite_headers: dict | None = None,
        max_retries: int = 5,
    ) -> requests.Response:
        headers = self._get_api_headers()
        if overwrite_headers:
            headers.update(overwrite_headers)
        base_delay = 1  # Start with 1 second
        max_delay = 60  # Cap at 60 seconds
        for attempt in range(max_retries + 1):
            response = requests.request(method, url, headers=headers, json=json, params=params, files=files)
            if response.status_code < 400:
                return response
            if response.status_code == 429 and attempt < max_retries:
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    try:
                        delay = int(retry_after)
                    except ValueError:
                        delay = min(base_delay * (2**attempt), max_delay)
                else:
                    # Exponential backoff: 1s, 2s, 4s, 8s, 16s, 32s, 60s (capped)
                    delay = min(base_delay * (2**attempt), max_delay)
                print(f"Rate limited (429). Retrying in {delay}s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(delay)
                continue
            # Print detailed error info before raising
            if response.status_code >= 400:
                print(f"❌ HTTP {response.status_code} Error")
                print(f"   URL: {url}")
                try:
                    error_detail = response.json()
                    print(f"   Error details: {error_detail}")
                except Exception:
                    print(f"   Response text: {response.text}")
            response.raise_for_status()
        raise Exception(f"Failed to complete request after {max_retries} attempts")

    def _get_workspace_id_by_name(self, workspace_name: str) -> str:
        response = self._request(method="GET", url=f"{self.BASE_URL}/workspaces")
        for workspace in response.json()["value"]:
            if workspace["displayName"] == workspace_name:
                return workspace["id"]
        raise RuntimeError(f"Workspace '{workspace_name}' not found")

    def _get_lakehouse_id_by_name(self, workspace_id: str, lakehouse_name: str) -> str:
        response = self._request(method="GET", url=f"{self.BASE_URL}/workspaces/{workspace_id}/items?type=Lakehouse")
        for item in response.json()["value"]:
            if item["displayName"] == lakehouse_name:
                return item["id"]
        raise RuntimeError(f"Lakehouse '{lakehouse_name}' not found in workspace")

    def _get_sql_endpoint_id_by_lakehouse_name(self, workspace_id: str, lakehouse_name: str) -> str:
        response = self._request(method="GET", url=f"{self.BASE_URL}/workspaces/{workspace_id}/items?type=SQLEndpoint")
        for item in response.json()["value"]:
            if item["displayName"] == lakehouse_name:
                return item["id"]
        raise RuntimeError(f"SQL Endpoint for lakehouse '{lakehouse_name}' not found in workspace")

    def get_connection_id_by_name(self, connection_name: str) -> str:
        response = self._request(method="GET", url=f"{self.BASE_URL}/connections")
        for connection in response.json()["value"]:
            if connection["displayName"] == connection_name:
                return connection["id"]
        raise RuntimeError(f"Connection '{connection_name}' not found")

    def _get_environment_id_by_name(self, workspace_id: str, environment_name: str) -> str:
        response = self._request(method="GET", url=f"{self.BASE_URL}/workspaces/{workspace_id}/items?type=Environment")
        for item in response.json()["value"]:
            if item["displayName"] == environment_name:
                return item["id"]
        raise RuntimeError(f"Environment '{environment_name}' not found")

    def _get_spark_job_id_by_name(self, workspace_id: str, job_name: str) -> str:
        response = self._request(method="GET", url=f"{self.BASE_URL}/workspaces/{workspace_id}/items?type=SparkJobDefinition")
        for job in response.json()["value"]:
            if job["displayName"] == job_name:
                return job["id"]
        raise RuntimeError(f"Spark Job Definition '{job_name}' not found")

    def _publish_environment(self, workspace_id: str, environment_id: str) -> None:
        self._request(method="POST", url=f"{self.BASE_URL}/workspaces/{workspace_id}/environments/{environment_id}/staging/publish")

    def _wait_for_environment_publish(self, workspace_id: str, environment_id: str) -> None:
        while True:
            time.sleep(1)
            response = self._request(method="GET", url=f"{self.BASE_URL}/workspaces/{workspace_id}/environments/{environment_id}")
            state = response.json().get("properties", {}).get("publishDetails", {}).get("state", "Unknown")
            if state == "Success":
                break
            if state in ["Failed", "Error"]:
                raise RuntimeError(f"Environment publish failed with state: {state}")

    def get_schema_path(self, workspace_name: str, lakehouse_name: str, schema_name: str) -> str:
        workspace_id = self._get_workspace_id_by_name(workspace_name=workspace_name)
        lakehouse_id = self._get_lakehouse_id_by_name(workspace_id=workspace_id, lakehouse_name=lakehouse_name)
        table_path = f"abfss://{workspace_id}@onelake.dfs.fabric.microsoft.com/{lakehouse_id}/Tables/{schema_name}"
        return table_path

    def list_workspaces(self) -> list[str]:
        response = self._request(method="GET", url=f"{self.BASE_URL}/workspaces")
        return [workspace["displayName"] for workspace in response.json()["value"]]

    def list_lakehouses(self, workspace_name: str) -> list[str]:
        workspace_id = self._get_workspace_id_by_name(workspace_name)
        response = self._request(method="GET", url=f"{self.BASE_URL}/workspaces/{workspace_id}/items?type=Lakehouse")
        return [item["displayName"] for item in response.json()["value"]]

    def find_copyjob(self, workspace_id: str, copyjob_name: str) -> dict | None:
        resp = self._request(method="GET", url=f"{self.BASE_URL}/workspaces/{workspace_id}/items?type=CopyJob")
        for item in resp.json().get("value", []):
            if item["displayName"] == copyjob_name:
                return item
        return None

    def get_copyjob_definition(self, workspace_id: str, copyjob_id: str) -> dict:
        """Get the full definition of a CopyJob."""
        response = self._request(
            method="POST",
            url=f"{self.BASE_URL}/workspaces/{workspace_id}/items/{copyjob_id}/getDefinition",
        )
        result = response.json()
        # Decode the base64 payload
        if "definition" in result and "parts" in result["definition"]:
            for part in result["definition"]["parts"]:
                if part.get("path") == "copyjob-content.json":
                    payload_b64 = part.get("payload", "")
                    payload_json = base64.b64decode(payload_b64).decode("utf-8")
                    return json.loads(payload_json)
        return result

    def create_copyjob(self, workspace_id: str, copyjob_name: str, copyjob_definition: dict) -> str:
        print(f"Creating CopyJob: {copyjob_name}")
        payload = {
            "displayName": copyjob_name,
            "type": "CopyJob",
            "definition": {
                "parts": [
                    {
                        "path": "copyjob-content.json",
                        "payload": base64.b64encode(json.dumps(copyjob_definition).encode()).decode(),
                        "payloadType": "InlineBase64",
                    },
                ],
            },
        }
        # Debug: print the copyjob definition
        print(f"   CopyJob definition preview: {json.dumps(copyjob_definition, indent=2)[:500]}...")
        resp = self._request(method="POST", url=f"{self.BASE_URL}/workspaces/{workspace_id}/items", json=payload)
        result = resp.json()
        copyjob_id = result.get("id")
        print(f"✅ Created CopyJob: {copyjob_name} (ID: {copyjob_id})")
        return copyjob_id

    def update_copyjob(self, workspace_id: str, copyjob_id: str, copyjob_name: str, copyjob_definition: dict) -> None:
        print(f"Updating CopyJob: {copyjob_name}")
        payload = {
            "definition": {
                "parts": [
                    {
                        "path": "copyjob-content.json",
                        "payload": base64.b64encode(json.dumps(copyjob_definition).encode()).decode(),
                        "payloadType": "InlineBase64",
                    },
                ],
            },
        }
        self._request(method="POST", url=f"{self.BASE_URL}/workspaces/{workspace_id}/items/{copyjob_id}/updateDefinition", json=payload)
        print(f"✅ Updated CopyJob: {copyjob_name}")

    def find_pipeline(self, workspace_id: str, pipeline_name: str) -> str | None:
        resp = self._request(method="GET", url=f"{self.BASE_URL}/workspaces/{workspace_id}/items?type=DataPipeline")
        for item in resp.json().get("value", []):
            if item["displayName"] == pipeline_name:
                print(f"Found existing pipeline: {pipeline_name} (ID: {item['id']})")
                return item["id"]
        return None

    def create_pipeline(self, workspace_id: str, pipeline_name: str) -> str:
        print(f"Creating new pipeline: {pipeline_name}")
        payload = {
            "displayName": pipeline_name,
            "type": "DataPipeline",
        }
        resp = self._request(method="POST", url=f"{self.BASE_URL}/workspaces/{workspace_id}/items", json=payload)
        pipeline_id = resp.json()["id"]
        print(f"Created pipeline: {pipeline_id}")
        return pipeline_id

    def update_pipeline_definition(
        self,
        workspace_id: str,
        pipeline_id: str,
        fabric_json: dict,
        schedule_config: dict | None = None,
    ) -> None:
        print("Updating pipeline definition...")
        parts = [
            {
                "path": "pipeline-content.json",
                "payload": base64.b64encode(json.dumps(fabric_json).encode()).decode(),
                "payloadType": "InlineBase64",
            },
        ]
        # Add schedule if provided
        if schedule_config:
            schedule_payload = {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/schedules/1.0.0/schema.json",
                "schedules": [schedule_config],
            }
            parts.append(
                {
                    "path": ".schedules",
                    "payload": base64.b64encode(json.dumps(schedule_payload).encode()).decode(),
                    "payloadType": "InlineBase64",
                }
            )
            print(f"  Including schedule: {schedule_config['configuration']['type']} at {schedule_config['configuration'].get('times', ['N/A'])[0]}")

        payload = {
            "definition": {
                "parts": parts,
            },
        }
        self._request(method="POST", url=f"{self.BASE_URL}/workspaces/{workspace_id}/items/{pipeline_id}/updateDefinition", json=payload)
        print("Pipeline definition updated successfully")

    def find_notebook(self, workspace_id: str, notebook_name: str) -> str | None:
        resp = self._request(method="GET", url=f"{self.BASE_URL}/workspaces/{workspace_id}/items?type=Notebook")
        for item in resp.json().get("value", []):
            if item["displayName"] == notebook_name:
                print(f"Found existing notebook: {notebook_name} (ID: {item['id']})")
                return item["id"]
        return None

    def create_notebook(self, workspace_id: str, notebook_name: str) -> str:
        print(f"Creating new Notebook: {notebook_name}")
        payload = {
            "displayName": notebook_name,
            "type": "Notebook",
        }
        resp = self._request(method="POST", url=f"{self.BASE_URL}/workspaces/{workspace_id}/items", json=payload)
        notebook_id = resp.json()["id"]
        print(f"Created Notebook: {notebook_id}")
        return notebook_id

    def update_notebook_definition(self, workspace_id: str, notebook_id: str, notebook_content: dict) -> None:
        print("Updating notebook definition...")
        notebook_json = json.dumps(notebook_content, indent=2)
        notebook_b64 = base64.b64encode(notebook_json.encode()).decode()
        payload = {
            "definition": {
                "format": "ipynb",
                "parts": [
                    {
                        "path": "notebook-content.ipynb",
                        "payload": notebook_b64,
                        "payloadType": "InlineBase64",
                    }
                ],
            },
        }
        try:
            self._request(method="POST", url=f"{self.BASE_URL}/workspaces/{workspace_id}/items/{notebook_id}/updateDefinition", json=payload)
            print("✅ Notebook definition updated")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code != 202:
                raise
            location = e.response.headers.get("Location", "")
            if location:
                print("  Waiting for update to complete...")
                for _ in range(60):
                    time.sleep(2)
                    poll_resp = self._request(method="GET", url=location)
                    result = poll_resp.json()
                    status = result.get("status", "")
                    if status == "Succeeded":
                        print("✅ Notebook definition updated")
                        return
                    elif status == "Failed":
                        error = result.get("error", {})
                        raise RuntimeError(f"Update failed: {error.get('message', 'Unknown error')}")  # noqa: B904
                raise RuntimeError("Timeout waiting for notebook update")  # noqa: B904

    def find_environment(self, workspace_id: str, environment_name: str) -> str:
        resp = self._request(method="GET", url=f"{self.BASE_URL}/workspaces/{workspace_id}/items?type=Environment")
        for item in resp.json().get("value", []):
            if item["displayName"] == environment_name:
                print(f"Found environment: {environment_name} (ID: {item['id']})")
                return item["id"]
        available = [item["displayName"] for item in resp.json().get("value", [])]
        raise ValueError(f"Environment '{environment_name}' not found. Available: {available}")

    def _wait_for_environment_ready(self, workspace_id: str, environment_id: str) -> None:
        while True:
            response = self._request(method="GET", url=f"{self.BASE_URL}/workspaces/{workspace_id}/environments/{environment_id}")
            state = response.json().get("properties", {}).get("publishDetails", {}).get("state", "Unknown")
            if state in ["Success", "Unknown"]:
                return
            if state in ["Failed", "Error"]:
                print(f"Warning: Environment in state '{state}', proceeding anyway...")
                return
            print(f"  Environment is in state '{state}', waiting...")
            time.sleep(5)

    def _delete_wheel_from_staging(self, workspace_id: str, environment_id: str, wheel_name: str) -> None:
        print(f"  Deleting: {wheel_name}")
        delete_url = f"{self.BASE_URL}/workspaces/{workspace_id}/environments/{environment_id}/staging/libraries"
        try:
            self._request(method="DELETE", url=delete_url, params={"libraryToDelete": wheel_name})
            print("    ✅ Deleted from staging")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print("    Wheel not found in staging (already deleted or never existed)")
            else:
                print(f"    Warning: Could not delete wheel (status {e.response.status_code})")

    def _upload_wheel_to_staging(self, workspace_id: str, environment_id: str, wheel_file: Path) -> None:
        print(f"Uploading wheel to staging: {wheel_file.name}")
        with open(wheel_file, "rb") as f:
            files = {"file": (wheel_file.name, f, "application/octet-stream")}
            self._request(
                method="POST",
                url=f"{self.BASE_URL}/workspaces/{workspace_id}/environments/{environment_id}/staging/libraries",
                files=files,
                overwrite_headers={"Content-Type": None},
            )
        print(f"✅ Successfully uploaded to staging: {wheel_file.name}")

    def deploy_wheel_to_environment(self, workspace_id: str, environment_id: str, wheel_file: Path, force: bool = False) -> None:
        print("\n" + "=" * 80)
        print("DEPLOYING WHEEL TO ENVIRONMENT")
        print("=" * 80)
        published_wheels: list[str] = []
        try:
            resp = self._request(method="GET", url=f"{self.BASE_URL}/workspaces/{workspace_id}/environments/{environment_id}/libraries")
            published_wheels = resp.json().get("customLibraries", {}).get("wheelFiles", [])
        except requests.exceptions.HTTPError as e:
            if e.response.status_code != 404:
                raise
            # If libraries are not published yet, Fabric can return 404 for this endpoint.
            # Treat any 404 from this specific call as an empty published library list.
            print("No published libraries found yet in environment (first deployment).")
        if wheel_file.name in published_wheels and not force:
            print(f"✅ Wheel already published: {wheel_file.name}")
            print("   Skipping deployment (use force=True to redeploy)")
            return
        print("Checking environment state...")
        self._wait_for_environment_ready(workspace_id=workspace_id, environment_id=environment_id)
        try:
            resp = self._request(method="GET", url=f"{self.BASE_URL}/workspaces/{workspace_id}/environments/{environment_id}/staging/libraries")
            existing_wheels = resp.json().get("customLibraries", {}).get("wheelFiles", [])
        except requests.exceptions.HTTPError as e:
            if e.response.status_code != 404:
                raise
            existing_wheels = []
        if existing_wheels:
            print(f"Found {len(existing_wheels)} existing wheel(s) in staging - cleaning up...")
            for wheel_name in existing_wheels:
                self._delete_wheel_from_staging(workspace_id=workspace_id, environment_id=environment_id, wheel_name=wheel_name)
        else:
            print("No existing wheels in staging")
        self._upload_wheel_to_staging(workspace_id=workspace_id, environment_id=environment_id, wheel_file=wheel_file)
        print("Publishing environment to install custom library...")
        self._publish_environment(workspace_id=workspace_id, environment_id=environment_id)
        print("Waiting for environment to be ready... (this may take several minutes)")
        self._wait_for_environment_publish(workspace_id=workspace_id, environment_id=environment_id)
        print(f"✅ Environment updated with: {wheel_file.name}")

    def build_schedule_config(
        self,
        schedule_cron: str,
        timezone: str = "GMT Standard Time",
    ) -> dict:
        """Build schedule configuration for pipeline definition from cron expression.

        Args:
            schedule_cron: Cron expression (e.g., "0 6 * * *" for 6am daily)
            timezone: Windows timezone ID (e.g., "GMT Standard Time", "Pacific Standard Time")

        Returns:
            Schedule configuration dict that can be passed to update_pipeline_definition
        """
        from datetime import datetime
        from datetime import timedelta

        # Parse cron expression
        parts = schedule_cron.strip().split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: '{schedule_cron}'. Expected format: 'minute hour day month day-of-week'")

        minute, hour = int(parts[0]), int(parts[1])
        if not (0 <= minute <= 59):
            raise ValueError(f"Invalid minute: {minute}. Must be between 0 and 59.")
        if not (0 <= hour <= 23):
            raise ValueError(f"Invalid hour: {hour}. Must be between 0 and 23.")

        start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=365)

        time_str = f"{hour:02d}:{minute:02d}"

        return {
            "enabled": True,
            "jobType": "Execute",
            "configuration": {
                "type": "Daily",
                "startDateTime": start_date.strftime("%Y-%m-%dT%H:%M:%S"),
                "endDateTime": end_date.strftime("%Y-%m-%dT%H:%M:%S"),
                "localTimeZoneId": timezone,
                "times": [time_str],
            },
        }
