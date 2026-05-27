import contextlib
import logging

import requests
from notebookutils import mssparkutils  # type: ignore[import-not-found]
from pyspark.sql import SparkSession

from tag_data_engineering.connectors.lakehouse_connector import LakehouseConnector


logger = logging.getLogger(__name__)

FABRIC_API_BASE = "https://api.fabric.microsoft.com/v1"


class FabricLakehouseConnector(LakehouseConnector):
    def __init__(
        self,
        spark: SparkSession,
        base_path: str = "",
        workspace_id: str = "",
        sql_endpoint_id: str = "",
    ):
        super().__init__(spark, base_path)
        self.workspace_id = workspace_id
        self.sql_endpoint_id = sql_endpoint_id

    def get_files_path(self, entity: str, run_id: str | None = None) -> str:
        if run_id:
            return f"Files/{entity}/{run_id}/"
        return f"Files/{entity}/*/"

    def mkdirs(self, path: str) -> None:
        mssparkutils.fs.mkdirs(path)

    def write_file(self, path: str, content: str) -> None:
        mssparkutils.fs.put(path, content, overwrite=True)

    def delete_dir(self, path: str) -> None:
        mssparkutils.fs.rm(path, recurse=True)

    def path_exists(self, path: str) -> bool:
        with contextlib.suppress(Exception):
            mssparkutils.fs.ls(path)
            return True
        return False

    def list_dir(self, path: str) -> list[tuple[str, str]]:
        entries = mssparkutils.fs.ls(path)
        results: list[tuple[str, str]] = []
        for entry in entries:
            name = entry.name
            entry_path = entry.path
            if not name or not entry_path:
                raise ValueError(f"Invalid file entry for path '{path}': {entry}")
            results.append((str(name), str(entry_path)))
        return results

    def close(self) -> None:
        # NOTE(krishan711): we're using a shared spark session in Fabric, so don't stop it
        pass

    def refresh_sql_endpoint_metadata(self) -> None:
        if not self.workspace_id or not self.sql_endpoint_id:
            logger.warning("workspace_id and sql_endpoint_id are required to refresh SQL endpoint metadata, skipping")
            return
        token = mssparkutils.credentials.getToken("https://api.fabric.microsoft.com")
        response = requests.post(
            f"{FABRIC_API_BASE}/workspaces/{self.workspace_id}/sqlEndpoints/{self.sql_endpoint_id}/refreshMetadata",
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
        response.raise_for_status()
        logger.info("SQL endpoint metadata refresh triggered")
