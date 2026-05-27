import json
from pathlib import Path

import tag_data_engineering.transformations
from tag_data_engineering.pipeline.models import ActivityConfig
from tag_data_engineering.pipeline.models import IfConditionActivity
from tag_data_engineering.pipeline.pipeline_discoverer import PipelineDiscoverer


def create_landing_metadata(base_path: Path, entity: str, extractor: str = "rest_api", pipeline_group: str = "", dependencies: list[str] | None = None):
    """Create minimal landing metadata.json"""
    path = base_path / "landing" / entity
    path.mkdir(parents=True, exist_ok=True)
    metadata = {
        "entity": entity,
        "pipeline_group": pipeline_group,
        "extractor": extractor,
        "extraction_mode": "full_refresh",
        "max_file_size_mb": 10,
        "output_format": "jsonl",
    }
    if dependencies:
        metadata["dependencies"] = dependencies
    if extractor == "rest_api":
        metadata["rest_api"] = {
            "base_url": "http://test.com",
            "endpoint": f"/{entity}/",
        }
    elif extractor == "copy_job":
        metadata["copy_job"] = {
            "source_connection": "TestConnection",
            "source_connection_type": "MySql",
            "source_type": "MySqlSource",
            "source_table": entity,
        }

    (path / "metadata.json").write_text(json.dumps(metadata, indent=2))


def create_bronze_metadata(base_path: Path, table: str, entity: str, pipeline_group: str = ""):
    """Create minimal bronze metadata.json"""
    path = base_path / "bronze" / table
    path.mkdir(parents=True, exist_ok=True)
    metadata = {
        "schema": "bronze",
        "pipeline_group": pipeline_group,
        "table": table,
        "entity": entity,
        "merge_key": "id",
        "source_format": "jsonl",
        "dependencies": [],
    }
    (path / "metadata.json").write_text(json.dumps(metadata, indent=2))


def create_silver_metadata(base_path: Path, table: str, deps: list[str], pipeline_group: str = ""):
    """Create minimal silver metadata.json"""
    path = base_path / "silver" / table
    path.mkdir(parents=True, exist_ok=True)
    metadata = {
        "schema": "silver",
        "pipeline_group": pipeline_group,
        "table": table,
        "merge_key": "id",
        "dependencies": deps,
    }
    (path / "metadata.json").write_text(json.dumps(metadata, indent=2))


def create_gold_metadata(base_path: Path, table: str, deps: list[str], pipeline_group: str = ""):
    """Create minimal gold metadata.json"""
    path = base_path / "gold" / table
    path.mkdir(parents=True, exist_ok=True)
    metadata = {
        "schema": "gold",
        "pipeline_group": pipeline_group,
        "table": table,
        "merge_key": "id",
        "dependencies": deps,
    }
    (path / "metadata.json").write_text(json.dumps(metadata, indent=2))


def test_discover_and_build_simple_landing(tmp_path):
    create_landing_metadata(tmp_path, "films", extractor="rest_api")
    discoverer = PipelineDiscoverer(tmp_path)
    pipeline = discoverer.build_pipeline("test", add_setup=True)
    assert len(pipeline.activities) == 2
    assert pipeline.activities[0].name == "setup_metadata"
    assert pipeline.activities[1].name == "landing_films"
    assert pipeline.activities[1].dependencies == ["setup_metadata"]


def test_discover_and_build_copyjob_landing(tmp_path):
    create_landing_metadata(tmp_path, "users", extractor="copy_job")
    pipeline = PipelineDiscoverer(tmp_path).build_pipeline("test", add_setup=True)
    assert len(pipeline.activities) == 3
    activity_names = [a.name for a in pipeline.activities]
    assert "setup_metadata" in activity_names
    assert "landing_copyjob_users" in activity_names
    assert "landing_copyjob_normalize_users" in activity_names
    activities_by_name = {a.name: a for a in pipeline.activities}
    assert activities_by_name["landing_copyjob_users"].dependencies == ["setup_metadata"]
    assert activities_by_name["landing_copyjob_normalize_users"].dependencies == ["landing_copyjob_users"]


def test_discover_and_build_full_medallion(tmp_path):
    create_landing_metadata(tmp_path, "films", extractor="rest_api")
    create_bronze_metadata(tmp_path, "films", entity="films")
    create_silver_metadata(tmp_path, "films", deps=["bronze.films"])
    create_gold_metadata(tmp_path, "dim_films", deps=["silver.films"])
    pipeline = PipelineDiscoverer(tmp_path).build_pipeline("test", add_setup=True)
    activities_by_name = {a.name: a for a in pipeline.activities}
    assert activities_by_name["landing_films"].dependencies == ["setup_metadata"]
    assert activities_by_name["bronze_films"].dependencies == ["landing_films"]
    assert activities_by_name["silver_films"].dependencies == ["bronze_films"]
    assert activities_by_name["gold_dim_films"].dependencies == ["silver_films"]


def test_discover_and_build_cross_dependencies(tmp_path):
    create_landing_metadata(tmp_path, "films", extractor="rest_api")
    create_landing_metadata(tmp_path, "people", extractor="rest_api")
    create_bronze_metadata(tmp_path, "films", entity="films")
    create_bronze_metadata(tmp_path, "people", entity="people")
    create_silver_metadata(tmp_path, "films_people", deps=["bronze.films", "bronze.people"])
    pipeline = PipelineDiscoverer(tmp_path).build_pipeline("test", add_setup=True)
    activities_by_name = {a.name: a for a in pipeline.activities}
    assert set(activities_by_name["silver_films_people"].dependencies) == {
        "bronze_films",
        "bronze_people",
    }


def test_activity_count_by_layer(tmp_path):
    create_landing_metadata(tmp_path, "films", extractor="rest_api")
    create_landing_metadata(tmp_path, "people", extractor="rest_api")
    create_bronze_metadata(tmp_path, "films", entity="films")
    create_bronze_metadata(tmp_path, "people", entity="people")
    create_silver_metadata(tmp_path, "combined", deps=["bronze.films", "bronze.people"])
    pipeline = PipelineDiscoverer(tmp_path).build_pipeline("test", add_setup=True)
    counts: dict[str, int] = {}
    for activity in pipeline.activities:
        layer_name = activity.layer.value
        counts[layer_name] = counts.get(layer_name, 0) + 1
    assert counts["setup"] == 1
    assert counts["landing"] == 2
    assert counts["bronze"] == 2
    assert counts["silver"] == 1


def test_mixed_landing_extractors(tmp_path):
    create_landing_metadata(tmp_path, "films", extractor="rest_api")
    create_landing_metadata(tmp_path, "users", extractor="copy_job")
    create_bronze_metadata(tmp_path, "films", entity="films")
    create_bronze_metadata(tmp_path, "users", entity="users")
    pipeline = PipelineDiscoverer(tmp_path).build_pipeline("test", add_setup=True)
    activities_by_name = {a.name: a for a in pipeline.activities}
    assert activities_by_name["bronze_films"].dependencies == ["landing_films"]
    assert activities_by_name["bronze_users"].dependencies == ["landing_copyjob_normalize_users"]


def test_custom_blob_landing_uses_single_landing_activity(tmp_path):
    create_landing_metadata(tmp_path, "myhr_hierarchy_history", extractor="blob")
    create_bronze_metadata(tmp_path, "myhr_hierarchy_history", entity="myhr_hierarchy_history")

    pipeline = PipelineDiscoverer(tmp_path).build_pipeline("test", add_setup=True)

    activities_by_name = {a.name: a for a in pipeline.activities}
    assert "landing_myhr_hierarchy_history" in activities_by_name
    assert "landing_copyjob_myhr_hierarchy_history" not in activities_by_name
    assert "landing_copyjob_normalize_myhr_hierarchy_history" not in activities_by_name
    assert activities_by_name["bronze_myhr_hierarchy_history"].dependencies == ["landing_myhr_hierarchy_history"]


def test_finance_blob_landing_uses_single_landing_activity(tmp_path):
    create_landing_metadata(tmp_path, "finance_monthly_budgets", extractor="blob")
    create_bronze_metadata(tmp_path, "finance_monthly_budgets", entity="finance_monthly_budgets")

    pipeline = PipelineDiscoverer(tmp_path).build_pipeline("test", add_setup=True)

    activities_by_name = {a.name: a for a in pipeline.activities}
    assert "landing_finance_monthly_budgets" in activities_by_name
    assert "landing_copyjob_finance_monthly_budgets" not in activities_by_name
    assert "landing_copyjob_normalize_finance_monthly_budgets" not in activities_by_name
    assert activities_by_name["bronze_finance_monthly_budgets"].dependencies == ["landing_finance_monthly_budgets"]


def test_mysql_extractor_landing_uses_single_landing_activity(tmp_path):
    create_landing_metadata(tmp_path, "popla_case_audits", extractor="mysql")
    create_bronze_metadata(tmp_path, "popla_case_audits", entity="popla_case_audits")

    pipeline = PipelineDiscoverer(tmp_path).build_pipeline("test", add_setup=True)

    activities_by_name = {a.name: a for a in pipeline.activities}
    assert "landing_popla_case_audits" in activities_by_name
    assert "landing_copyjob_popla_case_audits" not in activities_by_name
    assert "landing_copyjob_normalize_popla_case_audits" not in activities_by_name
    assert activities_by_name["bronze_popla_case_audits"].dependencies == ["landing_popla_case_audits"]


def test_sql_server_extractor_landing_uses_single_landing_activity(tmp_path):
    create_landing_metadata(tmp_path, "puzzel_agents", extractor="sql_server")
    create_bronze_metadata(tmp_path, "puzzel_agents", entity="puzzel_agents")

    pipeline = PipelineDiscoverer(tmp_path).build_pipeline("test", add_setup=True)

    activities_by_name = {a.name: a for a in pipeline.activities}
    assert "landing_puzzel_agents" in activities_by_name
    assert "landing_copyjob_puzzel_agents" not in activities_by_name
    assert "landing_copyjob_normalize_puzzel_agents" not in activities_by_name
    assert activities_by_name["bronze_puzzel_agents"].dependencies == ["landing_puzzel_agents"]


def test_builder_with_custom_config(tmp_path):
    create_landing_metadata(tmp_path, "films", extractor="rest_api")
    config = ActivityConfig(timeout_hours=6.0, retries=3, retry_interval_seconds=60)
    pipeline = PipelineDiscoverer(tmp_path).build_pipeline("test", add_setup=True, activity_config=config)
    for activity in pipeline.activities:
        assert activity.config.timeout_hours == 6.0
        assert activity.config.retries == 3
        assert activity.config.retry_interval_seconds == 60


def test_empty_transformations_folder(tmp_path):
    discoverer = PipelineDiscoverer(tmp_path)
    jobs = discoverer.discover_all()
    assert jobs == []
    pipeline = discoverer.build_pipeline("test", add_setup=True)
    assert len(pipeline.activities) == 1
    assert pipeline.activities[0].name == "setup_metadata"


def test_discover_skips_underscore_directories(tmp_path):
    create_landing_metadata(tmp_path, "films", extractor="rest_api")
    hidden_path = tmp_path / "landing" / "_hidden"
    hidden_path.mkdir(parents=True)
    (hidden_path / "metadata.json").write_text(json.dumps({"entity": "hidden"}))
    jobs = PipelineDiscoverer(tmp_path).discover_all()
    entities = [job.entity for job in jobs]
    assert "films" in entities
    assert "hidden" not in entities


def test_discover_skips_directories_without_metadata(tmp_path):
    (tmp_path / "bronze" / "no_metadata").mkdir(parents=True)
    create_bronze_metadata(tmp_path, "has_metadata", entity="test")
    jobs = PipelineDiscoverer(tmp_path).discover_all()
    entities = [job.entity for job in jobs]
    assert "has_metadata" in entities
    assert "no_metadata" not in entities


def test_build_subpipelines_groups_by_pipeline_group(tmp_path):
    create_landing_metadata(tmp_path, "films", pipeline_group="alpha")
    create_bronze_metadata(tmp_path, "films", entity="films", pipeline_group="alpha")
    create_silver_metadata(tmp_path, "films", deps=["bronze.films"], pipeline_group="alpha")

    create_landing_metadata(tmp_path, "people", pipeline_group="beta")
    create_bronze_metadata(tmp_path, "people", entity="people", pipeline_group="beta")
    create_silver_metadata(tmp_path, "people", deps=["bronze.people"], pipeline_group="beta")

    subs = PipelineDiscoverer(tmp_path).build_subpipelines("test")
    assert set(subs.keys()) == {
        "landing_alpha",
        "bronze_alpha",
        "silver_alpha",
        "landing_beta",
        "bronze_beta",
        "silver_beta",
    }
    for key, pipeline in subs.items():
        for activity in pipeline.activities:
            layer_group = activity.layer.layer_group
            group_suffix = key.split("_", 1)[1]
            assert f"{layer_group}_{group_suffix}" == key


def test_build_subpipelines_strips_cross_pipeline_dependencies(tmp_path):
    create_landing_metadata(tmp_path, "users", extractor="copy_job", pipeline_group="alpha")
    create_bronze_metadata(tmp_path, "users", entity="users", pipeline_group="alpha")

    subs = PipelineDiscoverer(tmp_path).build_subpipelines("test")
    bronze_pipeline = subs["bronze_alpha"]
    bronze_activity = bronze_pipeline.activities[0]
    assert bronze_activity.name == "bronze_users"
    assert bronze_activity.dependencies == []


def test_build_subpipelines_preserves_within_pipeline_dependencies(tmp_path):
    create_landing_metadata(tmp_path, "users", extractor="copy_job", pipeline_group="alpha")

    subs = PipelineDiscoverer(tmp_path).build_subpipelines("test")
    landing_pipeline = subs["landing_alpha"]
    activities_by_name = {a.name: a for a in landing_pipeline.activities}
    assert "landing_copyjob_users" in activities_by_name
    assert "landing_copyjob_normalize_users" in activities_by_name
    assert activities_by_name["landing_copyjob_normalize_users"].dependencies == ["landing_copyjob_users"]


def test_build_orchestrator_wiring(tmp_path):
    create_landing_metadata(tmp_path, "films", pipeline_group="alpha")
    create_bronze_metadata(tmp_path, "films", entity="films", pipeline_group="alpha")
    create_silver_metadata(tmp_path, "films", deps=["bronze.films"], pipeline_group="alpha")

    create_landing_metadata(tmp_path, "people", pipeline_group="beta")
    create_bronze_metadata(tmp_path, "people", entity="people", pipeline_group="beta")
    create_silver_metadata(tmp_path, "people", deps=["bronze.people"], pipeline_group="beta")

    create_gold_metadata(tmp_path, "dim_films", deps=["silver.films"], pipeline_group="all")

    discoverer = PipelineDiscoverer(tmp_path)
    subs = discoverer.build_subpipelines("test")
    for key, sub in subs.items():
        sub.deployed_id = f"id-{key}"

    orch = discoverer.build_orchestrator("orch", subs)
    names = [a.name for a in orch.activities]

    assert names[0] == "setup_metadata"
    assert "if_group_due_alpha" in names
    assert "if_group_due_beta" in names
    assert "if_gold_due" in names
    assert "lab_all" in names

    by_name = {a.name: a for a in orch.activities}
    assert by_name["if_group_due_alpha"].dependencies == ["setup_metadata"]
    assert by_name["if_group_due_beta"].dependencies == ["setup_metadata"]
    assert by_name["if_gold_due"].dependencies == ["if_group_due_alpha", "if_group_due_beta"]
    assert by_name["lab_all"].dependencies == ["if_gold_due"]

    alpha_gate = by_name["if_group_due_alpha"]
    assert isinstance(alpha_gate, IfConditionActivity)
    alpha_children = {a.name: a for a in alpha_gate.if_true_activities}
    assert alpha_children["invoke_landing_alpha"].dependencies == []
    assert alpha_children["invoke_bronze_alpha"].dependencies == ["invoke_landing_alpha"]
    assert alpha_children["invoke_silver_alpha"].dependencies == ["invoke_bronze_alpha"]
    assert alpha_children["setup_pipeline_group_success_alpha"].dependencies == ["invoke_silver_alpha"]
    assert alpha_children["setup_pipeline_group_success_alpha"].parameters["pipeline_group"] == "alpha"


def test_build_subpipelines_gold_group(tmp_path):
    create_landing_metadata(tmp_path, "films", pipeline_group="alpha")
    create_bronze_metadata(tmp_path, "films", entity="films", pipeline_group="alpha")
    create_silver_metadata(tmp_path, "films", deps=["bronze.films"], pipeline_group="alpha")
    create_gold_metadata(tmp_path, "dim_films", deps=["silver.films"], pipeline_group="all")

    subs = PipelineDiscoverer(tmp_path).build_subpipelines("test")
    assert "gold_all" in subs
    gold_activities = subs["gold_all"].activities
    assert len(gold_activities) == 1
    assert gold_activities[0].name == "gold_dim_films"


def test_build_orchestrator_invokes_all_gold_subpipelines(tmp_path):
    create_landing_metadata(tmp_path, "films", pipeline_group="alpha")
    create_bronze_metadata(tmp_path, "films", entity="films", pipeline_group="alpha")
    create_silver_metadata(tmp_path, "films", deps=["bronze.films"], pipeline_group="alpha")
    create_gold_metadata(tmp_path, "dim_films", deps=["silver.films"], pipeline_group="all")
    create_gold_metadata(tmp_path, "dim_other_films", deps=["silver.films"], pipeline_group="other_gold")

    discoverer = PipelineDiscoverer(tmp_path)
    subs = discoverer.build_subpipelines("test")
    for key, sub in subs.items():
        sub.deployed_id = f"id-{key}"

    orch = discoverer.build_orchestrator("orch", subs)
    gold_all_gate = next(a for a in orch.activities if a.name == "if_gold_due")
    gold_other_gate = next(a for a in orch.activities if a.name == "if_gold_other_gold_due")
    assert isinstance(gold_all_gate, IfConditionActivity)
    assert isinstance(gold_other_gate, IfConditionActivity)
    assert [a.name for a in gold_all_gate.if_true_activities] == ["invoke_gold"]
    assert [a.name for a in gold_other_gate.if_true_activities] == ["invoke_gold_other_gold"]
    assert set(next(a for a in orch.activities if a.name == "lab_all").dependencies) == {"if_gold_due", "if_gold_other_gold_due"}


def test_build_subpipelines_activity_counts(tmp_path):
    create_landing_metadata(tmp_path, "films", extractor="rest_api", pipeline_group="a")
    create_landing_metadata(tmp_path, "people", extractor="rest_api", pipeline_group="a")
    create_bronze_metadata(tmp_path, "films", entity="films", pipeline_group="a")
    create_bronze_metadata(tmp_path, "people", entity="people", pipeline_group="a")

    create_landing_metadata(tmp_path, "users", extractor="copy_job", pipeline_group="b")
    create_bronze_metadata(tmp_path, "users", entity="users", pipeline_group="b")

    subs = PipelineDiscoverer(tmp_path).build_subpipelines("test")
    assert len(subs["landing_a"].activities) == 2
    assert len(subs["bronze_a"].activities) == 2
    assert len(subs["landing_b"].activities) == 2  # copyjob + normalize
    assert len(subs["bronze_b"].activities) == 1


def test_build_subpipelines_returns_cross_group_dependencies(tmp_path):
    """landing_verint depends on silver.entra_users → landing_verint should depend on silver_other."""
    create_landing_metadata(tmp_path, "entra_users", pipeline_group="other")
    create_bronze_metadata(tmp_path, "entra_users", entity="entra_users", pipeline_group="other")
    create_silver_metadata(tmp_path, "entra_users", deps=["bronze.entra_users"], pipeline_group="other")

    create_landing_metadata(tmp_path, "verint_adherence", pipeline_group="verint", dependencies=["silver.entra_users"])
    create_bronze_metadata(tmp_path, "verint_adherence", entity="verint_adherence", pipeline_group="verint")

    subs = PipelineDiscoverer(tmp_path).build_subpipelines("test")

    assert "silver_other" in subs["landing_verint"].upstream_subpipeline_keys


def test_build_orchestrator_wires_cross_group_dependencies(tmp_path):
    """Orchestrator should make invoke_landing_verint depend on invoke_silver_other."""
    create_landing_metadata(tmp_path, "entra_users", pipeline_group="other")
    create_bronze_metadata(tmp_path, "entra_users", entity="entra_users", pipeline_group="other")
    create_silver_metadata(tmp_path, "entra_users", deps=["bronze.entra_users"], pipeline_group="other")

    create_landing_metadata(tmp_path, "verint_adherence", pipeline_group="verint", dependencies=["silver.entra_users"])
    create_bronze_metadata(tmp_path, "verint_adherence", entity="verint_adherence", pipeline_group="verint")

    discoverer = PipelineDiscoverer(tmp_path)
    subs = discoverer.build_subpipelines("test")
    for key, sub in subs.items():
        sub.deployed_id = f"id-{key}"

    orch = discoverer.build_orchestrator("orch", subs)
    by_name = {a.name: a for a in orch.activities}

    # landing_verint should wait for the other group gate because it depends on silver_other
    assert "setup_metadata" in by_name["if_group_due_verint"].dependencies
    assert "if_group_due_other" in by_name["if_group_due_verint"].dependencies

    # landing_other should NOT have cross-group deps (no external dependencies)
    assert by_name["if_group_due_other"].dependencies == ["setup_metadata"]

    # lab should run once after the latest available top layer (gold if present, otherwise silver)
    assert by_name["lab_all"].dependencies == ["if_group_due_other", "if_group_due_verint"]


def test_repo_finance_entities_use_single_blob_landing_activity():
    repo_transformations = Path(tag_data_engineering.transformations.__file__).parent
    pipeline = PipelineDiscoverer(repo_transformations).build_pipeline("repo", add_setup=True)
    activities_by_name = {activity.name: activity for activity in pipeline.activities}

    finance_entities = [
        "finance_monthly_budgets",
        "finance_monthly_forecasts",
        "finance_weekly_budgets",
        "finance_weekly_forecasts",
    ]

    for entity in finance_entities:
        assert f"landing_{entity}" in activities_by_name
        assert f"landing_copyjob_{entity}" not in activities_by_name
        assert f"landing_copyjob_normalize_{entity}" not in activities_by_name
        assert activities_by_name[f"bronze_{entity}"].dependencies == [f"landing_{entity}"]


def test_repo_blob_entities_are_assigned_to_weekly_blob_group():
    repo_transformations = Path(tag_data_engineering.transformations.__file__).parent
    jobs = PipelineDiscoverer(repo_transformations).discover_all()
    landing_blob_jobs = [job for job in jobs if job.layer.value == "landing" and getattr(job.metadata, "extractor", None) == "blob"]

    assert landing_blob_jobs
    assert {job.pipeline_group for job in landing_blob_jobs} == {"weekly_blob"}
