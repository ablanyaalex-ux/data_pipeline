import json
import logging
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import Iterable
from typing import Iterator
from typing import Set
from typing import cast

import msal
import requests
from pydantic import BaseModel

from tag_data_engineering.extractors.base_extractor import BaseExtractor
from tag_data_engineering.extractors.models import ExtractionBatch
from tag_data_engineering.models import ExtractionMetadata
from tag_data_engineering.models import ExtractionMode
from tag_data_engineering.secrets.secret_provider import SecretProvider


class EntraUsersExtractorConfig(BaseModel):
    base_url: str
    login_base_url: str


class EntraUsersExtractor(BaseExtractor):
    """Extract Entra users with an optional dynamic $select list."""

    # NOTE(krishan711): filter any properties we should not or can not access
    _IRRETRIEVABLE_PROPERTIES: Set[str] = {
        "aboutMe",
        "birthday",
        "hireDate",
        "interests",
        "mySite",
        "pastProjects",
        "preferredName",
        "responsibilities",
        "schools",
        "skills",
        "mailboxSettings",
    }
    # NOTE(krishna711): remove fields that give API errors
    _ERRORING_PROPERTIES: Set[str] = {
        "deviceEnrollmentLimit",
        "print",
        "7N_CRM",
        "7n_test",
    }

    def __init__(self, secret_provider: SecretProvider, timeout_seconds: int = 600):
        super().__init__(secret_provider=secret_provider)
        self.timeout_seconds = timeout_seconds
        self._token_cache: dict[str, tuple[str, float]] = {}

    @property
    def extractor_type(self) -> str:
        return "entra_users"

    def extract(
        self,
        metadata: ExtractionMetadata,
        cursor: dict[str, str | None] | None = None,
    ) -> Iterator[ExtractionBatch]:
        if metadata.extraction_mode == ExtractionMode.INCREMENTAL:
            raise ValueError(f"Entra users extractor does not support incremental extraction mode. Entity '{metadata.entity}' has extraction_mode='incremental'. Use full_refresh.")
        config = EntraUsersExtractorConfig.model_validate(metadata.extractor_config)
        endpoint = "users"
        results_key = "value"
        next_key = "@odata.nextLink"
        chunk_size = 150
        query_params: dict[str, str] = {}
        headers = {
            "Content-Type": "application/json",
            "ConsistencyLevel": "eventual",
            "Authorization": f"Bearer {self._get_token(config=config)}",
        }
        builtin_props = self._get_builtin_user_properties(headers, config.base_url)
        extensions = self._get_schema_extension_property_names(headers, config.base_url)
        app_extensions = self._get_application_extension_property_names(headers, config.base_url)
        all_properties = sorted(set(builtin_props) | set(extensions) | set(app_extensions))
        select_columns = [name for name in all_properties if name not in self._IRRETRIEVABLE_PROPERTIES and not name.endswith("_cippUser") and name not in self._ERRORING_PROPERTIES]
        url = f"{config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        user_properties: dict[str, dict] = defaultdict(dict)
        total_records = 0
        for batch_index, field_batch in enumerate(self._generate_chunks(select_columns, chunk_size), start=1):
            params = dict(query_params)
            # Ensure 'id' is included but avoid duplicates
            select_fields = ["id"] + [f for f in field_batch if f != "id"] if field_batch else ["id"]
            params["$select"] = ",".join(select_fields)
            next_url: str | None = url
            page_count = 0
            while next_url is not None:
                current_url = next_url
                page_count += 1
                logging.info(f"Fetching batch {batch_index} page {page_count}: {current_url}")
                page_params = params if current_url == url else None
                response = requests.get(current_url, headers=headers, params=page_params, timeout=self.timeout_seconds)
                response.raise_for_status()
                data = response.json()
                records = data.get(results_key, []) if isinstance(data, dict) else data
                if not records:
                    break
                for record in records:
                    user_id = record.get("id")
                    if user_id:
                        user_properties[user_id].update(record)
                total_records += len(records)
                next_url = cast(str | None, data.get(next_key)) if isinstance(data, dict) and next_key else None
        logging.info(f"Extraction complete: {len(user_properties)} users, {total_records} records across field batches")
        yield ExtractionBatch(records=list(user_properties.values()))

    def _get_builtin_user_properties(self, headers: dict[str, str], base_url: str) -> list[str]:
        """
        Retrieve the list of built-in Entra ID user property names by parsing the
        Microsoft Graph OData $metadata document.

        This method inspects the 'user' EntityType definition in the metadata and
        returns all declared property names. The result represents the full set of
        schema-defined user fields, not all of which are necessarily selectable or
        readable via the /users list endpoint (due to API, permission, or endpoint
        constraints). Additional filtering is applied by the caller.

        Supports both XML (OData standard) and JSON (custom format) metadata responses.
        """
        url = f"{base_url.rstrip('/')}/$metadata"
        response = requests.get(url, headers=headers, timeout=self.timeout_seconds)
        response.raise_for_status()

        # Try to parse as JSON first (for mock servers), then fall back to XML
        try:
            metadata_json = response.json()
            if "entityTypes" in metadata_json and "user" in metadata_json["entityTypes"]:
                user_properties = metadata_json["entityTypes"]["user"].get("properties", [])
                return sorted(user_properties)
        except (ValueError, KeyError):
            # Not JSON or doesn't have expected structure, try XML
            pass

        # Parse as XML (original implementation)
        ns = {
            "edmx": "http://docs.oasis-open.org/odata/ns/edmx",
            "edm": "http://docs.oasis-open.org/odata/ns/edm",
        }
        root = ET.fromstring(response.text)
        user_entity = None
        for entity in root.findall(".//edm:EntityType", ns):
            if entity.attrib.get("Name") == "user":
                user_entity = entity
                break
        if user_entity is None:
            raise RuntimeError("Could not find EntityType 'user' in Graph $metadata")
        props = sorted({p.attrib["Name"] for p in user_entity.findall("./edm:Property", ns)})
        return props

    def _get_schema_extension_property_names(self, headers: dict[str, str], base_url: str) -> list[str]:
        results_key = "value"
        next_key = "@odata.nextLink"
        ext_names: Set[str] = set()
        url = f"{base_url.rstrip('/')}/schemaExtensions"
        for extension in self._get_paged(url, headers, results_key, next_key):
            if "User" not in extension.get("targetTypes", []):
                continue
            name = extension.get("id")
            if name:
                ext_names.add(name)
        return sorted(ext_names)

    def _get_application_extension_property_names(self, headers: dict[str, str], base_url: str) -> list[str]:
        results_key = "value"
        next_key = "@odata.nextLink"
        ext_names: Set[str] = set()
        apps_url = f"{base_url.rstrip('/')}/applications"
        for app in self._get_paged(apps_url, headers, results_key, next_key):
            app_id = app.get("id")
            if not app_id:
                continue
            ext_url = f"{base_url.rstrip('/')}/applications/{app_id}/extensionProperties"
            for extension in self._get_paged(ext_url, headers, results_key, next_key):
                if "User" not in extension.get("targetObjects", []):
                    continue
                name = extension.get("name")
                if name:
                    ext_names.add(name)
        return sorted(ext_names)

    def _get_paged(self, url: str, headers: dict[str, str], results_key: str, next_key: str | None) -> Iterable[dict]:
        current_url: str | None = url
        while current_url:
            response = requests.get(current_url, headers=headers, timeout=self.timeout_seconds)
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                raise RuntimeError(f"Graph error payload: {json.dumps(data, indent=2)}")
            items = data.get(results_key, [])
            if not isinstance(items, list):
                raise RuntimeError(f"Unexpected payload (no list '{results_key}'): {json.dumps(data, indent=2)}")
            yield from items
            new_url = data.get(next_key) if next_key else None
            current_url = str(new_url) if new_url else None

    def _generate_chunks(self, values: list[str], chunk_size: int) -> Iterator[list[str]]:
        for index in range(0, len(values), chunk_size):
            yield values[index : index + chunk_size]

    def _get_token(self, config: EntraUsersExtractorConfig) -> str:
        sp_credentials = json.loads(self.secret_provider.get_secret("de-sp-credentials"))
        tenant_id = self.secret_provider.get_secret("tenant-id")
        client_id = sp_credentials["client_id"]
        client_secret = sp_credentials["client_secret"]
        scope = "https://graph.microsoft.com/.default"
        authority = f"{config.login_base_url}/{tenant_id}"
        logging.info(f"Acquiring token from authority: {authority}")
        if not authority.startswith("https://login.microsoftonline.com"):
            token = "test-token"
        else:
            cache_key = f"{tenant_id}:{client_id}:{scope}"
            if cache_key in self._token_cache:
                token, expiry = self._token_cache[cache_key]
                if time.time() < expiry - 60:
                    return token
            # TODO(aablanya): Remove use of msal; call Api directly
            app = msal.ConfidentialClientApplication(
                client_id=client_id,
                client_credential=client_secret,
                authority=authority,
            )
            result = app.acquire_token_for_client(scopes=[scope])
            token = result.get("access_token")
            if not token:
                raise RuntimeError(f"Could not acquire token: {json.dumps(result, indent=2)}")
            expires_in = result.get("expires_in", 3600)
            expiry_time = time.time() + expires_in
            self._token_cache[cache_key] = (token, expiry_time)
        return token
