from tag_data_engineering import constants
from tag_data_engineering.deployment.fabric_connection import FabricConnection
from tag_data_engineering.extractors.copyjob_extractor import CopyJobExtractorConfig
from tag_data_engineering.pipeline.models import IfConditionActivity
from tag_data_engineering.pipeline.models import InvokePipelineActivity
from tag_data_engineering.pipeline.models import Layer
from tag_data_engineering.pipeline.models import PipelineActivity
from tag_data_engineering.pipeline.models import PipelineDefinition


def serialize_pipeline_to_fabric(
    pipeline: PipelineDefinition,
    workspace_id: str,
    notebook_id: str,
    lakehouse_id: str,
    fabric_conn: FabricConnection,
    copyjob_ids: dict[str, str] | None = None,
) -> dict:
    activities = []
    for activity in pipeline.activities:
        if isinstance(activity, IfConditionActivity):
            activities.append(_serialize_if_condition_activity_to_fabric(activity, workspace_id, notebook_id, lakehouse_id, fabric_conn, copyjob_ids))
        elif isinstance(activity, InvokePipelineActivity):
            activities.append(_serialize_invoke_pipeline_activity_to_fabric(activity, workspace_id))
        else:
            activities.append(_serialize_activity_to_fabric(activity, workspace_id, notebook_id, lakehouse_id, fabric_conn, copyjob_ids))
    return {
        "properties": {
            "activities": activities,
        }
    }


def _serialize_activity_to_fabric(
    activity: PipelineActivity,
    workspace_id: str,
    notebook_id: str,
    lakehouse_id: str,
    fabric_conn: FabricConnection,
    copyjob_ids: dict[str, str] | None = None,
) -> dict:
    depends_on = [
        {
            "activity": dep,
            "dependencyConditions": ["Succeeded"],
        }
        for dep in activity.dependencies
    ]
    if activity.layer == Layer.LANDING_COPYJOB:
        copyjob_id = copyjob_ids.get(activity.name) if copyjob_ids else None
        if not copyjob_id:
            raise ValueError(f"No CopyJob ID found for activity: {activity.name}")
        return _serialize_copy_job_activity_to_fabric(activity, workspace_id, copyjob_id, fabric_conn, depends_on)
    return _serialize_notebook_activity_to_fabric(activity, workspace_id, notebook_id, lakehouse_id, depends_on)


def _serialize_copy_job_activity_to_fabric(
    activity: PipelineActivity,
    workspace_id: str,
    copyjob_id: str,
    fabric_conn: FabricConnection,
    depends_on: list[dict],
) -> dict:
    copyjob_connection_id = fabric_conn.get_connection_id_by_name(constants.COPYJOB_CONNECTION_NAME)
    return {
        "name": activity.name,
        "type": "InvokeCopyJob",
        "dependsOn": depends_on,
        "policy": {
            "timeout": "0.12:00:00",
            "retry": 0,
            "retryIntervalInSeconds": 30,
            "secureOutput": False,
            "secureInput": False,
        },
        "typeProperties": {
            "copyJobId": copyjob_id,
            "workspaceId": workspace_id,
            "operationType": "RunCopyJob",
        },
        "externalReferences": {
            "connection": copyjob_connection_id,
        },
    }


def _serialize_notebook_activity_to_fabric(
    activity: PipelineActivity,
    workspace_id: str,
    notebook_id: str,
    lakehouse_id: str,
    depends_on: list[dict],
) -> dict:
    hours = int(activity.config.timeout_hours)
    minutes = int((activity.config.timeout_hours - hours) * 60)
    timeout_str = f"0.{hours:02d}:{minutes:02d}:00"
    parameters = {
        "layer": {
            "value": activity.layer.value,
            "type": "string",
        },
        "entity": {
            "value": activity.entity,
            "type": "string",
        },
    }
    for key, value in activity.parameters.items():
        parameters[key] = {
            "value": value,
            "type": "Expression" if isinstance(value, str) and value.startswith("@") else "string",
        }

    return {
        "name": activity.name,
        "type": "TridentNotebook",
        "dependsOn": depends_on,
        "policy": {
            "timeout": timeout_str,
            "retry": activity.config.retries,
            "retryIntervalInSeconds": activity.config.retry_interval_seconds,
            "secureOutput": False,
            "secureInput": False,
        },
        "typeProperties": {
            "notebookId": notebook_id,
            "workspaceId": workspace_id,
            "parameters": parameters,
            "defaultLakehouse": {
                "workspaceId": workspace_id,
                "artifactId": lakehouse_id,
            },
        },
    }


def _serialize_if_condition_activity_to_fabric(
    activity: IfConditionActivity,
    workspace_id: str,
    notebook_id: str,
    lakehouse_id: str,
    fabric_conn: FabricConnection,
    copyjob_ids: dict[str, str] | None = None,
) -> dict:
    depends_on = [
        {
            "activity": dep,
            "dependencyConditions": ["Succeeded"],
        }
        for dep in activity.dependencies
    ]
    if_true_activities = [
        _serialize_invoke_pipeline_activity_to_fabric(child, workspace_id)
        if isinstance(child, InvokePipelineActivity)
        else _serialize_activity_to_fabric(child, workspace_id, notebook_id, lakehouse_id, fabric_conn, copyjob_ids)
        for child in activity.if_true_activities
    ]
    if_false_activities = [
        _serialize_invoke_pipeline_activity_to_fabric(child, workspace_id)
        if isinstance(child, InvokePipelineActivity)
        else _serialize_activity_to_fabric(child, workspace_id, notebook_id, lakehouse_id, fabric_conn, copyjob_ids)
        for child in activity.if_false_activities
    ]
    return {
        "name": activity.name,
        "type": "IfCondition",
        "dependsOn": depends_on,
        "typeProperties": {
            "expression": {
                "value": activity.expression,
                "type": "Expression",
            },
            "ifTrueActivities": if_true_activities,
            "ifFalseActivities": if_false_activities,
        },
    }


def _serialize_invoke_pipeline_activity_to_fabric(
    activity: InvokePipelineActivity,
    workspace_id: str,
) -> dict:
    depends_on = [
        {
            "activity": dep,
            "dependencyConditions": ["Succeeded"],
        }
        for dep in activity.dependencies
    ]
    hours = int(activity.config.timeout_hours)
    minutes = int((activity.config.timeout_hours - hours) * 60)
    timeout_str = f"0.{hours:02d}:{minutes:02d}:00"
    return {
        "name": activity.name,
        "type": "ExecutePipeline",
        "dependsOn": depends_on,
        "policy": {
            "timeout": timeout_str,
            "retry": activity.config.retries,
            "retryIntervalInSeconds": activity.config.retry_interval_seconds,
            "secureOutput": False,
            "secureInput": False,
        },
        "typeProperties": {
            "pipeline": {
                "referenceName": activity.pipeline_id,
                "type": "PipelineReference",
            },
            "waitOnCompletion": activity.wait_on_completion,
        },
    }


def serialize_copyjob_to_fabric(
    config: CopyJobExtractorConfig,
    workspace_id: str,
    lakehouse_id: str,
    entity_name: str,
    fabric_conn: FabricConnection,
) -> dict:
    source_conn_id = fabric_conn.get_connection_id_by_name(config.source_connection)
    # dest_conn_id = fabric_conn.get_connection_id_by_name(constants.LAKEHOUSE_CONNECTION_NAME)

    # Build source dataset settings based on connection type
    if config.source_connection_type == "AzureSqlDatabase":
        # Azure SQL uses schema and table separately
        source_dataset_settings = {
            "schema": config.source_schema or "dbo",
            "table": config.source_table,
        }
    elif config.source_connection_type == "AzureBlobStorage":
        location_config = {
            "type": "AzureBlobStorageLocation",
            "container": config.source_container,  # Use container field for container name
        }
        # Add folderPath if source_folder is specified
        if config.source_folder:
            location_config["folderPath"] = config.source_folder
        # Azure Blob Storage supports different dataset settings depending on file type.
        # We branch here so Fabric Copy Jobs are configured correctly for each format.
        if config.source_type == "DelimitedText":
            # CSV files from Azure Blob Storage (e.g. Verint exports)
            source_dataset_settings = {
                "location": location_config,
                "columnDelimiter": ",",  # for CSV files only
                "escapeChar": "\\",
                "firstRowAsHeader": True,
                "quoteChar": '"',
            }
        elif config.source_type == "Excel":
            # Excel copy jobs require a sheet name.
            if not config.source_sheet_name:
                raise ValueError("Missing required 'source_sheet_name' for AzureBlobStorage Excel source. Please set 'source_sheet_name' in landing metadata extractor_config.")
            # Excel files from Azure Blob Storage (e.g. HR hierarchy spreadsheets)
            # Sheet name is provided via landing metadata
            source_dataset_settings = {
                "location": location_config,
                "sheetName": config.source_sheet_name,
                "firstRowAsHeader": True,
            }
        else:
            # Fail fast if a new/unsupported blob file type is configured
            raise ValueError(f"Unsupported source_type '{config.source_type}' for AzureBlobStorage. Only 'DelimitedText' (CSV) and 'Excel' are currently supported.")
    elif config.source_connection_type == "PostgreSql":
        # PostgreSQL uses schema and table
        source_dataset_settings = {
            "schema": config.source_schema or "public",
            "table": config.source_table,
        }
    else:
        # MySQL uses backtick-quoted table name
        source_dataset_settings = {
            "table": f"`{config.source_table}`",
        }

    source_settings: dict = {
        "datasetSettings": source_dataset_settings,
    }
    # Add store settings for Azure Blob Storage
    if config.source_connection_type == "AzureBlobStorage":
        source_settings["storeSettings"] = {
            "recursive": True,
            "enablePartitionDiscovery": False,
        }
    if config.incremental and config.incremental.column:
        source_settings["changeDataSettings"] = {
            "readMethod": "SnapshotPlusIncremental",
            "columns": [
                {
                    "name": config.incremental.column,
                    "type": config.incremental.column_type,
                    "physicalType": config.incremental.column_type,
                },
            ],
        }
    folder_path = f"copyjob_raw/{entity_name}"
    file_name = "data"  # We can use a fixed name, CDC handles versions
    file_extension = "json"

    # Build connection settings with database if needed
    source_connection_settings: dict = {
        "type": config.source_connection_type,
        "externalReferences": {
            "connection": source_conn_id,
        },
    }
    if config.source_database:
        source_connection_settings["typeProperties"] = {
            "database": config.source_database,
        }

    return {
        "properties": {
            "jobMode": "CDC" if config.incremental else "Batch",
            "source": {
                "type": config.source_type,
                "connectionSettings": source_connection_settings,
            },
            "destination": {
                "type": "Json",  # Always JSON for now
                "connectionSettings": {
                    "type": "Lakehouse",
                    "typeProperties": {
                        "workspaceId": workspace_id,
                        "artifactId": lakehouse_id,
                        "rootFolder": "Files",
                    },
                    # "externalReferences": {
                    #     "connection": dest_conn_id,
                    # },
                },
            },
            "policy": {
                "timeout": "0.12:00:00",
            },
        },
        "activities": [
            {
                "id": f"activity_{config.source_table or entity_name}",
                "properties": {
                    "source": source_settings,
                    "destination": {
                        "datasetSettings": {
                            "location": {
                                "type": "LakehouseLocation",
                                "fileName": f"{file_name}.{file_extension}",
                                "folderPath": folder_path,
                            },
                        },
                        "storeSettings": {
                            "copyBehavior": "MergeFiles" if config.source_connection_type == "AzureBlobStorage" else {},
                        }
                        if config.source_connection_type == "AzureBlobStorage"
                        else {},
                        "formatSettings": {
                            "type": "JsonWriteSettings",
                            "fileExtension": f".{file_extension}",
                        },
                    },
                    "enableStaging": False,
                    "translator": {
                        "type": "TabularTranslator",
                    },
                    "typeConversionSettings": {
                        "typeConversion": {
                            "allowDataTruncation": True,
                            "treatBooleanAsNumber": False,
                        },
                    },
                },
            },
        ],
    }
