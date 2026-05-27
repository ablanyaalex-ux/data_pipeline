import json
import logging
import time
import uuid
from datetime import datetime

from pydantic import BaseModel

from tag_data_engineering.connectors.lakehouse_connector import LakehouseConnector
from tag_data_engineering.extractors.base_extractor import BaseExtractor
from tag_data_engineering.extractors.models import ExtractionBatch
from tag_data_engineering.metadata_schema import LANDING_RUNS_SCHEMA
from tag_data_engineering.models import ExtractionMetadata
from tag_data_engineering.models import ExtractionMode


class LandingResult(BaseModel):
    entity: str
    run_id: str
    records_extracted: int
    files_written: int
    duration_seconds: float
    cursor: dict[str, str | None] | None = None  # Cursor state as key/value map


class LandingRunner:
    def __init__(
        self,
        connector: LakehouseConnector,
        extractors: list[BaseExtractor],
    ):
        self.connector = connector
        self._extractors = {e.extractor_type: e for e in extractors}

    def _get_extractor(self, extractor_type: str) -> BaseExtractor:
        if extractor_type not in self._extractors:
            raise ValueError(f"Unsupported extractor type: {extractor_type}")
        return self._extractors[extractor_type]

    def generate_run_id(self) -> str:
        return str(uuid.uuid4())

    def run(self, metadata: ExtractionMetadata) -> LandingResult:
        start_time = datetime.now()
        logging.info(f"Starting landing extraction for entity: {metadata.entity}")
        logging.info(f"Extractor: {metadata.extractor}, Mode: {metadata.extraction_mode}")
        run_id = self.generate_run_id()
        logging.info(f"Run ID: {run_id}")
        logging.info("Starting extraction...")
        # Load cursor from latest successful run for incremental extractions
        existing_cursor: dict[str, str | None] | None = None
        if metadata.extraction_mode == ExtractionMode.INCREMENTAL:
            existing_cursor = self._load_latest_cursor(metadata.entity)

        extractor = self._get_extractor(metadata.extractor)
        new_cursor: dict[str, str | None] | None = None
        try:
            total_records, files_written, new_cursor = self._extract_and_write(
                extractor=extractor,
                metadata=metadata,
                run_id=run_id,
                cursor=existing_cursor,
            )
            status = "completed"
            error_message = None
        except Exception as e:
            total_records = 0
            files_written = 0
            status = "failed"
            error_message = str(e)
            logging.error(f"Extraction failed: {e}")
        completed_at = datetime.now()
        self._record_run(
            entity=metadata.entity,
            run_id=run_id,
            started_at=start_time,
            completed_at=completed_at,
            status=status,
            file_count=files_written,
            total_record_count=total_records,
            error_message=error_message,
            cursor=new_cursor,
        )
        if status == "failed":
            raise RuntimeError(f"Extraction failed: {error_message}")
        duration = (completed_at - start_time).total_seconds()
        return LandingResult(
            entity=metadata.entity,
            run_id=run_id,
            records_extracted=total_records,
            files_written=files_written,
            duration_seconds=round(duration, 2),
            cursor=new_cursor,
        )

    def _load_latest_cursor(self, entity: str) -> dict[str, str | None] | None:
        """Load cursor from the latest successful run for an entity.
        Returns the cursor dict, or None if no previous run exists.
        """
        try:
            df = self.connector.run_sql(f"""
                SELECT cursor FROM _metadata.landing_runs
                WHERE entity = '{entity}' AND status = 'completed'
                ORDER BY completed_at DESC
                LIMIT 1
            """)
            rows = df.collect()
            if rows and rows[0].cursor:
                return dict(rows[0].cursor)
            return None
        except Exception as e:
            logging.warning(f"Could not load cursor for {entity}: {e}")
            return None

    def _extract_and_write(
        self,
        extractor: BaseExtractor,
        metadata: ExtractionMetadata,
        run_id: str,
        cursor: dict[str, str | None] | None = None,
    ) -> tuple[int, int, dict[str, str | None] | None]:
        """Extract data and write to files.

        Returns:
            Tuple of (total_records, files_written, cursor)
        """
        max_file_size_bytes = metadata.max_file_size_mb * 1024 * 1024
        output_path = self.connector.get_files_path(metadata.entity, run_id)
        self.connector.mkdirs(output_path)
        total_records = 0
        files_written = 0
        current_batch: ExtractionBatch | None = None
        current_batch_size_bytes = 0
        new_cursor: dict[str, str | None] | None = None
        extract_start = time.perf_counter()
        last_batch_end = extract_start
        for batch_index, batch in enumerate(extractor.extract(metadata=metadata, cursor=cursor), start=1):
            batch_received_at = time.perf_counter()
            wait_time = batch_received_at - last_batch_end
            batch_processing_time = 0.0
            batch_write_time = 0.0
            files_written_for_batch = 0
            # Capture cursor from batch for persistence (last one wins)
            # Convert all values to strings for MapType storage
            if batch.cursor is not None:
                new_cursor = {k: str(v) if v is not None else None for k, v in batch.cursor.items()}
            for record in batch.records:
                record_processing_start = time.perf_counter()
                if current_batch is None:
                    current_batch = ExtractionBatch(records=[])
                record_size_bytes = len(json.dumps(record, default=str).encode("utf-8"))
                projected_size_bytes = current_batch_size_bytes + record_size_bytes + (1 if current_batch.records else 0)
                batch_processing_time += time.perf_counter() - record_processing_start
                if current_batch.records and projected_size_bytes >= max_file_size_bytes:
                    # Write current batch before adding this record
                    file_write_start = time.perf_counter()
                    files_written += 1
                    self._write_batch_to_file(current_batch, output_path, files_written, metadata.output_format)
                    file_write_time = time.perf_counter() - file_write_start
                    batch_write_time += file_write_time
                    files_written_for_batch += 1
                    logging.info("Landing writer file timing: batch=%s file_index=%s records=%s write_time=%.2fs", batch_index, files_written, len(current_batch.records), file_write_time)
                    current_batch = ExtractionBatch(records=[record])
                    current_batch_size_bytes = record_size_bytes
                else:
                    current_batch.records.append(record)
                    current_batch_size_bytes = projected_size_bytes
                total_records += 1
            logging.info(
                "Landing writer batch timing: batch=%s records=%s wait_time=%.2fs processing_time=%.2fs write_time=%.2fs files_written=%s",
                batch_index,
                len(batch.records),
                wait_time,
                batch_processing_time,
                batch_write_time,
                files_written_for_batch,
            )
            last_batch_end = time.perf_counter()
        # Write any remaining data
        if current_batch is not None and current_batch.records:
            final_write_start = time.perf_counter()
            files_written += 1
            self._write_batch_to_file(current_batch, output_path, files_written, metadata.output_format)
            final_write_time = time.perf_counter() - final_write_start
            logging.info("Landing writer final file timing: file_index=%s records=%s write_time=%.2fs", files_written, len(current_batch.records), final_write_time)
        logging.info(f"Extraction complete: {total_records:,} records in {files_written} files")
        return total_records, files_written, new_cursor

    def _write_batch_to_file(self, batch: ExtractionBatch, output_path: str, file_index: int, output_format: str) -> None:
        if output_format != "jsonl":
            raise ValueError(f"Unsupported output_format: {output_format}. Only 'jsonl' is currently supported.")
        file_path = f"{output_path}{file_index}.{output_format}"
        self.connector.write_file(file_path, batch.to_json_lines())
        logging.info(f"Wrote {len(batch.records):,} records to {file_path}")

    def _record_run(
        self,
        entity: str,
        run_id: str,
        started_at: datetime,
        completed_at: datetime,
        status: str,
        file_count: int,
        total_record_count: int,
        error_message: str | None,
        cursor: dict[str, str | None] | None,
    ) -> None:
        row_data = [
            (
                entity,
                run_id,
                started_at,
                completed_at,
                status,
                file_count,
                total_record_count,
                error_message,
                cursor,
            )
        ]
        self.connector.write_data_to_table(
            data=row_data,
            schema=LANDING_RUNS_SCHEMA,
            table="_metadata.landing_runs",
            mode="append",
            options={"mergeSchema": "true"},
        )
        logging.info(f"Recorded run: {run_id} ({status}, {total_record_count:,} records in {file_count} files)")
