from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pyspark.sql.types import IntegerType
from pyspark.sql.types import LongType
from pyspark.sql.types import MapType
from pyspark.sql.types import StringType
from pyspark.sql.types import StructField
from pyspark.sql.types import StructType
from pyspark.sql.types import TimestampType


class MetadataTableConfig(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,  # Allow StructType
        populate_by_name=True,
    )

    name: str
    schema_definition: StructType = Field(alias="schema")
    partition_by: list[str]


LANDING_RUNS_SCHEMA = StructType(
    [
        StructField("entity", StringType(), nullable=False),
        StructField("run_id", StringType(), nullable=False),
        StructField("started_at", TimestampType(), nullable=False),
        StructField("completed_at", TimestampType(), nullable=False),
        StructField("status", StringType(), nullable=False),
        StructField("file_count", IntegerType(), nullable=True),
        StructField("total_record_count", LongType(), nullable=True),
        StructField("error_message", StringType(), nullable=True),
        StructField("cursor", MapType(StringType(), StringType()), nullable=True),
    ]
)


BRONZE_RUNS_SCHEMA = StructType(
    [
        StructField("entity", StringType(), nullable=False),
        StructField("run_id", StringType(), nullable=False),
        StructField("started_at", TimestampType(), nullable=False),
        StructField("completed_at", TimestampType(), nullable=False),
        StructField("status", StringType(), nullable=False),
        StructField("rows_processed", LongType(), nullable=True),
        StructField("error_message", StringType(), nullable=True),
    ]
)


METADATA_TABLES: list[MetadataTableConfig] = [
    MetadataTableConfig(
        name="landing_runs",
        schema=LANDING_RUNS_SCHEMA,
        partition_by=["entity"],
    ),
    MetadataTableConfig(
        name="bronze_runs",
        schema=BRONZE_RUNS_SCHEMA,
        partition_by=["entity"],
    ),
]
