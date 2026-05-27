from unittest.mock import Mock

import pytest

from tag_data_engineering import constants
from tag_data_engineering.deployment.fabric_serialization import serialize_copyjob_to_fabric
from tag_data_engineering.deployment.fabric_serialization import serialize_pipeline_to_fabric
from tag_data_engineering.extractors.copyjob_extractor import CopyJobExtractorConfig
from tag_data_engineering.extractors.copyjob_extractor import IncrementalConfig
from tag_data_engineering.models import SetupMetadata
from tag_data_engineering.pipeline.models import ActivityConfig
from tag_data_engineering.pipeline.models import IfConditionActivity
from tag_data_engineering.pipeline.models import InvokePipelineActivity
from tag_data_engineering.pipeline.models import Layer
from tag_data_engineering.pipeline.models import PipelineActivity
from tag_data_engineering.pipeline.models import PipelineDefinition


@pytest.fixture
def mock_fabric_conn():
    """Mock FabricConnection for testing serialization."""
    mock = Mock()
    # Mock connection ID lookups to return predictable values
    mock.get_connection_id_by_name.side_effect = lambda name: {
        constants.COPYJOB_CONNECTION_NAME: "940c99b6-af98-4d6c-9d4b-c442ecb33639",
        constants.LUMIN_PROD_AWS_CMS_MYSQL_CONNECTION_NAME: "b0ef9dbe-f0e8-4330-b345-d060dc0816fd",
        constants.LAKEHOUSE_CONNECTION_NAME: "1f175212-6baa-4e25-b641-b7472e9a5100",
    }[name]
    return mock


def test_serialize_setup_activity(mock_fabric_conn):
    pipeline = PipelineDefinition(
        name="test_pipeline",
        activities=[
            PipelineActivity(
                layer=Layer.SETUP,
                entity="metadata",
                config=ActivityConfig(),
                metadata=SetupMetadata(),
            ),
        ],
    )
    result = serialize_pipeline_to_fabric(
        pipeline,
        workspace_id="ws-123",
        notebook_id="nb-456",
        lakehouse_id="lh-789",
        fabric_conn=mock_fabric_conn,
    )
    activity = result["properties"]["activities"][0]
    assert activity["name"] == "setup_metadata"
    assert activity["type"] == "TridentNotebook"
    assert activity["dependsOn"] == []
    assert activity["policy"]["timeout"] == "0.12:00:00"
    assert activity["policy"]["retry"] == 3
    assert activity["typeProperties"]["notebookId"] == "nb-456"
    assert activity["typeProperties"]["workspaceId"] == "ws-123"
    assert activity["typeProperties"]["parameters"]["layer"]["value"] == "setup"
    assert activity["typeProperties"]["parameters"]["entity"]["value"] == "metadata"
    assert activity["typeProperties"]["defaultLakehouse"]["artifactId"] == "lh-789"


def test_serialize_landing_activity_with_dependencies(mock_fabric_conn):
    pipeline = PipelineDefinition(
        name="test_pipeline",
        activities=[
            PipelineActivity(
                layer=Layer.LANDING,
                entity="films",
                dependencies=["setup_metadata"],
                config=ActivityConfig(),
                metadata=SetupMetadata(),
            ),
        ],
    )
    result = serialize_pipeline_to_fabric(
        pipeline,
        workspace_id="ws-123",
        notebook_id="nb-456",
        lakehouse_id="lh-789",
        fabric_conn=mock_fabric_conn,
    )
    activity = result["properties"]["activities"][0]
    assert activity["name"] == "landing_films"
    assert activity["type"] == "TridentNotebook"
    assert len(activity["dependsOn"]) == 1
    assert activity["dependsOn"][0]["activity"] == "setup_metadata"
    assert activity["dependsOn"][0]["dependencyConditions"] == ["Succeeded"]


def test_serialize_copyjob_activity(mock_fabric_conn):
    pipeline = PipelineDefinition(
        name="test_pipeline",
        activities=[
            PipelineActivity(
                layer=Layer.LANDING_COPYJOB,
                entity="users",
                dependencies=["setup_metadata"],
                config=ActivityConfig(),
                metadata=SetupMetadata(),
            ),
        ],
    )
    copyjob_ids = {"landing_copyjob_users": "copyjob-123"}
    result = serialize_pipeline_to_fabric(
        pipeline,
        workspace_id="ws-123",
        notebook_id="nb-456",
        lakehouse_id="lh-789",
        fabric_conn=mock_fabric_conn,
        copyjob_ids=copyjob_ids,
    )
    activity = result["properties"]["activities"][0]
    assert activity["name"] == "landing_copyjob_users"
    assert activity["type"] == "InvokeCopyJob"
    assert activity["typeProperties"]["copyJobId"] == "copyjob-123"
    assert activity["typeProperties"]["workspaceId"] == "ws-123"
    assert activity["typeProperties"]["operationType"] == "RunCopyJob"
    assert activity["externalReferences"]["connection"] == "940c99b6-af98-4d6c-9d4b-c442ecb33639"
    assert len(activity["dependsOn"]) == 1
    assert activity["dependsOn"][0]["activity"] == "setup_metadata"


def test_serialize_activity_with_custom_timeout(mock_fabric_conn):
    pipeline = PipelineDefinition(
        name="test_pipeline",
        activities=[
            PipelineActivity(
                layer=Layer.BRONZE,
                entity="users",
                dependencies=["landing_users"],
                config=ActivityConfig(timeout_hours=2.5, retries=2, retry_interval_seconds=60),
                metadata=SetupMetadata(),
            ),
        ],
    )
    result = serialize_pipeline_to_fabric(
        pipeline,
        workspace_id="ws-123",
        notebook_id="nb-456",
        lakehouse_id="lh-789",
        fabric_conn=mock_fabric_conn,
    )
    activity = result["properties"]["activities"][0]
    assert activity["policy"]["timeout"] == "0.02:30:00"  # 2 hours 30 minutes
    assert activity["policy"]["retry"] == 2
    assert activity["policy"]["retryIntervalInSeconds"] == 60


def test_serialize_notebook_activity_with_extra_parameters(mock_fabric_conn):
    pipeline = PipelineDefinition(
        name="test_pipeline",
        activities=[
            PipelineActivity(
                layer=Layer.SETUP,
                entity="pipeline_group_success",
                config=ActivityConfig(),
                metadata=SetupMetadata(),
                parameters={
                    "pipeline_group": "cms",
                    "orchestrator_run_id": "@json(activity('setup_metadata').output.result.exitValue).orchestrator_run_id",
                },
            ),
        ],
    )

    result = serialize_pipeline_to_fabric(
        pipeline,
        workspace_id="ws-123",
        notebook_id="nb-456",
        lakehouse_id="lh-789",
        fabric_conn=mock_fabric_conn,
    )

    params = result["properties"]["activities"][0]["typeProperties"]["parameters"]
    assert params["pipeline_group"] == {"value": "cms", "type": "string"}
    assert params["orchestrator_run_id"]["type"] == "Expression"


def test_serialize_if_condition_activity(mock_fabric_conn):
    pipeline = PipelineDefinition(
        name="test_pipeline",
        activities=[
            PipelineActivity(
                layer=Layer.SETUP,
                entity="metadata",
                config=ActivityConfig(),
                metadata=SetupMetadata(),
            ),
            IfConditionActivity(
                name="if_group_due_cms",
                expression="@contains(json(activity('setup_metadata').output.result.exitValue).due_groups, 'cms')",
                dependencies=["setup_metadata"],
                if_true_activities=[
                    InvokePipelineActivity(
                        name="invoke_landing_cms",
                        pipeline_id="pipeline-cms",
                        config=ActivityConfig(),
                    ),
                    PipelineActivity(
                        layer=Layer.SETUP,
                        entity="pipeline_group_success",
                        dependencies=["invoke_landing_cms"],
                        config=ActivityConfig(),
                        metadata=SetupMetadata(),
                        parameters={"pipeline_group": "cms"},
                    ),
                ],
            ),
        ],
    )

    result = serialize_pipeline_to_fabric(
        pipeline,
        workspace_id="ws-123",
        notebook_id="nb-456",
        lakehouse_id="lh-789",
        fabric_conn=mock_fabric_conn,
    )

    activity = result["properties"]["activities"][1]
    assert activity["name"] == "if_group_due_cms"
    assert activity["type"] == "IfCondition"
    assert activity["dependsOn"][0]["activity"] == "setup_metadata"
    assert activity["typeProperties"]["expression"]["type"] == "Expression"
    true_activities = activity["typeProperties"]["ifTrueActivities"]
    assert [child["name"] for child in true_activities] == ["invoke_landing_cms", "setup_pipeline_group_success"]
    assert true_activities[1]["dependsOn"][0]["activity"] == "invoke_landing_cms"


def test_serialize_copyjob_activity_missing_id(mock_fabric_conn):
    pipeline = PipelineDefinition(
        name="test_pipeline",
        activities=[
            PipelineActivity(
                layer=Layer.LANDING_COPYJOB,
                entity="users",
                config=ActivityConfig(),
                metadata=SetupMetadata(),
            ),
        ],
    )
    with pytest.raises(ValueError, match="No CopyJob ID found"):
        serialize_pipeline_to_fabric(
            pipeline,
            workspace_id="ws-123",
            notebook_id="nb-456",
            lakehouse_id="lh-789",
            fabric_conn=mock_fabric_conn,
            copyjob_ids={},  # Empty mapping - missing ID
        )


def test_serialize_full_pipeline(mock_fabric_conn):
    pipeline = PipelineDefinition(
        name="test_pipeline",
        activities=[
            PipelineActivity(
                layer=Layer.SETUP,
                entity="metadata",
                config=ActivityConfig(),
                metadata=SetupMetadata(),
            ),
            PipelineActivity(
                layer=Layer.LANDING,
                entity="films",
                dependencies=["setup_metadata"],
                config=ActivityConfig(),
                metadata=SetupMetadata(),
            ),
            PipelineActivity(
                layer=Layer.BRONZE,
                entity="films",
                dependencies=["landing_films"],
                config=ActivityConfig(),
                metadata=SetupMetadata(),
            ),
        ],
    )
    result = serialize_pipeline_to_fabric(
        pipeline,
        workspace_id="ws-123",
        notebook_id="nb-456",
        lakehouse_id="lh-789",
        fabric_conn=mock_fabric_conn,
    )
    assert "properties" in result
    assert "activities" in result["properties"]
    assert len(result["properties"]["activities"]) == 3
    activities = result["properties"]["activities"]
    assert activities[0]["name"] == "setup_metadata"
    assert activities[0]["dependsOn"] == []
    assert activities[1]["name"] == "landing_films"
    assert len(activities[1]["dependsOn"]) == 1
    assert activities[2]["name"] == "bronze_films"
    assert len(activities[2]["dependsOn"]) == 1


def test_serialize_pipeline_with_copyjobs(mock_fabric_conn):
    pipeline = PipelineDefinition(
        name="test_pipeline",
        activities=[
            PipelineActivity(
                layer=Layer.SETUP,
                entity="metadata",
                config=ActivityConfig(),
                metadata=SetupMetadata(),
            ),
            PipelineActivity(
                layer=Layer.LANDING_COPYJOB,
                entity="users",
                dependencies=["setup_metadata"],
                config=ActivityConfig(),
                metadata=SetupMetadata(),
            ),
            PipelineActivity(
                layer=Layer.LANDING_COPYJOB_NORMALIZE,
                entity="users",
                dependencies=["landing_copyjob_users"],
                config=ActivityConfig(),
                metadata=SetupMetadata(),
            ),
        ],
    )
    copyjob_ids = {"landing_copyjob_users": "copyjob-abc-123"}
    result = serialize_pipeline_to_fabric(
        pipeline,
        workspace_id="ws-123",
        notebook_id="nb-456",
        lakehouse_id="lh-789",
        fabric_conn=mock_fabric_conn,
        copyjob_ids=copyjob_ids,
    )
    activities = result["properties"]["activities"]
    assert len(activities) == 3
    assert activities[1]["type"] == "InvokeCopyJob"
    assert activities[1]["typeProperties"]["copyJobId"] == "copyjob-abc-123"
    assert activities[2]["type"] == "TridentNotebook"
    assert activities[2]["name"] == "landing_copyjob_normalize_users"


def test_serialize_copyjob_batch_mode(mock_fabric_conn):
    """Test serialization of a Copy Job in Batch mode (full refresh)."""
    config = CopyJobExtractorConfig(
        source_connection=constants.LUMIN_PROD_AWS_CMS_MYSQL_CONNECTION_NAME,
        source_table="companies",
        source_type="MySqlTable",
        source_connection_type="MySql",
    )
    result = serialize_copyjob_to_fabric(
        config=config,
        workspace_id="ws-123",
        lakehouse_id="lh-789",
        entity_name="cms_companies",
        fabric_conn=mock_fabric_conn,
    )

    # Validate top-level properties
    assert result["properties"]["jobMode"] == "Batch"
    assert result["properties"]["source"]["type"] == "MySqlTable"
    assert result["properties"]["source"]["connectionSettings"]["type"] == "MySql"
    assert result["properties"]["destination"]["type"] == "Json"
    assert result["properties"]["destination"]["connectionSettings"]["type"] == "Lakehouse"
    assert result["properties"]["policy"]["timeout"] == "0.12:00:00"

    # Validate workspace/lakehouse IDs
    dest_props = result["properties"]["destination"]["connectionSettings"]["typeProperties"]
    assert dest_props["workspaceId"] == "ws-123"
    assert dest_props["artifactId"] == "lh-789"
    assert dest_props["rootFolder"] == "Files"

    # Validate activity
    activities = result["activities"]
    assert len(activities) == 1
    activity = activities[0]
    assert activity["id"] == "activity_companies"
    assert activity["properties"]["source"]["datasetSettings"]["table"] == "`companies`"

    # Validate destination settings
    dest = activity["properties"]["destination"]
    assert dest["datasetSettings"]["location"]["type"] == "LakehouseLocation"
    assert dest["datasetSettings"]["location"]["fileName"] == "data.json"
    assert dest["datasetSettings"]["location"]["folderPath"] == "copyjob_raw/cms_companies"
    assert dest["formatSettings"]["type"] == "JsonWriteSettings"
    assert dest["formatSettings"]["fileExtension"] == ".json"

    # Should NOT have CDC settings in Batch mode
    assert "changeDataSettings" not in activity["properties"]["source"]


def test_serialize_copyjob_cdc_mode(mock_fabric_conn):
    """Test serialization of a Copy Job in CDC mode (incremental)."""
    config = CopyJobExtractorConfig(
        source_connection=constants.LUMIN_PROD_AWS_CMS_MYSQL_CONNECTION_NAME,
        source_table="companies",
        source_type="MySqlTable",
        source_connection_type="MySql",
        incremental=IncrementalConfig(
            column="updated_at",
            column_type="DateTime",
        ),
    )
    result = serialize_copyjob_to_fabric(
        config=config,
        workspace_id="ws-123",
        lakehouse_id="lh-789",
        entity_name="cms_companies",
        fabric_conn=mock_fabric_conn,
    )

    # Validate CDC mode
    assert result["properties"]["jobMode"] == "CDC"

    # Validate CDC settings in activity
    activities = result["activities"]
    activity = activities[0]
    source = activity["properties"]["source"]

    assert "changeDataSettings" in source
    assert source["changeDataSettings"]["readMethod"] == "SnapshotPlusIncremental"
    assert len(source["changeDataSettings"]["columns"]) == 1

    cdc_column = source["changeDataSettings"]["columns"][0]
    assert cdc_column["name"] == "updated_at"
    assert cdc_column["type"] == "DateTime"
    assert cdc_column["physicalType"] == "DateTime"


def test_serialize_copyjob_different_table(mock_fabric_conn):
    """Test serialization with different table name."""
    config = CopyJobExtractorConfig(
        source_connection=constants.LUMIN_PROD_AWS_CMS_MYSQL_CONNECTION_NAME,
        source_table="order_items",
        source_type="MySqlTable",
        source_connection_type="MySql",
    )
    result = serialize_copyjob_to_fabric(
        config=config,
        workspace_id="ws-456",
        lakehouse_id="lh-abc",
        entity_name="orders_items",
        fabric_conn=mock_fabric_conn,
    )

    assert result["properties"]["source"]["type"] == "MySqlTable"
    assert result["properties"]["source"]["connectionSettings"]["type"] == "MySql"
    activities = result["activities"]
    assert activities[0]["id"] == "activity_order_items"
    assert activities[0]["properties"]["source"]["datasetSettings"]["table"] == "`order_items`"


def test_serialize_copyjob_int_incremental(mock_fabric_conn):
    """Test serialization with integer-based incremental column."""
    config = CopyJobExtractorConfig(
        source_connection=constants.LUMIN_PROD_AWS_CMS_MYSQL_CONNECTION_NAME,
        source_table="users",
        source_type="MySqlTable",
        source_connection_type="MySql",
        incremental=IncrementalConfig(
            column="id",
            column_type="Int",
        ),
    )
    result = serialize_copyjob_to_fabric(
        config=config,
        workspace_id="ws-123",
        lakehouse_id="lh-789",
        entity_name="cms_users",
        fabric_conn=mock_fabric_conn,
    )

    # Validate incremental column type
    activities = result["activities"]
    cdc_column = activities[0]["properties"]["source"]["changeDataSettings"]["columns"][0]
    assert cdc_column["name"] == "id"
    assert cdc_column["type"] == "Int"
    assert cdc_column["physicalType"] == "Int"


def test_serialize_copyjob_invalid_connection(mock_fabric_conn):
    """Test that invalid connection name raises RuntimeError."""
    # Configure mock to raise RuntimeError for unknown connection
    mock_fabric_conn.get_connection_id_by_name.side_effect = RuntimeError("Connection 'UnknownConnection' not found")

    config = CopyJobExtractorConfig(
        source_connection="UnknownConnection",
        source_table="companies",
        source_type="MySqlTable",
        source_connection_type="MySql",
    )

    with pytest.raises(RuntimeError, match="Connection 'UnknownConnection' not found"):
        serialize_copyjob_to_fabric(
            config=config,
            workspace_id="ws-123",
            lakehouse_id="lh-789",
            entity_name="cms_companies",
            fabric_conn=mock_fabric_conn,
        )


def test_serialize_copyjob_external_references(mock_fabric_conn):
    """Test that external references for connections are set correctly."""
    config = CopyJobExtractorConfig(
        source_connection=constants.LUMIN_PROD_AWS_CMS_MYSQL_CONNECTION_NAME,
        source_table="companies",
        source_type="MySqlTable",
        source_connection_type="MySql",
    )
    result = serialize_copyjob_to_fabric(
        config=config,
        workspace_id="ws-123",
        lakehouse_id="lh-789",
        entity_name="cms_companies",
        fabric_conn=mock_fabric_conn,
    )

    # Validate source connection reference
    source_refs = result["properties"]["source"]["connectionSettings"]["externalReferences"]
    assert "connection" in source_refs
    # Should match a value from CONNECTIONS dict (we know MySQL_CMS should be there)
    assert source_refs["connection"] is not None

    # # Validate destination connection reference
    # dest_refs = result["properties"]["destination"]["connectionSettings"]["externalReferences"]
    # assert "connection" in dest_refs
    # # Should be Fabric_Lakehouse connection
    # assert dest_refs["connection"] is not None


def test_serialize_copyjob_translator_settings(mock_fabric_conn):
    """Test that translator and type conversion settings are included."""
    config = CopyJobExtractorConfig(
        source_connection=constants.LUMIN_PROD_AWS_CMS_MYSQL_CONNECTION_NAME,
        source_table="companies",
        source_type="MySqlTable",
        source_connection_type="MySql",
    )
    result = serialize_copyjob_to_fabric(
        config=config,
        workspace_id="ws-123",
        lakehouse_id="lh-789",
        entity_name="cms_companies",
        fabric_conn=mock_fabric_conn,
    )

    activity = result["activities"][0]["properties"]
    assert activity["enableStaging"] is False
    assert activity["translator"]["type"] == "TabularTranslator"
    assert activity["typeConversionSettings"]["typeConversion"]["allowDataTruncation"] is True
    assert activity["typeConversionSettings"]["typeConversion"]["treatBooleanAsNumber"] is False


def test_serialize_invoke_pipeline_activity(mock_fabric_conn):
    pipeline = PipelineDefinition(
        name="orchestrator",
        activities=[
            PipelineActivity(
                layer=Layer.SETUP,
                entity="metadata",
                config=ActivityConfig(),
                metadata=SetupMetadata(),
            ),
            InvokePipelineActivity(
                name="invoke_landing_cms",
                pipeline_id="pipeline-id-123",
                dependencies=["setup_metadata"],
                config=ActivityConfig(),
            ),
        ],
    )
    result = serialize_pipeline_to_fabric(
        pipeline,
        workspace_id="ws-123",
        notebook_id="nb-456",
        lakehouse_id="lh-789",
        fabric_conn=mock_fabric_conn,
    )
    activities = result["properties"]["activities"]
    assert len(activities) == 2
    setup = activities[0]
    assert setup["name"] == "setup_metadata"
    assert setup["type"] == "TridentNotebook"
    invoke = activities[1]
    assert invoke["name"] == "invoke_landing_cms"
    assert invoke["type"] == "ExecutePipeline"
    assert invoke["typeProperties"]["pipeline"]["referenceName"] == "pipeline-id-123"
    assert invoke["typeProperties"]["pipeline"]["type"] == "PipelineReference"
    assert invoke["typeProperties"]["waitOnCompletion"] is True
    assert "externalReferences" not in invoke
    assert len(invoke["dependsOn"]) == 1
    assert invoke["dependsOn"][0]["activity"] == "setup_metadata"
    assert invoke["dependsOn"][0]["dependencyConditions"] == ["Succeeded"]
