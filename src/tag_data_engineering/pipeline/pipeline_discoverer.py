import json
from importlib.resources import files
from pathlib import Path

import tag_data_engineering.transformations
from tag_data_engineering.models import BronzeMetadata
from tag_data_engineering.models import ExtractionMetadata
from tag_data_engineering.models import SetupMetadata
from tag_data_engineering.models import TransformationMetadata
from tag_data_engineering.pipeline.models import ActivityConfig
from tag_data_engineering.pipeline.models import DiscoveredJob
from tag_data_engineering.pipeline.models import IfConditionActivity
from tag_data_engineering.pipeline.models import InvokePipelineActivity
from tag_data_engineering.pipeline.models import Layer
from tag_data_engineering.pipeline.models import PipelineActivity
from tag_data_engineering.pipeline.models import PipelineDefinition


def _parse_dependencies_from_json(metadata_file: Path) -> list[str]:
    data = json.loads(metadata_file.read_text())
    deps = data.get("dependencies", [])
    parsed = []
    for dep in deps:
        if "." in dep:
            schema, table = dep.split(".", 1)
            parsed.append(f"{schema}_{table}")
        else:
            parsed.append(dep)
    return parsed


def _due_group_expression(groups: list[str]) -> str:
    if not groups:
        return "@greater(length(json(activity('setup_metadata').output.result.exitValue).due_groups), 0)"
    expressions = [f"contains(json(activity('setup_metadata').output.result.exitValue).due_groups, '{group}')" for group in sorted(groups)]
    condition = expressions[0]
    for expression in expressions[1:]:
        condition = f"or({condition}, {expression})"
    return f"@{condition}"


class PipelineDiscoverer:
    def __init__(self, transformations_path: Path | None = None):
        self._base_path = Path(str(files(tag_data_engineering.transformations))) if transformations_path is None else transformations_path

    def discover_all(self) -> list[DiscoveredJob]:
        jobs: list[DiscoveredJob] = []
        for layer in [Layer.LANDING, Layer.BRONZE, Layer.SILVER, Layer.GOLD]:
            jobs.extend(self.discover_layer(layer))
        return jobs

    def build_pipeline(
        self,
        name: str,
        add_setup: bool = True,
        activity_config: ActivityConfig | None = None,
    ) -> PipelineDefinition:
        jobs = self.discover_all()
        config = activity_config or ActivityConfig()
        activities: list[PipelineActivity] = []
        if add_setup:
            activities.append(
                PipelineActivity(
                    layer=Layer.SETUP,
                    entity="metadata",
                    config=config,
                    metadata=SetupMetadata(),
                )
            )
        layer_order = [
            Layer.LANDING,
            Layer.LANDING_COPYJOB,
            Layer.LANDING_COPYJOB_NORMALIZE,
            Layer.BRONZE,
            Layer.SILVER,
            Layer.GOLD,
        ]
        for layer in layer_order:
            layer_jobs = [job for job in jobs if job.layer == layer]
            for job in layer_jobs:
                activities.append(
                    PipelineActivity(
                        layer=job.layer,
                        entity=job.entity,
                        dependencies=job.dependencies,
                        config=config,
                        metadata=job.metadata,
                    )
                )
        return PipelineDefinition(name=name, activities=activities)

    def discover_layer(self, layer: Layer) -> list[DiscoveredJob]:
        if layer == Layer.SETUP:
            # Setup is not discovered from files, it's added explicitly
            return []
        layer_path = self._base_path / layer.value
        if not layer_path.exists():
            return []
        jobs: list[DiscoveredJob] = []
        for entity_path in sorted(layer_path.iterdir()):
            if not entity_path.is_dir() or entity_path.name.startswith("_"):
                continue
            metadata_file = entity_path / "metadata.json"
            if not metadata_file.exists():
                continue
            jobs.extend(self._load_job(layer, entity_path.name, metadata_file))
        return jobs

    def _load_job(self, layer: Layer, entity: str, metadata_file: Path) -> list[DiscoveredJob]:
        if layer == Layer.LANDING:
            return self._load_landing_job(entity, metadata_file)
        if layer == Layer.BRONZE:
            job = self._load_bronze_job(entity, metadata_file)
            return [job] if job else []
        if layer in (Layer.SILVER, Layer.GOLD):
            job = self._load_transformation_job(layer, entity, metadata_file)
            return [job] if job else []
        return []

    def _load_landing_job(self, entity: str, metadata_file: Path) -> list[DiscoveredJob]:
        metadata = ExtractionMetadata.from_json_file(metadata_file)
        extra_dependencies = _parse_dependencies_from_json(metadata_file)
        if "setup_metadata" not in extra_dependencies:
            extra_dependencies.insert(0, "setup_metadata")
        if metadata.extractor == "copy_job":
            # Two jobs for Copy Job: InvokeCopyJob + normalize notebook
            return [
                DiscoveredJob(
                    layer=Layer.LANDING_COPYJOB,
                    entity=entity,
                    pipeline_group=metadata.pipeline_group,
                    dependencies=extra_dependencies,  # Depends on setup + metadata deps
                    metadata=metadata,
                ),
                DiscoveredJob(
                    layer=Layer.LANDING_COPYJOB_NORMALIZE,
                    entity=entity,
                    pipeline_group=metadata.pipeline_group,
                    dependencies=[f"landing_copyjob_{entity}"],  # Depends on copy job
                    metadata=metadata,
                ),
            ]
        else:
            # Single notebook job for internal extractors (REST API, etc.)
            return [
                DiscoveredJob(
                    layer=Layer.LANDING,
                    entity=entity,
                    pipeline_group=metadata.pipeline_group,
                    dependencies=extra_dependencies,  # Depends on setup + metadata deps
                    metadata=metadata,
                )
            ]

    def _load_bronze_job(self, entity: str, metadata_file: Path) -> DiscoveredJob:
        metadata = BronzeMetadata.from_json_file(metadata_file)
        landing_entity = metadata.entity
        landing_metadata_file = self._base_path / "landing" / landing_entity / "metadata.json"
        if landing_metadata_file.exists():
            landing_metadata = ExtractionMetadata.from_json_file(landing_metadata_file)
            if landing_metadata.extractor == "copy_job":
                dependencies = [f"landing_copyjob_normalize_{landing_entity}"]
            else:
                dependencies = [f"landing_{landing_entity}"]
        else:
            dependencies = [f"landing_{landing_entity}"] if landing_entity else []
        return DiscoveredJob(
            layer=Layer.BRONZE,
            entity=entity,
            pipeline_group=metadata.pipeline_group,
            dependencies=dependencies,
            metadata=metadata,
        )

    def build_subpipelines(
        self,
        base_name: str,
        activity_config: ActivityConfig | None = None,
    ) -> dict[str, PipelineDefinition]:
        jobs = self.discover_all()
        config = activity_config or ActivityConfig()

        buckets: dict[str, list[DiscoveredJob]] = {}
        for job in jobs:
            layer_group = job.layer.layer_group
            group = job.pipeline_group
            key = f"{layer_group}_{group}"
            buckets.setdefault(key, []).append(job)

        # Map each activity name to its bucket key for cross-group dependency resolution
        activity_to_bucket: dict[str, str] = {}
        for key, bucket_jobs in buckets.items():
            for job in bucket_jobs:
                activity_to_bucket[job.activity_name] = key

        subpipelines: dict[str, PipelineDefinition] = {}
        for key, bucket_jobs in sorted(buckets.items()):
            pipeline_name = f"{base_name}_{key}"
            activity_names_in_pipeline = {j.activity_name for j in bucket_jobs}

            # Collect cross-group dependencies for this sub-pipeline
            upstream_keys: set[str] = set()
            for job in bucket_jobs:
                for dep in job.dependencies:
                    if dep in activity_to_bucket and activity_to_bucket[dep] != key:
                        upstream_keys.add(activity_to_bucket[dep])

            layer_order = [
                Layer.LANDING,
                Layer.LANDING_COPYJOB,
                Layer.LANDING_COPYJOB_NORMALIZE,
                Layer.BRONZE,
                Layer.SILVER,
                Layer.GOLD,
            ]
            activities: list[PipelineActivity] = []
            for layer in layer_order:
                layer_jobs = [j for j in bucket_jobs if j.layer == layer]
                for job in layer_jobs:
                    filtered_deps = [d for d in job.dependencies if d in activity_names_in_pipeline]
                    activities.append(
                        PipelineActivity(
                            layer=job.layer,
                            entity=job.entity,
                            dependencies=filtered_deps,
                            config=config,
                            metadata=job.metadata,
                        )
                    )
            subpipelines[key] = PipelineDefinition(
                name=pipeline_name,
                activities=activities,
                upstream_subpipeline_keys=upstream_keys,
            )

        return subpipelines

    def build_orchestrator(
        self,
        name: str,
        subpipelines: dict[str, PipelineDefinition],
        activity_config: ActivityConfig | None = None,
    ) -> PipelineDefinition:
        config = activity_config or ActivityConfig()
        activities: list[PipelineActivity | InvokePipelineActivity] = []

        activities.append(
            PipelineActivity(
                layer=Layer.SETUP,
                entity="metadata",
                config=config,
                metadata=SetupMetadata(),
            )
        )

        groups = sorted({key.split("_", 1)[1] for key in subpipelines if not key.startswith("gold")})
        group_condition_names: list[str] = []

        for group in groups:
            landing_key = f"landing_{group}"
            bronze_key = f"bronze_{group}"
            silver_key = f"silver_{group}"

            same_group_keys = {landing_key, bronze_key, silver_key}
            true_activities: list[PipelineActivity | InvokePipelineActivity] = []
            prev_dep = ""
            condition_dependencies = ["setup_metadata"]
            for key in [landing_key, bronze_key, silver_key]:
                if key not in subpipelines:
                    continue
                sub = subpipelines[key]
                activity_name = f"invoke_{key}"
                for dep_key in sorted(sub.upstream_subpipeline_keys):
                    if dep_key in subpipelines and dep_key not in same_group_keys:
                        upstream_group = dep_key.split("_", 1)[1]
                        upstream_condition = f"if_group_due_{upstream_group}"
                        if upstream_condition not in condition_dependencies:
                            condition_dependencies.append(upstream_condition)
                deps = [prev_dep] if prev_dep else []
                true_activities.append(
                    InvokePipelineActivity(
                        name=activity_name,
                        pipeline_id=sub.deployed_id or "",
                        dependencies=deps,
                        config=config,
                    )
                )
                prev_dep = activity_name
            if not true_activities:
                continue

            success_dependencies = [prev_dep] if prev_dep else []
            true_activities.append(
                PipelineActivity(
                    layer=Layer.SETUP,
                    entity="pipeline_group_success",
                    name_override=f"setup_pipeline_group_success_{group}",
                    dependencies=success_dependencies,
                    config=config,
                    metadata=SetupMetadata(),
                    parameters={
                        "pipeline_group": group,
                        "orchestrator_run_id": "@json(activity('setup_metadata').output.result.exitValue).orchestrator_run_id",
                    },
                )
            )
            condition_name = f"if_group_due_{group}"
            activities.append(
                IfConditionActivity(
                    name=condition_name,
                    expression=_due_group_expression([group]),
                    dependencies=condition_dependencies,
                    if_true_activities=true_activities,
                )
            )
            group_condition_names.append(condition_name)

        gold_keys = sorted(key for key in subpipelines if key.startswith("gold_"))
        gold_condition_names: list[str] = []
        for key in gold_keys:
            sub = subpipelines[key]
            upstream_groups = sorted({dep_key.split("_", 1)[1] for dep_key in sub.upstream_subpipeline_keys if not dep_key.startswith("gold_")})
            condition_name = "if_gold_due" if key == "gold_all" else f"if_{key}_due"
            activities.append(
                IfConditionActivity(
                    name=condition_name,
                    expression=_due_group_expression(upstream_groups),
                    dependencies=group_condition_names or ["setup_metadata"],
                    if_true_activities=[
                        InvokePipelineActivity(
                            name="invoke_gold" if key == "gold_all" else f"invoke_{key}",
                            pipeline_id=subpipelines[key].deployed_id or "",
                            config=config,
                        )
                    ],
                )
            )
            gold_condition_names.append(condition_name)

        if gold_condition_names:
            lab_dependencies = gold_condition_names
        else:
            lab_dependencies = group_condition_names or ["setup_metadata"]

        activities.append(
            PipelineActivity(
                layer=Layer.LAB,
                entity="all",
                dependencies=lab_dependencies,
                config=config,
                metadata=SetupMetadata(),
            )
        )

        return PipelineDefinition(name=name, activities=activities)

    def _load_transformation_job(self, layer: Layer, entity: str, metadata_file: Path) -> DiscoveredJob:
        metadata = TransformationMetadata.from_json_file(metadata_file)
        # Load SQL from data.sql file and attach to metadata
        sql_file = metadata_file.parent / "data.sql"
        if sql_file.exists():
            metadata.sql = sql_file.read_text()
        dependencies = _parse_dependencies_from_json(metadata_file)
        return DiscoveredJob(
            layer=layer,
            entity=entity,
            pipeline_group=metadata.pipeline_group,
            dependencies=dependencies,
            metadata=metadata,
        )
