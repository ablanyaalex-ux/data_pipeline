import logging
from typing import Any
from typing import Iterator

import requests
from pydantic import BaseModel
from pydantic import Field

from tag_data_engineering.extractors.base_extractor import BaseExtractor
from tag_data_engineering.extractors.models import ExtractionBatch
from tag_data_engineering.models import ExtractionMetadata
from tag_data_engineering.models import ExtractionMode
from tag_data_engineering.secrets.secret_provider import SecretProvider


class RestApiExtractorConfig(BaseModel):
    base_url: str  # e.g., "https://swapi.dev/api"
    endpoint: str  # e.g., "people"
    results_key: str  # JSON key containing the data array
    next_key: str | None  # JSON key for pagination URL (None = no pagination)
    headers: dict[str, str] = Field(default_factory=dict)  # Optional HTTP headers
    secret_headers: dict[str, str] = Field(default_factory=dict)  # Header name -> secret name mapping


class RestApiExtractor(BaseExtractor):
    def __init__(self, secret_provider: SecretProvider, timeout_seconds: int = 30):
        super().__init__(secret_provider=secret_provider)
        self.timeout_seconds = timeout_seconds

    @property
    def extractor_type(self) -> str:
        return "rest_api"

    def extract(
        self,
        metadata: ExtractionMetadata,
        cursor: dict[str, str | None] | None = None,
    ) -> Iterator[ExtractionBatch]:
        if metadata.extraction_mode == ExtractionMode.INCREMENTAL:
            raise ValueError(
                f"REST API extractor does not support incremental extraction mode. "
                f"Entity '{metadata.entity}' has extraction_mode='incremental', which is only supported "
                f"by the 'copy_job' extractor. Use extraction_mode='full_refresh' for REST API extractions."
            )
        config = RestApiExtractorConfig.model_validate(metadata.extractor_config)
        base_url = config.base_url.rstrip("/")
        endpoint = config.endpoint.lstrip("/")
        headers = config.headers.copy()
        if config.secret_headers:
            for header_name, secret_name in config.secret_headers.items():
                headers[header_name] = self.secret_provider.get_secret(secret_name)
        logging.info(f"Starting extraction for {metadata.entity}")
        url: str | None = f"{base_url}/{endpoint}/"
        total_records = 0
        page_count = 0
        while url:
            page_count += 1
            data = self._fetch_page(url, headers)
            if isinstance(data, list):
                records = data
            else:
                records = data.get(config.results_key, [])
            logging.info(f"Fetched page {page_count} from {url}: found {len(records)} records")
            if not records:
                break
            total_records += len(records)
            logging.info(f"Page {page_count}: {len(records)} records (total: {total_records})")
            yield ExtractionBatch(records=records)
            # Simplified pagination: our current use case either has no pagination
            # or provides an absolute URL in the `next` field. Anything else stops.
            if config.next_key and isinstance(data, dict):
                next_val = data.get(config.next_key)
                if isinstance(next_val, str):
                    next_val = next_val.strip()
                    url = next_val if next_val else None
                else:
                    url = None
            else:
                url = None
        logging.info(f"Extraction complete: {total_records} records from {page_count} pages")

    def _fetch_page(self, url: str, headers: dict[str, str]) -> dict[str, Any]:
        logging.info(f"Fetching: {url}")
        response = requests.get(url, headers=headers, timeout=self.timeout_seconds)
        response.raise_for_status()
        return response.json()
