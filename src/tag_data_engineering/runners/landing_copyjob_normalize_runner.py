import logging
from datetime import datetime

from tag_data_engineering.models import ExtractionMetadata
from tag_data_engineering.runners.landing_runner import LandingResult
from tag_data_engineering.runners.landing_runner import LandingRunner


class LandingCopyJobNormalizeRunner(LandingRunner):
    def run(self, metadata: ExtractionMetadata) -> LandingResult:
        start_time = datetime.now()
        logging.info(f"Starting Copy Job normalization for entity: {metadata.entity}")
        logging.info(f"Loaded metadata for {metadata.entity}")
        run_id = self.generate_run_id()
        logging.info(f"Run ID: {run_id}")
        try:
            copyjob_output_path = self._get_copyjob_output_path(metadata)
            if not self.connector.path_exists(copyjob_output_path):
                logging.info(f"No raw files found at {copyjob_output_path} - already processed or no data")
                return LandingResult(
                    entity=metadata.entity,
                    run_id=run_id,
                    records_extracted=0,
                    files_written=0,
                    duration_seconds=0.0,
                )
            total_records, files_written = self._normalize_and_write(
                copyjob_output_path=copyjob_output_path,
                metadata=metadata,
                run_id=run_id,
            )
            logging.info(f"Deleting raw files from: {copyjob_output_path}")
            self.connector.delete_dir(copyjob_output_path)
            logging.info("Raw files deleted successfully")
            status = "completed"
            error_message = None
        except Exception as e:
            total_records = 0
            files_written = 0
            status = "failed"
            error_message = str(e)
            logging.error(f"Normalization failed: {e}")
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
            cursor=None,
        )
        if status == "failed":
            raise RuntimeError(f"Normalization failed: {error_message}")
        duration = (completed_at - start_time).total_seconds()
        return LandingResult(
            entity=metadata.entity,
            run_id=run_id,
            records_extracted=total_records,
            files_written=files_written,
            duration_seconds=round(duration, 2),
        )

    def _get_copyjob_output_path(self, metadata: ExtractionMetadata) -> str:
        base = self.connector.base_path
        if base:
            return f"{base}/Files/copyjob_raw/{metadata.entity}/"
        return f"Files/copyjob_raw/{metadata.entity}/"

    def _normalize_and_write(self, copyjob_output_path: str, metadata: ExtractionMetadata, run_id: str) -> tuple[int, int]:
        # Read JSON files from Copy Job output
        max_file_size_bytes = metadata.max_file_size_mb * 1024 * 1024
        self.connector.set_conf("spark.sql.files.maxPartitionBytes", str(max_file_size_bytes))
        logging.info(f"Reading Copy Job output from: {copyjob_output_path}")
        df = self.connector.read_json(copyjob_output_path)
        total_records = df.count()
        logging.info(f"Read {total_records:,} records from Copy Job output")
        if total_records == 0:
            logging.info("No records found in Copy Job output")
            return 0, 0
        # Get output path using connector method
        output_path = self.connector.get_files_path(metadata.entity, run_id)
        num_partitions = df.rdd.getNumPartitions()
        logging.info(f"Writing {total_records:,} records in {num_partitions} partition(s) to: {output_path}")
        # Write as JSON Lines (one JSON object per line)
        # Each partition becomes a separate file, sized based on maxPartitionBytes
        df.write.mode("overwrite").json(output_path)
        logging.info(f"Normalization complete: {total_records:,} records written")
        return total_records, num_partitions
