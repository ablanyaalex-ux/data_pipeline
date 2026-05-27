import logging
import time
from datetime import datetime

from pydantic import BaseModel
from pyspark.sql import DataFrame
from pyspark.sql.functions import col
from pyspark.sql.functions import lit
from pyspark.sql.functions import row_number
from pyspark.sql.window import Window

from tag_data_engineering.connectors.lakehouse_connector import LakehouseConnector
from tag_data_engineering.metadata_schema import BRONZE_RUNS_SCHEMA
from tag_data_engineering.models import BronzeMetadata
from tag_data_engineering.models import TransformationMetadata


class TransformationResult(BaseModel):
    rows_processed: int
    duration_seconds: float


class TransformationRunner:
    def __init__(self, connector: LakehouseConnector):
        self.connector = connector

    def run_transformation(self, metadata: BronzeMetadata | TransformationMetadata) -> TransformationResult:
        if isinstance(metadata, BronzeMetadata):
            return self._run_bronze_transformation(metadata)
        return self._run_silver_transformation(metadata)

    def _run_bronze_transformation(self, metadata: BronzeMetadata) -> TransformationResult:
        start_time = time.time()
        full_table_name = f"bronze.{metadata.table}"
        logging.info(f"Starting bronze transformation for {full_table_name}")
        logging.info(f"Entity: {metadata.entity}, merge_key: {metadata.merge_key_list}")
        unprocessed_runs = self._get_unprocessed_landing_runs(entity=metadata.entity)
        if not unprocessed_runs:
            logging.info("No unprocessed landing runs found. Nothing to do.")
            duration = time.time() - start_time
            return TransformationResult(rows_processed=0, duration_seconds=round(duration, 2))
        logging.info(f"Found {len(unprocessed_runs)} unprocessed run(s) to process")
        self.connector.create_schema(metadata.schema_name)
        total_rows_processed = 0
        for run_id, file_count in unprocessed_runs:
            logging.info(f"Processing run: {run_id}")
            if file_count == 0:
                self._record_bronze_run(
                    entity=metadata.entity,
                    run_id=run_id,
                    record_count=0,
                )
                logging.info(f"Run {run_id} has 0 files. Marked as processed (0 records). Skipping.")
                continue
            # Read JSON files for this run
            files_path = self.connector.get_files_path(
                entity=metadata.entity,
                run_id=run_id,
            )
            logging.info(f"Reading files from: {files_path}")
            source_df = self._read_landing_files(files_path, metadata.source_format)
            source_df = source_df.withColumn("_run_id", lit(run_id))
            # including explode fields from feature branch
            if metadata.explode_fields:
                source_df = self._apply_explode_fields(source_df, metadata.explode_fields)
                logging.info(f"Applied explode_fields: {metadata.explode_fields}")
            logging.info(f"Run {run_id}: {source_df.count()} rows after deduplication")
            # Deduplicate by merge key within this run (keep first occurrence per key)
            window = Window.partitionBy(*metadata.merge_key_list).orderBy(*metadata.merge_key_list)
            deduped_df = source_df.withColumn("_row_num", row_number().over(window)).filter(col("_row_num") == 1).drop("_row_num")
            run_row_count = deduped_df.count()
            logging.info(f"Run {run_id}: {run_row_count} rows after deduplication")
            target_table = self.connector.get_table_path(metadata.schema_name, metadata.table)
            table_exists = self._table_exists(metadata.schema_name, metadata.table)
            string_deduped_df = deduped_df.select([col(c).cast("string").alias(c) for c in deduped_df.columns])
            with self.connector.create_temp_view(string_deduped_df) as view_name:
                if not table_exists:
                    # First run: create the table
                    # Note(Aablanya): TBLPROPERTIES added to enable column mapping by name for future schema evolution and column with spaces in definition
                    logging.info(f"Creating new bronze table: {target_table}")
                    self.connector.run_sql(f"""
                        CREATE TABLE {target_table}
                        USING DELTA
                        TBLPROPERTIES ('delta.columnMapping.mode' = 'name')
                        AS SELECT * FROM {view_name}
                    """)
                else:
                    # Subsequent runs: merge with deduplication
                    logging.info(f"Merging into existing bronze table: {target_table}")
                    merge_condition = " AND ".join([f"target.`{key}` = source.`{key}`" for key in metadata.merge_key_list])
                    merge_sql = f"""
                    MERGE INTO {target_table} AS target
                    USING {view_name} AS source
                    ON {merge_condition}
                    WHEN MATCHED THEN UPDATE SET *
                    WHEN NOT MATCHED THEN INSERT *
                    """
                    self.connector.run_sql(merge_sql)
            # Track this run as processed
            self._record_bronze_run(
                entity=metadata.entity,
                run_id=run_id,
                record_count=run_row_count,
            )
            total_rows_processed += run_row_count
        duration = time.time() - start_time
        result_obj = TransformationResult(
            rows_processed=total_rows_processed,
            duration_seconds=round(duration, 2),
        )
        logging.info(f"✅ Bronze transformation completed: {total_rows_processed:,} rows in {duration:.2f}s")
        return result_obj

    def _apply_explode_fields(self, df: "DataFrame", explode_fields: list[str]) -> "DataFrame":
        """Flatten/explode struct columns specified in explode_fields.
        For each struct column in explode_fields, extracts nested fields as top-level
        columns with prefix format (e.g., attributes.field -> attributes_field).
        Only the flattened struct fields are kept; other columns are dropped.
        Args:
            df: Input DataFrame with nested struct columns
            explode_fields: List of struct column names to flatten
        Returns:
            DataFrame with only the flattened struct columns
        """
        all_flattened_exprs = []
        for struct_col in explode_fields:
            if struct_col not in df.columns:
                logging.warning(f"explode_fields column '{struct_col}' not found in DataFrame. Available: {df.columns}")
                continue
            logging.info(f"Exploding struct column: {struct_col}")
            # Get the struct fields
            struct_fields = df.select(f"{struct_col}.*").columns
            logging.info(f"  Found fields: {struct_fields}")
            # Build select expressions: only include the flattened struct fields
            all_flattened_exprs += [col(f"{struct_col}.{field}").alias(f"{struct_col}_{field}") for field in struct_fields]
            logging.info(f"  Flattened {struct_col} into {len(struct_fields)} columns")
        if all_flattened_exprs:
            df = df.select(all_flattened_exprs)
        return df

    def _table_exists(self, schema: str, table: str) -> bool:
        try:
            tables = self.connector.run_sql(f"SHOW TABLES IN {schema}").collect()
            table_names = [row.tableName for row in tables]
            return table in table_names
        except Exception as e:
            # Schema doesn't exist is expected - return False
            # But log other errors so we can diagnose issues
            error_str = str(e).lower()
            if "schema" in error_str and ("not found" in error_str or "does not exist" in error_str):
                return False
            logging.warning(f"Unexpected error checking if {schema}.{table} exists: {e}")
            return False

    def _get_unprocessed_landing_runs(self, entity: str) -> list[tuple[str, int]]:
        query = f"""
        SELECT lr.run_id, lr.file_count
        FROM _metadata.landing_runs lr
        LEFT JOIN _metadata.bronze_runs br
            ON lr.run_id = br.run_id
            AND lr.entity = br.entity
        WHERE lr.entity = '{entity}'
            AND lr.status = 'completed'
            AND br.run_id IS NULL
        ORDER BY lr.completed_at ASC
        """
        result = self.connector.run_sql(query).collect()
        return [(row.run_id, int(row.file_count)) for row in result]

    def _record_bronze_run(self, entity: str, run_id: str, record_count: int) -> None:
        processed_at = datetime.now()
        row_data = [
            (
                entity,
                run_id,
                processed_at,  # started_at
                processed_at,  # completed_at
                "completed",  # status
                record_count,  # rows_processed
                None,  # error_message
            )
        ]
        self.connector.write_data_to_table(
            data=row_data,
            schema=BRONZE_RUNS_SCHEMA,
            table="_metadata.bronze_runs",
            mode="append",
        )
        logging.info(f"Marked run {run_id} as processed ({record_count} records)")

    def _read_landing_files(self, files_path: str, source_format: str) -> "DataFrame":
        if source_format != "jsonl":
            raise ValueError(f"Unsupported source_format: {source_format}. Only 'jsonl' is currently supported.")
        return self.connector.read_json(files_path)

    def _run_silver_transformation(self, metadata: TransformationMetadata) -> TransformationResult:
        start_time = time.time()
        full_table_name = f"{metadata.schema_name}.{metadata.table}"
        logging.info(f"Starting transformation for {full_table_name} (merge_key: {metadata.merge_key_list})")
        logging.info(f"Executing transformation SQL for {full_table_name}")
        source_df = self.connector.run_sql(metadata.sql)
        row_count = source_df.count()
        logging.info(f"Transformation produced {row_count:,} rows")
        target_table = self.connector.get_table_path(
            schema=metadata.schema_name,
            table=metadata.table,
        )
        self.connector.create_schema(metadata.schema_name)
        table_exists = self._table_exists(metadata.schema_name, metadata.table)
        with self.connector.create_temp_view(source_df) as view_name:
            if not table_exists:
                # First run: create the table
                logging.info(f"Creating new table: {target_table}")
                self.connector.run_sql(f"""
                    CREATE TABLE {target_table}
                    USING DELTA
                    AS SELECT * FROM {view_name}
                """)
            else:
                # Subsequent runs: merge into existing table
                if metadata.overwrite_matching_existing_source_keys:
                    if not metadata.source_merge_key:
                        raise ValueError("source_merge_key must be specified when overwrite_matching_existing_source_keys is True.")
                    logging.info(f"Replacing rows in target table matching source_merge_key: {metadata.source_merge_key}")
                    # NOTE(aablanya): REPLACE WHERE and DELETE cant use subqueries, so we use a MERGE to do the bulk delete of exitsing matching records
                    delete_condition = " AND ".join([f"target.`{k}` = source.`{k}`" for k in metadata.source_merge_key])
                    delete_sql = f"""
                        MERGE INTO {target_table} AS target
                        USING {view_name} AS source
                        ON {delete_condition}
                        WHEN MATCHED THEN DELETE
                    """
                    self.connector.run_sql(delete_sql)
                    logging.info(f"Deleted rows in {target_table} matching source_merge_key before merge.")
                logging.info(f"Merging into existing table: {target_table}")
                merge_condition = " AND ".join([f"target.`{key}` = source.`{key}`" for key in metadata.merge_key_list])
                merge_sql = f"""
                MERGE INTO {target_table} AS target
                USING {view_name} AS source
                ON {merge_condition}
                WHEN MATCHED THEN UPDATE SET *
                WHEN NOT MATCHED THEN INSERT *
                """
                self.connector.run_sql(merge_sql)
        duration = time.time() - start_time
        result_obj = TransformationResult(
            rows_processed=row_count,
            duration_seconds=round(duration, 2),
        )
        logging.info(f"✅ Transformation completed: {row_count:,} rows in {duration:.2f}s")
        return result_obj
