# Fabric Pipeline Activity Limit — Sub-Pipeline Strategy

## Problem Statement

Our data pipeline deploys as a single Fabric Data Factory pipeline containing all transformation steps across the full medallion architecture (landing → bronze → silver → gold). The pipeline currently generates **136 activities** (1 setup + 135 discovered jobs), which exceeds Fabric's hard limit of **120 activities per pipeline** (although histircally it's even been as low as 80).

We need to restructure the pipeline into multiple sub-pipelines orchestrated by a parent pipeline using the **Invoke Pipeline** activity.

## Background

### Current Architecture

The pipeline is built by [`PipelineDiscoverer`](../src/tag_data_engineering/pipeline/pipeline_discoverer.py) which scans the [`transformations/`](../src/tag_data_engineering/transformations/) directory and creates a flat list of activities across all layers. The [`pipeline_deploy.py`](../scripts/pipeline_deploy.py) script then deploys this as a single Fabric pipeline.

**Current activity breakdown (136 total):**

| Layer | Count |
|---|---|
| setup | 1 |
| landing (notebook) | 3 |
| landing_copyjob | 28 |
| landing_copyjob_normalize | 28 |
| bronze | 31 |
| silver | 32 |
| gold | 13 |

**Activities by source system:**

| Source | Landing | Landing CopyJob | Landing Normalize | Bronze | Silver | Total |
|---|---|---|---|---|---|---|
| CMS | — | 20 | 20 | 20 | 21 | 81 |
| POPLA | — | 4 | 4 | 4 | 4 | 16 |
| Puzzel | — | 3 | 3 | 3 | 3 | 12 |
| Heritage | — | 1 | 1 | 1 | 1 | 4 |
| Entra | 1 | — | — | 1 | 1 | 3 |
| Verint | 1 | — | — | 1 | 1 | 3 |
| Starwars | 1 | — | — | 1 | 1 | 3 |
| **Gold** | — | — | — | — | — | **13** |

### Fabric Pipeline Limits

From the [official Fabric Data Factory limitations page](https://learn.microsoft.com/en-us/fabric/data-factory/data-factory-limitations):

- **Maximum activities per pipeline (including inner activities for containers): 120** (documented), but community reports confirm the [effective limit is 80](https://community.fabric.microsoft.com/t5/Data-Pipeline/How-to-change-the-limit-number-of-activities-in-a-Data-pipeline/m-p/4319634) and Microsoft Support has stated the increase to 120 is no longer available.
- Maximum parameters per pipeline: 50
- Concurrent pipeline runs per workspace: 10,000
- Total pipelines per workspace: 5,000
- Maximum timeout per activity run: 24 hours

### Invoke Pipeline Activity

Fabric supports the [**Invoke Pipeline** activity](https://learn.microsoft.com/en-us/fabric/data-factory/invoke-pipeline-activity) which can call child pipelines from a parent pipeline. Key details:

- There are two versions: **Invoke Pipeline (Legacy)** (same workspace only, no child monitoring) and the newer **Invoke Pipeline** (cross-workspace, child monitoring, supports ADF/Synapse).
- Supports **"Wait on completion"** — the parent pipeline blocks until the child finishes — or **fire-and-forget** where the child runs in parallel with subsequent activities in the parent.
- Each Invoke Pipeline activity requires a **Connection** object (stored in Fabric credentials) using organizational account, service principal, or workspace identity authentication.
- The 80-activity limit applies **per pipeline independently** — a parent pipeline with 5 Invoke Pipeline activities and a child pipeline with 70 activities are each within their own limits.

### Nesting Constraints (from [ADF nested activities docs](https://learn.microsoft.com/en-us/azure/data-factory/concepts-nested-activities))

- ForEach/Until support only single-level nesting of If/Switch.
- For deeper nesting, use Execute/Invoke Pipeline to call a child pipeline.
- No documented depth limit on Invoke Pipeline nesting itself — you can have pipelines invoking pipelines invoking pipelines.

### Dependency Structure

Within our pipeline, dependencies flow strictly downward through the medallion layers:

- **Landing** depends on `setup_metadata`
- **Bronze** depends on its corresponding landing entity
- **Silver** depends on its corresponding bronze entity (no cross-source dependencies)
- **Gold** depends on various silver entities (cross-source) and other gold entities

Gold is the only layer with cross-source dependencies (e.g., `dim_cases` depends on `silver_cms_complaints`, `silver_cms_decisions`, `silver_cms_appeals`, and other gold entities).

## Proposed Solutions

### Solution 1: Source-Based Sub-Pipelines + Gold Pipeline

Group landing → bronze → silver by source system into separate sub-pipelines, with gold in its own pipeline. An orchestrator parent pipeline invokes them all.

**Sub-pipelines:**

| Pipeline | Activities | Within Limit? |
|---|---|---|
| `orchestrator` (parent) | 1 setup + 8 invoke activities = 9 | ✅ |
| `source_cms` | 81 | ❌ Still over 80 |
| `source_popla` | 16 | ✅ |
| `source_puzzel` | 12 | ✅ |
| `source_heritage` | 4 | ✅ |
| `source_entra` | 3 | ✅ |
| `source_verint` | 3 | ✅ |
| `source_starwars` | 3 | ✅ |
| `gold` | 13 | ✅ |

**Problem:** CMS has 81 activities, which is already over the limit. CMS would need to be split further (e.g., CMS-A and CMS-B with ~40 each), or an alternative approach is needed.

**CMS split option:** Split CMS into two sub-pipelines. Since there are no cross-dependencies within silver CMS entities, the split can be arbitrary (e.g., alphabetical). Each half would have ~10 copyjob + 10 normalize + 10 bronze + ~10 silver ≈ 40 activities.

**Orchestrator flow:**

```
setup_metadata
    ├─► Invoke source_cms_a (wait) ──┐
    ├─► Invoke source_cms_b (wait) ──┤
    ├─► Invoke source_popla (wait) ──┤
    ├─► Invoke source_puzzel (wait) ─┤  (all run in parallel)
    ├─► Invoke source_heritage (wait)┤
    ├─► Invoke source_entra (wait) ──┤
    ├─► Invoke source_verint (wait) ─┤
    └─► Invoke source_starwars (wait)┘
                                     │
                                     ▼
                          Invoke gold (wait)
```

**Pros:**
- Logical grouping by data source — easy to understand and debug
- Each source pipeline is independently deployable and testable
- Source pipelines can be scheduled independently if needed
- Gold dependencies are satisfied because all source pipelines complete before gold starts

**Cons:**
- CMS needs an additional split, adding complexity
- 9–10 total pipelines to manage
- Requires creating Fabric Connection objects for Invoke Pipeline activities
- Deployment script needs significant refactoring to create and deploy multiple pipelines
- No parallelism within the orchestrator beyond the source-level (all sources run simultaneously, then gold)

---

### Solution 2: Layer-Based Sub-Pipelines

Split by layer rather than by source. Each medallion layer gets its own sub-pipeline.

**Sub-pipelines:**

| Pipeline | Activities | Within Limit? |
|---|---|---|
| `orchestrator` (parent) | 1 setup + 4 invoke activities = 5 | ✅ |
| `layer_landing` | 31 (3 notebook + 28 copyjob) | ✅ |
| `layer_landing_normalize` | 28 | ✅ |
| `layer_bronze` | 31 | ✅ |
| `layer_silver` | 32 | ✅ |
| `layer_gold` | 13 | ✅ |

**Orchestrator flow:**

```
setup_metadata
    │
    ▼
Invoke layer_landing (wait)
    │
    ▼
Invoke layer_landing_normalize (wait)
    │
    ▼
Invoke layer_bronze (wait)
    │
    ▼
Invoke layer_silver (wait)
    │
    ▼
Invoke layer_gold (wait)
```

**Pros:**
- Simple, clean split — every pipeline is well within the 80 limit
- No need to split CMS further
- Minimal changes to the existing code structure (layers already exist as concepts)
- Fewer pipelines to manage (6 total)

**Cons:**
- **Loses all parallelism** — currently the single pipeline resolves dependencies and runs many things in parallel (e.g., all independent copyjobs run simultaneously). With layer-based sub-pipelines, each layer must fully complete before the next starts, even though many entities within a layer are independent of each other.
- Within each sub-pipeline, activities would still run in parallel (since Fabric resolves dependencies within a pipeline), but cross-layer parallelism is lost (e.g., `bronze_cms_roles` could start as soon as `landing_copyjob_normalize_cms_roles` finishes, but would have to wait for *all* landing normalizations to complete)
- Slower overall execution time

---

### Solution 3: Layer-per-Source Sub-Pipelines (Recommended)

Split each layer into its own pipeline per source system. This gives fine-grained sub-pipelines where each pipeline handles exactly one layer for one source. The orchestrator chains them per-source (landing → bronze → silver) and runs all sources in parallel, with gold at the end.

**Pipeline group configuration (via metadata.json):**

Each landing entity's `metadata.json` gains a `pipeline_group` field that controls which sub-pipeline it belongs to. Bronze and silver entities inherit the group from their corresponding landing entity automatically (since they already reference it via dependencies).

```json
// transformations/landing/cms_appeals/metadata.json
{
    "extractor": "copy_job",
    "pipeline_group": "cms",
    ...
}
```

```json
// transformations/landing/popla_appellant_cases/metadata.json
{
    "extractor": "copy_job",
    "pipeline_group": "other",
    ...
}
```

To promote POPLA to its own pipeline, just change its landing metadata files:

```json
// transformations/landing/popla_appellant_cases/metadata.json
{
    "extractor": "copy_job",
    "pipeline_group": "popla",
    ...
}
```

The pipeline builder discovers all distinct `pipeline_group` values and generates the correct sub-pipelines and orchestrator wiring automatically — no code changes needed.

**Sub-pipelines (default grouping):**

| Pipeline | Contents | Activities |
|---|---|---|
| `orchestrator` | setup + invoke activities | 8 |
| `landing_cms` | CMS copyjob + normalize | 40 |
| `bronze_cms` | CMS bronze transforms | 20 |
| `silver_cms` | CMS silver transforms | 21 |
| `landing_other` | POPLA/Puzzel/Heritage copyjob + normalize + Entra/Verint/Starwars notebook landing | 19 |
| `bronze_other` | POPLA + Puzzel + Heritage + Entra + Verint + Starwars bronze | 11 |
| `silver_other` | POPLA + Puzzel + Heritage + Entra + Verint + Starwars silver | 11 |
| `gold` | All gold transforms | 13 |

All sub-pipelines are comfortably within the 80-activity limit (largest is `landing_cms` at 40).

**Orchestrator flow (8 activities: 1 setup + 7 invoke):**

```
setup_metadata
    ├─► Invoke landing_cms ─► Invoke bronze_cms ─► Invoke silver_cms ────┐
    └─► Invoke landing_other ─► Invoke bronze_other ─► Invoke silver_other ─┘
                                                                          │
                                                                          ▼
                                                               Invoke gold (wait)
```

Each source group chain runs in parallel. Within each chain, the layers are sequential (landing waits to complete before bronze starts, etc.). Within each sub-pipeline, Fabric resolves internal dependencies and runs independent activities in parallel (e.g., all 20 CMS copyjobs start simultaneously within `landing_cms`).

**Key implementation details:**

1. **Parallelism is preserved at two levels**: Sources run in parallel via the orchestrator, and within each sub-pipeline Fabric parallelises independent activities (e.g., all CMS copyjobs fire at once, each normalize starts as its copyjob finishes, etc.).

2. **Gold dependencies are naturally satisfied**: All source chains complete before gold is invoked. Gold entities reference silver tables in the lakehouse, so the data is available regardless of which sub-pipeline wrote it.

3. **No cross-dependencies within a source**: Each entity's bronze depends only on its own landing, and each silver depends only on its own bronze. No CMS silver entity depends on another CMS silver entity, so each sub-pipeline's internal dependency graph is clean.

4. **Configurable grouping via `metadata.json`**: Each landing entity declares its `pipeline_group`. Bronze and silver entities inherit the group from their corresponding landing entity (the link already exists via `BronzeMetadata.entity`). The pipeline builder discovers all distinct groups and generates sub-pipelines accordingly. Promoting a source to its own pipeline is just editing its metadata files.

5. **Code changes required**:
   - Add `pipeline_group` field to `ExtractionMetadata` (landing metadata model)
   - Extend `PipelineDiscoverer` to read `pipeline_group`, propagate it to bronze/silver jobs, and support building sub-pipelines grouped by it
   - Extend `fabric_serialization.py` to serialize Invoke Pipeline activities (with "wait on completion" and dependency chaining)
   - Update `pipeline_deploy.py` to deploy all sub-pipelines first, then build and deploy the orchestrator with references to the child pipeline IDs
   - Add new `PipelineDefinition` support for invoke-pipeline activities (not just notebook/copyjob)

**Pros:**
- Every pipeline is well within the 80-activity limit (max 40)
- Only 8 pipelines to manage (down from 14 in the per-source variant)
- Preserves parallelism: source groups run concurrently, activities within each sub-pipeline run concurrently
- Each sub-pipeline is independently deployable, testable, and re-runnable
- Clear naming convention (`{layer}_{group}`) makes monitoring and debugging straightforward
- Easy to promote a source to its own pipeline — just change `pipeline_group` in its metadata.json files, no code changes
- Scales well — new sources either join an existing group or get their own
- Gold can be re-run independently without re-running any source pipelines

**Cons:**
- 8 pipelines to manage (but deployment is automated)
- Requires Fabric Connection setup for Invoke Pipeline activities
- Minor loss of cross-source parallelism at layer boundaries (e.g., `bronze_cms_roles` could theoretically start the instant `landing_cms_roles` normalize finishes, without waiting for all of `landing_cms` — but this is already the case since `bronze_cms` waits for `landing_cms` to fully complete)
