"""
Silver Companies Transformation - Microsoft Fabric User Data Function.

This function transforms company data from bronze to silver layer.
"""

import logging

import fabric.functions as fn
from tag_data_engineering.transformation_runner import TransformationRunner

from tag_data_engineering.connectors.fabric_lakehouse_connector import FabricLakehouseConnector


app = fn.UserDataFunctions()

logging.info("Module loaded: silver_companies")


@app.connection(argName="lakehouse", alias="Lakehouse")
@app.function()
def silver_companies(lakehouse: fn.FabricLakehouseClient) -> dict:
    """Transform companies data from bronze to silver layer."""
    logging.info(f"Function silver_companies called with lakehouse: {type(lakehouse)}")

    # Use Fabric connector (automatically gets Spark session from runtime)
    connector = FabricLakehouseConnector()
    logging.info(f"Spark version: {connector.spark.version}")

    runner = TransformationRunner(connector=connector)

    logging.info("Running silver.companies transformation...")
    result = runner.run_transformation(schema="silver", table="companies")

    return {
        "status": "Success",
        "message": f"Transformed {result.rows_processed} rows to silver.companies",
        "rows_processed": result.rows_processed,
        "duration_seconds": result.duration_seconds,
    }
