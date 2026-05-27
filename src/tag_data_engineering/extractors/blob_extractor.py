import csv
import json
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from io import StringIO
from typing import Iterator

from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient
from pydantic import BaseModel

from tag_data_engineering.extractors.base_extractor import BaseExtractor
from tag_data_engineering.extractors.models import ExtractionBatch
from tag_data_engineering.models import ExtractionMetadata
from tag_data_engineering.secrets.secret_provider import SecretProvider


def _normalize_to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class BlobSourceConfig(BaseModel):
    source_container: str
    source_folder: str
    blob_account_url_keyvault: str
    file_encoding: str | None = None


@dataclass
class BlobStorageObjectInfo:
    object_name: str
    last_modified: datetime


class BlobSourceFactory:
    class _AzureBlobSource:
        def __init__(self, service_client):
            self._service_client = service_client

        def list_objects(self, container: str, prefix: str) -> list[BlobStorageObjectInfo]:
            container_client = self._service_client.get_container_client(container)
            return [BlobStorageObjectInfo(object_name=blob.name, last_modified=_normalize_to_utc(blob.last_modified)) for blob in container_client.list_blobs(name_starts_with=prefix)]

        def read_object(self, container: str, object_name: str) -> bytes:
            blob_client = self._service_client.get_blob_client(container=container, blob=object_name)
            return blob_client.download_blob().readall()

    def __init__(self, secret_provider: SecretProvider):
        self.secret_provider = secret_provider

    def build(self, config: BlobSourceConfig) -> _AzureBlobSource:
        blob_account_url_credentials = json.loads(self.secret_provider.get_secret(config.blob_account_url_keyvault))
        blob_account_url = f"https://{blob_account_url_credentials['account_name']}.blob.core.windows.net"
        sp_credentials = json.loads(self.secret_provider.get_secret("de-sp-credentials"))
        token_credential = ClientSecretCredential(
            tenant_id=self.secret_provider.get_secret("tenant-id"),
            client_id=sp_credentials["client_id"],
            client_secret=sp_credentials["client_secret"],
        )
        service_client = BlobServiceClient(account_url=blob_account_url, credential=token_credential)
        return self._AzureBlobSource(service_client)


class BlobCursor(BaseModel):
    last_modified: datetime | None = None
    last_object_name: str | None = None


class BlobExtractor(BaseExtractor):
    def __init__(self, secret_provider: SecretProvider, blob_source_factory: BlobSourceFactory | None = None):
        super().__init__(secret_provider=secret_provider)
        self._blob_source_factory = blob_source_factory or BlobSourceFactory(secret_provider=secret_provider)

    @property
    def extractor_type(self) -> str:
        return "blob"

    def extract(
        self,
        metadata: ExtractionMetadata,
        cursor: dict[str, str | None] | None = None,
    ) -> Iterator[ExtractionBatch]:
        emitted_batch = False
        all_records: list[dict[str, str | None]] = []
        latest_cursor: dict[str, str | None] | None = None
        config = BlobSourceConfig.model_validate(metadata.extractor_config)
        blob_source = self._blob_source_factory.build(config)
        if not cursor:
            existing_cursor = BlobCursor()
        else:
            last_modified = cursor.get("last_modified")
            existing_cursor = BlobCursor(
                last_modified=datetime.fromisoformat(last_modified.replace("Z", "+00:00")).astimezone(timezone.utc) if last_modified else None,
                last_object_name=cursor.get("last_object_name"),
            )
        objects = sorted(
            [obj for obj in blob_source.list_objects(config.source_container, prefix=f"{config.source_folder}/") if obj.object_name.lower().endswith(".csv")],
            key=lambda obj: (_normalize_to_utc(obj.last_modified), obj.object_name),
        )
        for obj in objects:
            obj_last_modified = _normalize_to_utc(obj.last_modified)
            if existing_cursor.last_modified is not None:
                if obj_last_modified < existing_cursor.last_modified:
                    continue
                if obj_last_modified == existing_cursor.last_modified:
                    if existing_cursor.last_object_name is None or obj.object_name <= existing_cursor.last_object_name:
                        continue
            content = blob_source.read_object(config.source_container, obj.object_name)
            decoded_content = content.decode(config.file_encoding or "utf-8") if isinstance(content, bytes) else content
            new_cursor = BlobCursor(
                last_modified=obj_last_modified,
                last_object_name=obj.object_name,
            ).model_dump(mode="json")
            file_name = obj.object_name.rsplit("/", 1)[-1]
            records = list(csv.DictReader(StringIO(decoded_content)))
            for record in records:
                record["source_file_name"] = file_name
            all_records.extend(records)
            latest_cursor = new_cursor
            emitted_batch = True
        if emitted_batch:
            yield ExtractionBatch(records=all_records, cursor=latest_cursor)
        if not emitted_batch and cursor:
            yield ExtractionBatch(records=[], cursor=existing_cursor.model_dump(mode="json"))
