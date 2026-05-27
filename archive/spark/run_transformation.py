import sys

from pyspark.sql import SparkSession

from tag_data_engineering.connectors.fabric_lakehouse_connector import FabricLakehouseConnector
from tag_data_engineering.runners.landing_copyjob_normalize_runner import LandingCopyJobNormalizeRunner
from tag_data_engineering.runners.landing_runner import LandingRunner
from tag_data_engineering.runners.setup_runner import SetupRunner
from tag_data_engineering.runners.transformation_runner import TransformationRunner


def main() -> None:
    """Main entry point for the medallion transformation job."""
    # Parse command line arguments
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} '<layer> <entity>'")
        print(f"Example: {sys.argv[0]} 'landing people'")
        print(f"Example: {sys.argv[0]} 'bronze people'")
        sys.exit(1)

    args = sys.argv[1].split() if len(sys.argv) == 2 else sys.argv[1:]
    if len(args) < 2:
        print(f"Error: Expected 2 arguments (layer entity), got: {args}")
        sys.exit(1)

    layer = args[0].lower()
    entity = args[1]
    print(f"Target: {layer}/{entity}")

    spark = SparkSession.builder.getOrCreate()
    connector = FabricLakehouseConnector(spark)
    print(f"Running {layer}/{entity}")

    if layer == "setup":
        runner = SetupRunner(connector=connector)
        runner.run(entity=entity)
    elif layer == "landing":
        runner = LandingRunner(connector=connector)
        result = runner.run(entity=entity)
        print(f"✅ Landing extraction: {result.records_extracted} records in {result.duration_seconds}s")
    elif layer == "landing_copyjob_normalize":
        runner = LandingCopyJobNormalizeRunner(connector=connector)
        result = runner.run(entity=entity)
        print(f"✅ Copy Job Normalized: {result.records_extracted} records in {result.duration_seconds}s")
    elif layer in ("bronze", "silver", "gold"):
        runner = TransformationRunner(connector=connector)
        result = runner.run_transformation(schema=layer, table=entity)
        print(f"✅ Transformation: {result.rows_processed} rows in {result.duration_seconds}s")
    else:
        raise ValueError(f"Unknown layer: {layer}")


if __name__ == "__main__":
    main()
