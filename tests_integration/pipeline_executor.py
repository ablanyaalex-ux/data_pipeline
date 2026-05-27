import logging
import time
from collections import deque
from dataclasses import dataclass

from minio import Minio
from pyspark.sql import SparkSession

from tag_data_engineering.connectors.lakehouse_connector import LakehouseConnector
from tag_data_engineering.extractors.blob_extractor import BlobExtractor
from tag_data_engineering.extractors.blob_extractor import BlobSourceConfig
from tag_data_engineering.extractors.blob_extractor import BlobStorageObjectInfo
from tag_data_engineering.extractors.blob_extractor import _normalize_to_utc
from tag_data_engineering.extractors.entra_users_extractor import EntraUsersExtractor
from tag_data_engineering.extractors.mysql_extractor import MySqlExtractor
from tag_data_engineering.extractors.postgres_extractor import PostgresExtractor
from tag_data_engineering.extractors.rest_api_extractor import RestApiExtractor
from tag_data_engineering.extractors.sql_server_extractor import SqlServerExtractor
from tag_data_engineering.extractors.verint_adherence_extractor import VerintAdherenceExtractor
from tag_data_engineering.pipeline.models import InvokePipelineActivity
from tag_data_engineering.pipeline.models import Layer
from tag_data_engineering.pipeline.models import PipelineActivity
from tag_data_engineering.pipeline.models import PipelineDefinition
from tag_data_engineering.runners.landing_copyjob_normalize_runner import LandingCopyJobNormalizeRunner
from tag_data_engineering.runners.landing_runner import LandingRunner
from tag_data_engineering.runners.setup_runner import SetupRunner
from tag_data_engineering.runners.transformation_runner import TransformationRunner
from tag_data_engineering.secrets.secret_provider import SecretProvider


@dataclass
class ActivityResult:
    activity_name: str
    success: bool
    error_message: str | None = None
    duration_seconds: float = 0.0


class _MinioBlobSource:
    def __init__(self, client: Minio):
        self._client = client

    def list_objects(self, container: str, prefix: str) -> list[BlobStorageObjectInfo]:
        return [
            BlobStorageObjectInfo(
                object_name=obj.object_name,
                last_modified=_normalize_to_utc(obj.last_modified),
            )
            for obj in self._client.list_objects(container, prefix=prefix, recursive=True)
        ]

    def read_object(self, container: str, object_name: str) -> str:
        response = self._client.get_object(container, object_name)
        return response.read().decode("utf-8")


class _MinioBlobSourceFactory:
    def __init__(self, client: Minio):
        self._blob_source = _MinioBlobSource(client)

    def build(self, config: BlobSourceConfig) -> _MinioBlobSource:
        return self._blob_source


class PipelineExecutor:
    def __init__(
        self,
        spark: SparkSession,
        connector: LakehouseConnector,
        secret_provider: SecretProvider,
        tagdataengineering_blob_minio_client: Minio,
    ):
        self.spark = spark
        self.connector = connector
        self.secret_provider = secret_provider
        self.tagdataengineering_blob_minio_client = tagdataengineering_blob_minio_client

    def execute_subpipelines(self, orchestrator: PipelineDefinition, subpipelines: dict[str, PipelineDefinition]) -> list[ActivityResult]:
        logging.info(f"Starting sub-pipeline execution: {orchestrator.name}")
        logging.info(f"Sub-pipelines: {list(subpipelines.keys())}")
        execution_order = self._topological_sort(orchestrator.activities)
        all_results: list[ActivityResult] = []
        completed: set[str] = set()
        for activity in execution_order:
            if isinstance(activity, InvokePipelineActivity):
                sub_key = activity.name.removeprefix("invoke_")
                sub_pipeline = subpipelines.get(sub_key)
                if not sub_pipeline:
                    all_results.append(ActivityResult(activity_name=activity.name, success=False, error_message=f"Sub-pipeline not found: {sub_key}"))
                    continue
                logging.info(f"Invoking sub-pipeline: {sub_pipeline.name} ({len(sub_pipeline.activities)} activities)")
                sub_results = self.execute(sub_pipeline)
                all_results.extend(sub_results)
                failed = [r for r in sub_results if not r.success]
                if failed:
                    all_results.append(ActivityResult(activity_name=activity.name, success=False, error_message=f"Sub-pipeline failed: {sub_key}"))
                    return all_results
                completed.add(activity.name)
            else:
                result = self._execute_activity(activity)
                all_results.append(result)
                if result.success:
                    completed.add(activity.name)
                else:
                    return all_results
        return all_results

    def execute(self, pipeline: PipelineDefinition) -> list[ActivityResult]:
        logging.info(f"Starting pipeline execution: {pipeline.name}")
        logging.info(f"Total activities: {len(pipeline.activities)}")
        # Build execution order using topological sort
        execution_order = self._topological_sort(pipeline.activities)
        logging.info(f"Execution order determined for {len(execution_order)} activities")
        results: list[ActivityResult] = []
        completed: set[str] = set()
        for i, activity in enumerate(execution_order, 1):
            logging.info(f"[{i}/{len(execution_order)}] Processing activity: {activity.name}")
            # Verify dependencies are met
            for dep in activity.dependencies:
                if dep not in completed:
                    error_msg = f"Dependency not met: {dep}"
                    logging.error(f"Activity {activity.name}: {error_msg}")
                    results.append(
                        ActivityResult(
                            activity_name=activity.name,
                            success=False,
                            error_message=error_msg,
                        )
                    )
                    continue
            # Execute activity
            result = self._execute_activity(activity)
            results.append(result)
            if result.success:
                completed.add(activity.name)
                logging.info(f"✅ {activity.name} completed in {result.duration_seconds:.2f}s")
            else:
                logging.error(f"❌ {activity.name} failed: {result.error_message}")
        # Summary
        successful = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)
        total_duration = sum(r.duration_seconds for r in results)
        logging.info(f"\n{'=' * 60}")
        logging.info(f"Pipeline execution completed: {pipeline.name}")
        logging.info(f"Total activities: {len(results)}")
        logging.info(f"Successful: {successful}")
        logging.info(f"Failed: {failed}")
        logging.info(f"Total duration: {total_duration:.2f}s")
        logging.info(f"{'=' * 60}\n")
        return results

    def _topological_sort(self, activities: list[PipelineActivity]) -> list[PipelineActivity]:
        # Build adjacency list and in-degree count
        name_to_activity = {a.name: a for a in activities}
        in_degree = {a.name: 0 for a in activities}
        dependents: dict[str, list[str]] = {a.name: [] for a in activities}
        for activity in activities:
            for dep in activity.dependencies:
                if dep in name_to_activity:
                    in_degree[activity.name] += 1
                    dependents[dep].append(activity.name)
        # Start with activities that have no dependencies
        queue = deque([name for name, degree in in_degree.items() if degree == 0])
        sorted_activities: list[PipelineActivity] = []
        while queue:
            name = queue.popleft()
            sorted_activities.append(name_to_activity[name])
            # Reduce in-degree for dependents
            for dependent in dependents[name]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        # Check for cycles (if we didn't process all activities)
        if len(sorted_activities) != len(activities):
            unprocessed = set(name_to_activity.keys()) - {a.name for a in sorted_activities}
            raise ValueError(f"Circular dependency detected. Unprocessed activities: {unprocessed}")
        return sorted_activities

    def _execute_activity(self, activity: PipelineActivity) -> ActivityResult:
        start = time.time()
        try:
            if activity.layer == Layer.SETUP:
                runner = SetupRunner(connector=self.connector)
                runner.run(entity=activity.entity)
            elif activity.layer == Layer.LANDING or activity.layer == Layer.LANDING_COPYJOB:
                runner = LandingRunner(
                    connector=self.connector,
                    extractors=[
                        RestApiExtractor(secret_provider=self.secret_provider),
                        EntraUsersExtractor(secret_provider=self.secret_provider),
                        VerintAdherenceExtractor(secret_provider=self.secret_provider, connector=self.connector),
                        BlobExtractor(
                            secret_provider=self.secret_provider,
                            blob_source_factory=_MinioBlobSourceFactory(self.tagdataengineering_blob_minio_client),
                        ),
                        MySqlExtractor(secret_provider=self.secret_provider),
                        PostgresExtractor(secret_provider=self.secret_provider),
                        SqlServerExtractor(secret_provider=self.secret_provider),
                    ],
                )
                runner.run(metadata=activity.metadata)
            elif activity.layer == Layer.LANDING_COPYJOB_NORMALIZE:
                runner = LandingCopyJobNormalizeRunner(connector=self.connector, extractors=[])
                runner.run(metadata=activity.metadata)
            elif activity.layer in (Layer.BRONZE, Layer.SILVER, Layer.GOLD):
                runner = TransformationRunner(connector=self.connector)
                runner.run_transformation(metadata=activity.metadata)
            else:
                raise ValueError(f"Unsupported layer: {activity.layer}")
            duration = time.time() - start
            return ActivityResult(
                activity_name=activity.name,
                success=True,
                duration_seconds=duration,
            )
        except Exception as e:
            duration = time.time() - start
            logging.exception(f"Activity {activity.name} failed")
            return ActivityResult(
                activity_name=activity.name,
                success=False,
                error_message=str(e),
                duration_seconds=duration,
            )
