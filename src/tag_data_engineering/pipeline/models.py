from __future__ import annotations

from enum import Enum

from pydantic import BaseModel
from pydantic import Field

from tag_data_engineering.models import BronzeMetadata
from tag_data_engineering.models import ExtractionMetadata
from tag_data_engineering.models import SetupMetadata
from tag_data_engineering.models import TransformationMetadata


JobMetadata = SetupMetadata | ExtractionMetadata | BronzeMetadata | TransformationMetadata


class Layer(str, Enum):
    SETUP = "setup"
    LANDING = "landing"  # Internal extractors (REST API, etc.) - notebook
    LANDING_COPYJOB = "landing_copyjob"  # Fabric Copy Job invocation - NOT a notebook
    LANDING_COPYJOB_NORMALIZE = "landing_copyjob_normalize"  # Copy Job normalization - notebook
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    LAB = "lab"

    @property
    def layer_group(self) -> str:
        if self in (Layer.LANDING, Layer.LANDING_COPYJOB, Layer.LANDING_COPYJOB_NORMALIZE):
            return "landing"
        return self.value


class ActivityConfig(BaseModel):
    timeout_hours: float = 12.0
    retries: int = 3
    retry_interval_seconds: int = 180


class PipelineActivity(BaseModel):
    layer: Layer
    entity: str
    name_override: str | None = None
    dependencies: list[str] = Field(default_factory=list)  # Activity names that must complete first
    config: ActivityConfig = Field(default_factory=ActivityConfig)
    metadata: JobMetadata
    parameters: dict[str, str] = Field(default_factory=dict)

    @property
    def name(self) -> str:
        if self.name_override:
            return self.name_override
        return f"{self.layer.value}_{self.entity}"


class InvokePipelineActivity(BaseModel):
    name: str
    pipeline_id: str
    dependencies: list[str] = Field(default_factory=list)
    config: ActivityConfig = Field(default_factory=ActivityConfig)
    wait_on_completion: bool = True


class IfConditionActivity(BaseModel):
    name: str
    expression: str
    dependencies: list[str] = Field(default_factory=list)
    if_true_activities: list[PipelineActivity | InvokePipelineActivity] = Field(default_factory=list)
    if_false_activities: list[PipelineActivity | InvokePipelineActivity] = Field(default_factory=list)


class PipelineDefinition(BaseModel):
    name: str
    activities: list[PipelineActivity | InvokePipelineActivity | IfConditionActivity] = Field(default_factory=list)  # Ordered with resolved dependencies
    upstream_subpipeline_keys: set[str] = Field(default_factory=set)  # Sub-pipeline keys this pipeline depends on (cross-group)
    deployed_id: str | None = None  # Set after deployment to Fabric


class DiscoveredJob(BaseModel):
    layer: Layer
    entity: str
    pipeline_group: str
    dependencies: list[str]  # Activity names from previous layers
    metadata: JobMetadata

    @property
    def activity_name(self) -> str:
        return f"{self.layer.value}_{self.entity}"
