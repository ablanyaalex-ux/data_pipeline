import json
import os
from collections.abc import Generator

import pytest
from minio import Minio
from pyspark.sql import SparkSession

from tag_data_engineering.connectors.local_lakehouse_connector import LocalLakehouseConnector
from tag_data_engineering.models import ExtractionMetadata
from tag_data_engineering.pipeline.models import PipelineDefinition
from tag_data_engineering.pipeline.pipeline_discoverer import PipelineDiscoverer
from tag_data_engineering.runners.setup_runner import SetupRunner
from tag_data_engineering.secrets.mock_secret_provider import MockSecretProvider
from tag_data_engineering.secrets.secret_provider import SecretProvider
from tests_integration.pipeline_executor import PipelineExecutor


@pytest.fixture(scope="session")
def minio_settings() -> dict[str, str]:
    if os.environ.get("MINIO_ENDPOINT") is None:
        pytest.skip("Requires Docker environment with MinIO")
    return {
        "endpoint": os.environ["MINIO_ENDPOINT"],
        "access_key": os.environ.get("MINIO_ACCESS_KEY", "minioadmin"),
        "secret_key": os.environ.get("MINIO_SECRET_KEY", "minioadmin"),
        "bucket": os.environ.get("MINIO_BUCKET", "test-lakehouse"),
    }


@pytest.fixture(scope="session")
def minio_client(minio_settings: dict[str, str]) -> Minio:
    return Minio(
        endpoint=minio_settings["endpoint"],
        access_key=minio_settings["access_key"],
        secret_key=minio_settings["secret_key"],
        secure=False,
    )


@pytest.fixture(scope="session")
def tagdataengineering_blob_minio_client() -> Minio:
    if os.environ.get("TAGDATAENGINEERING_BLOB_ENDPOINT") is None:
        pytest.skip("Requires Docker environment with tagdataengineering blob storage")
    minio_endpoint = os.environ["TAGDATAENGINEERING_BLOB_ENDPOINT"]
    minio_access_key = os.environ.get("TAGDATAENGINEERING_BLOB_ACCESS_KEY", "minioadmin")
    minio_secret_key = os.environ.get("TAGDATAENGINEERING_BLOB_SECRET_KEY", "minioadmin")
    return Minio(
        endpoint=minio_endpoint,
        access_key=minio_access_key,
        secret_key=minio_secret_key,
        secure=False,
    )


@pytest.fixture(scope="session")
def spark_session(minio_client: Minio, minio_settings: dict[str, str]) -> Generator[SparkSession, None, None]:
    minio_bucket = minio_settings["bucket"]
    if minio_client.bucket_exists(bucket_name=minio_bucket):
        objects = minio_client.list_objects(minio_bucket, recursive=True)
        for obj in objects:
            minio_client.remove_object(minio_bucket, obj.object_name)
    else:
        minio_client.make_bucket(bucket_name=minio_bucket)
    spark = (
        SparkSession.builder.appName("TestSession")
        .master("local[*]")
        .config(
            "spark.jars.packages",
            ",".join(
                [
                    "io.delta:delta-spark_2.12:3.2.0",
                    "org.apache.hadoop:hadoop-aws:3.3.4",
                    "com.amazonaws:aws-java-sdk-bundle:1.12.262",
                ]
            ),
        )
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.warehouse.dir", f"s3a://{minio_bucket}/")
        .config("spark.hadoop.hive.metastore.warehouse.dir", f"s3a://{minio_bucket}/")
        # Keep joins non-broadcast in integration runs to prevent driver OOM during merge-heavy gold transforms.
        .config("spark.sql.autoBroadcastJoinThreshold", "-1")
        .config("spark.sql.adaptive.autoBroadcastJoinThreshold", "-1")
        .config("spark.hadoop.fs.s3a.endpoint", f"http://{minio_settings['endpoint']}")
        .config("spark.hadoop.fs.s3a.access.key", minio_settings["access_key"])
        .config("spark.hadoop.fs.s3a.secret.key", minio_settings["secret_key"])
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .getOrCreate()
    )
    yield spark
    spark.stop()


@pytest.fixture(scope="session")
def lakehouse_connector(spark_session: SparkSession, minio_settings: dict[str, str]) -> LocalLakehouseConnector:
    base_path = f"s3a://{minio_settings['bucket']}"
    connector = LocalLakehouseConnector(
        spark=spark_session,
        base_path=base_path,
    )
    connector._lakehouse_name = "integration_test"
    return connector


@pytest.fixture(autouse=True)
def cleanup_schemas(request: pytest.FixtureRequest):
    # Only run cleanup if spark_session fixture is being used by the test
    if "spark_session" not in request.fixturenames:
        yield
        return
    spark_session = request.getfixturevalue("spark_session")
    for schema in ["_metadata", "bronze", "silver", "gold", "test_entity", "test_copyjob_entity"]:
        try:
            spark_session.sql(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        except Exception:
            pass
    yield
    for schema in ["_metadata", "bronze", "silver", "gold", "test_entity", "test_copyjob_entity"]:
        try:
            spark_session.sql(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        except Exception:
            pass


@pytest.fixture
def setup_metadata_tables(spark_session: SparkSession):
    setup_runner = SetupRunner(spark=spark_session)
    setup_runner.run(entity="metadata")


def _patch_activity_metadata(activity):
    if isinstance(activity.metadata, ExtractionMetadata) and activity.metadata.entity == "entra_users":
        if isinstance(activity.metadata.extractor_config, dict):
            activity.metadata.extractor_config["base_url"] = os.environ["ENTRA_GRAPH_BASE_URL"]
            activity.metadata.extractor_config["login_base_url"] = f"{os.environ['ENTRA_GRAPH_BASE_URL']}/login"
    # Patch Verint REST API to use mock container
    if isinstance(activity.metadata, ExtractionMetadata) and activity.metadata.entity == "verint_employee_adherence":
        activity.metadata.extractor_config["base_url"] = os.environ["VERINT_BASE_URL"]
    if isinstance(activity.metadata, ExtractionMetadata) and activity.metadata.extractor == "mysql":
        source_system = activity.metadata.extractor_config.get("source_system")
        if source_system == "popla":
            activity.metadata.extractor_config["source_database"] = os.environ["POPLA_MYSQL_DATABASE"]
        elif source_system == "cms":
            activity.metadata.extractor_config["source_database"] = os.environ["CMS_MYSQL_DATABASE"]
        elif source_system == "orn_ic_portal":
            activity.metadata.extractor_config["source_database"] = os.environ["ORN_IC_PORTAL_MYSQL_DATABASE"]


@pytest.fixture(scope="session")
def pipeline() -> PipelineDefinition:
    discoverer = PipelineDiscoverer()
    pipeline_def = discoverer.build_pipeline(name="integration_test")
    for activity in pipeline_def.activities:
        _patch_activity_metadata(activity)
    return pipeline_def


@pytest.fixture(scope="session")
def subpipelines() -> dict[str, PipelineDefinition]:
    discoverer = PipelineDiscoverer()
    subs = discoverer.build_subpipelines(base_name="integration_test")
    for sub_pipeline in subs.values():
        for activity in sub_pipeline.activities:
            _patch_activity_metadata(activity)
    return subs


@pytest.fixture(scope="session")
def orchestrator(subpipelines: dict[str, PipelineDefinition]) -> PipelineDefinition:
    discoverer = PipelineDiscoverer()
    child_pipeline_ids = {key: f"fake-id-{key}" for key in subpipelines}
    return discoverer.build_orchestrator(name="integration_test_orchestrator", child_pipeline_ids=child_pipeline_ids)


@pytest.fixture(scope="session")
def secret_provider() -> SecretProvider:
    return MockSecretProvider(
        secrets={
            "entra-tenant-id": "test-tenant-id",
            "entra-client-id": "test-client-id",
            "entra-client-secret": "test-client-secret",
            "de-sp-credentials": '{"client_id":"test-client-id","client_secret":"test-client-secret"}',
            "verint-api-key": "test-verint-key-id",
            "verint-api-secret": "test-verint-api-key",
            "verint-prod-api-credentials": '{"api_key":"test-verint-key-id","api_secret":"test-verint-api-key"}',
            "blob_account_url": "https://testaccount.blob.core.windows.net",
            "data-ingest-storage-credentials": '{"account_name":"test123"}',
            "myhr-storage-credentials": '{"account_name":"test1234"}',
            "tenant-id": "test-tenant-id",
            "client-id": "test-client-id",
            "client-secret": "test-client-secret",
            "lumin-prod-aws-cms-mysql-credentials": json.dumps(
                {
                    "host": os.environ["CMS_MYSQL_HOST"],
                    "port": os.environ["CMS_MYSQL_PORT"],
                    "username": os.environ["CMS_MYSQL_USER"],
                    "password": os.environ["CMS_MYSQL_PASSWORD"],
                }
            ),
            "lumin-prod-aws-icportal-mysql-credentials": json.dumps(
                {
                    "host": os.environ["ORN_IC_PORTAL_MYSQL_HOST"],
                    "port": os.environ["ORN_IC_PORTAL_MYSQL_PORT"],
                    "username": os.environ["ORN_IC_PORTAL_MYSQL_USER"],
                    "password": os.environ["ORN_IC_PORTAL_MYSQL_PASSWORD"],
                }
            ),
            "lumin-prod-aws-popla-mysql-credentials": json.dumps(
                {
                    "host": os.environ["POPLA_MYSQL_HOST"],
                    "port": os.environ["POPLA_MYSQL_PORT"],
                    "username": os.environ["POPLA_MYSQL_USER"],
                    "password": os.environ["POPLA_MYSQL_PASSWORD"],
                }
            ),
            "lumin-prod-aws-cms-psql-credentials": json.dumps(
                {
                    "host": os.environ["CMS_POSTGRES_HOST"],
                    "port": os.environ["CMS_POSTGRES_PORT"],
                    "username": os.environ["CMS_POSTGRES_USER"],
                    "password": os.environ["CMS_POSTGRES_PASSWORD"],
                    "database": os.environ["CMS_POSTGRES_DATABASE"],
                }
            ),
            "puzzel-mssql-credentials": json.dumps(
                {
                    "host": os.environ["PUZZEL_SQLSERVER_HOST"],
                    "port": os.environ["PUZZEL_SQLSERVER_PORT"],
                    "username": os.environ["PUZZEL_SQLSERVER_USER"],
                    "password": os.environ["PUZZEL_SQLSERVER_PASSWORD"],
                    "database": os.environ["PUZZEL_SQLSERVER_DATABASE"],
                }
            ),
            "blob_account_url_keyvault": "detestaccount",
        }
    )


@pytest.fixture(scope="session")
def pipeline_executor(
    spark_session: SparkSession,
    lakehouse_connector: LocalLakehouseConnector,
    secret_provider: SecretProvider,
    tagdataengineering_blob_minio_client: Minio,  # tagdataengineering blob storage MinIO client
) -> PipelineExecutor:
    return PipelineExecutor(
        spark=spark_session,
        connector=lakehouse_connector,
        secret_provider=secret_provider,
        tagdataengineering_blob_minio_client=tagdataengineering_blob_minio_client,  # tagdataengineering blob MinIO client
    )
