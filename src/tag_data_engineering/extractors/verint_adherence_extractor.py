import base64
import hashlib
import hmac
import json
import logging
import random
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any
from typing import Iterator
from urllib.parse import urlparse

import requests
from pydantic import BaseModel

from tag_data_engineering.connectors.lakehouse_connector import LakehouseConnector
from tag_data_engineering.extractors.base_extractor import BaseExtractor
from tag_data_engineering.extractors.models import ExtractionBatch
from tag_data_engineering.models import ExtractionMetadata
from tag_data_engineering.secrets.secret_provider import SecretProvider


# NOTE(aablanya): Mainly for initial run tracking; updated via cursor thereafter
START_RUN_DATE = "2025-01-01T00:00:00Z"


class VerintExtractorCursor(BaseModel):
    """Cursor model for Verint Extractor state tracking."""

    last_run_time: datetime | None


class VerintApiExtractor(BaseModel):
    base_url: str


class VerintPreAuth:
    """HMAC-SHA256 Pre-Authorization for Verint API."""

    @staticmethod
    def get_keys(endpoint: str, api_key_id: str, api_key: str, verint_username: str) -> str:
        """Generate Verint authorization header."""
        issued_at = VerintPreAuth.get_iso_date_string()
        salt = VerintPreAuth.base64_url_encode(VerintPreAuth.generate_salt())
        headers = {"Verint-UserName": verint_username}
        canonicalized_header = VerintPreAuth.generate_canonicalized_header(headers)
        method = "GET"
        string_to_sign = f"{salt}\n{method}\n{endpoint}\n{issued_at}\n{canonicalized_header}\n"
        signature = VerintPreAuth.generate_signature(string_to_sign, api_key)
        auth_id = "Vrnt-1-HMAC-SHA256"
        return f"{auth_id} salt={salt},iat={issued_at},kid={api_key_id},sig={signature}"

    @staticmethod
    def get_iso_date_string() -> str:
        """Get current UTC time in ISO format."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def generate_canonicalized_header(headers: dict) -> str:
        """Generate canonicalized header string for signature."""
        return "".join(f"{k.lower()}:{v}\n" for k, v in sorted(headers.items()) if k.lower().startswith("verint-"))

    @staticmethod
    def generate_signature(string_to_sign: str, api_key: str) -> str:
        """Generate HMAC-SHA256 signature."""
        key_bytes = base64.b64decode(VerintPreAuth.convert_from_base64_url(api_key))
        signature = hmac.new(key_bytes, string_to_sign.encode(), hashlib.sha256).digest()
        return VerintPreAuth.base64_url_encode(signature)

    @staticmethod
    def base64_url_encode(input_bytes: bytes) -> str:
        """Base64 URL encode without padding."""
        return base64.b64encode(input_bytes).decode().rstrip("=").replace("+", "-").replace("/", "_")

    @staticmethod
    def convert_from_base64_url(input_str: str) -> str:
        """Convert Base64 URL encoded string to standard Base64."""
        input_str = input_str.replace("-", "+").replace("_", "/")
        padding = len(input_str) % 4
        if padding:
            input_str += "=" * (4 - padding)
        return input_str

    @staticmethod
    def generate_salt() -> bytes:
        """Generate random 16-byte salt."""
        return random.randbytes(16) if hasattr(random, "randbytes") else bytes(random.getrandbits(8) for _ in range(16))


class VerintAdherenceExtractor(BaseExtractor):
    """Specialized extractor for Verint Employee Adherence data.
    This extractor is purpose-built for adherence extraction and handles:
    - Rolling 30-day date window (calculated at runtime)
    - Employee list from Entra ID (filtered for FRE in Operations)
    - Batched API requests (50 employees per batch)
    - HMAC-SHA256 authentication
    NOT designed for reuse - create new extractors for other Verint domains.
    """

    def __init__(self, secret_provider: SecretProvider, connector: LakehouseConnector, timeout_seconds: int = 30):
        super().__init__(secret_provider=secret_provider)
        self.timeout_seconds = timeout_seconds
        self.connector = connector

    @property
    def extractor_type(self) -> str:
        return "verint_adherence"

    def _get_employees_from_lakehouse(self) -> list[str]:
        """Fetch employee list from Lakehouse 'silver.entra_users' table."""
        # NOTE(aablanya): user_principal_name returns email addresses; `Operations` and `Parking Operations` are (Energy and Comms) and Popla respectively, derived from MYHR.
        select_query = """
            SELECT user_principal_name
            FROM silver.entra_users
            WHERE org_hierarchy_level_4 in ('Operations', 'Parking Operations')
        """
        df = self.connector.run_sql(select_query)
        employees = [row["user_principal_name"] for row in df.collect()]
        return employees

    def _iter_rolling_day_slices(self, last_run_time: datetime | None) -> Iterator[tuple[str, str]]:
        """
        Produces 1-day [start, end) slices for a rolling window that expands
        if the extractor has not run recently.
        Rules:
        - Base window = ROLLING_WINDOW_DAYS
        - If last run < today, extend window by missed days
        - Always emit full-day slices
        - Never include partial today
        Args:
            last_run_time: A timezone-aware datetime object, or None.
        """
        rolling_windows_days = 30
        today_midnight = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        # Normalize last run time (fallback to rolling window only)
        if last_run_time:
            last_run_midnight = last_run_time.replace(hour=0, minute=0, second=0, microsecond=0)
            days_since_last_run = max(0, (today_midnight - last_run_midnight).days)
        else:
            days_since_last_run = 0
        # Calculate how many days we are behind
        effective_window_days = rolling_windows_days + days_since_last_run
        # Window boundaries
        window_end = today_midnight  # exclusive
        window_start = window_end - timedelta(days=effective_window_days)
        current_start = window_start
        while current_start < window_end:
            current_end = current_start + timedelta(days=1)
            yield (
                current_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                current_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
            current_start = current_end

    def extract(
        self,
        metadata: ExtractionMetadata,
        cursor: dict[str, str | None] | None = None,
    ) -> Iterator[ExtractionBatch]:
        """Extract Verint adherence data.
        Supports both FULL_REFRESH and INCREMENTAL modes:
        - FULL_REFRESH: Always extracts the rolling 30-day window
        - INCREMENTAL: Uses cursor's last_run_time to extend window if behind
        On first run (no cursor), uses the default rolling window.
        """
        # Rolling Date Window (adherence business rule: always last 30 days)
        employee_batch_size = 200
        logging.info(f"Starting Verint Adherence extraction for {metadata.entity}")
        api_credentials = json.loads(self.secret_provider.get_secret("verint-prod-api-credentials"))
        api_key_id = api_credentials["api_key"]
        api_key = api_credentials["api_secret"]
        config = VerintApiExtractor.model_validate(metadata.extractor_config)
        base_url = config.base_url.rstrip("/")
        # Step 2: Get employees once
        employees = self._get_employees_from_lakehouse()
        if not employees:
            raise RuntimeError("No employees found in silver.entra_users")
        logging.info(f"Found {len(employees)} employees")
        batches = [employees[i : i + employee_batch_size] for i in range(0, len(employees), employee_batch_size)]
        logging.info(f"Split into {len(batches)} batches of {employee_batch_size}")
        # Use cursor's last_run_time if provided, otherwise use Global Last Run Time
        last_run_dt: datetime | None = None
        last_run_value = cursor.get("last_run_time") if cursor else None
        if last_run_value:
            # Parse ISO format datetime string from cursor
            last_run_dt = datetime.fromisoformat(last_run_value)
            logging.info(f"Using cursor last_run_time: {last_run_dt}")
        else:
            # First run - no cursor, use default rolling window only
            last_run_dt = datetime.fromisoformat(START_RUN_DATE).replace(tzinfo=timezone.utc)
            logging.info("No cursor found, using default rolling window")
        # Step 1 (updated): loop over a rolling window of 1-day slices
        # Track date slices for cursor update
        slices = list(self._iter_rolling_day_slices(last_run_dt))
        total_slices = len(slices)
        for slice_idx, (start_date, end_date) in enumerate(slices, 1):
            logging.info(f"Date slice: {start_date} to {end_date}")
            is_last_slice = slice_idx == total_slices
            total_records_for_day = 0
            for batch_num, batch in enumerate(batches, 1):
                logging.info(f"Processing batch {batch_num}/{len(batches)} for slice {start_date}..{end_date}")
                is_last_batch = is_last_slice and (batch_num == len(batches))
                records = self._extract_batch(
                    employees=batch,
                    start_date=start_date,
                    end_date=end_date,
                    api_key_id=api_key_id,
                    api_key=api_key,
                    base_url=base_url,
                )
                if records:
                    total_records_for_day += len(records)
                    # Set cursor on the final batch to track last successful run
                    if is_last_batch:
                        new_cursor = VerintExtractorCursor(last_run_time=datetime.now(timezone.utc))
                        yield ExtractionBatch(records=records, cursor=new_cursor.model_dump(mode="json"))
                    else:
                        yield ExtractionBatch(records=records)
                elif is_last_batch:
                    # Even if no records, emit cursor on final batch
                    new_cursor = VerintExtractorCursor(last_run_time=datetime.now(timezone.utc))
                    yield ExtractionBatch(records=[], cursor=new_cursor.model_dump(mode="json"))
            logging.info(f"Slice complete ({start_date}..{end_date}): {total_records_for_day} records")

    def _extract_batch(
        self,
        employees: list[str],
        start_date: str,
        end_date: str,
        api_key_id: str,
        api_key: str,
        base_url: str,
    ) -> list[dict[str, Any]]:
        """Extract adherence data for a batch of employees."""
        # Build URL (check for test override)
        verint_endpoint = "adherence"
        verint_results_key = "data"
        verint_employee_lookup_key = "userName"
        verint_username: str = "okenny@trustalliancegroup.org"
        url = f"{base_url}/{verint_endpoint}/"
        # Build query parameters (adherence-specific)
        params = {
            "adherenceStartDate": start_date,
            "adherenceEndDate": end_date,
            "employeeLookupKey": verint_employee_lookup_key,
            "employeeIdentifierList": ",".join(employees),
        }
        # Build headers with HMAC auth
        headers = {"Accept": "application/json"}
        if api_key_id and api_key and verint_username:
            parsed = urlparse(base_url)
            auth_path = f"{parsed.path}/{verint_endpoint}/"
            headers["Authorization"] = VerintPreAuth.get_keys(
                endpoint=auth_path,
                api_key_id=api_key_id,
                api_key=api_key,
                verint_username=verint_username,
            )
            headers["Verint-UserName"] = verint_username
        # Make request
        response = requests.get(url, headers=headers, params=params, timeout=self.timeout_seconds)
        response.raise_for_status()
        data = response.json()
        return data.get(verint_results_key, []) if isinstance(data, dict) else data
