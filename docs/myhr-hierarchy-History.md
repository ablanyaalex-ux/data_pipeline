## MyHR Hierarchy History

`myhr_hierarchy_history` is a separate entity from `myhr_hierarchy`.

It uses a custom landing extractor instead of `copy_job`, and landing output is written directly as `jsonl`.

### Current flow

1. The landing metadata is defined in [`src/tag_data_engineering/transformations/landing/myhr_hierarchy_history/metadata.json`](/c:/Users/aablanya/Data_Pipeline/src/tag_data_engineering/transformations/landing/myhr_hierarchy_history/metadata.json).
2. The extractor is [`src/tag_data_engineering/extractors/myhr_hierarchy_history_blob_extractor.py`](/c:/Users/aablanya/Data_Pipeline/src/tag_data_engineering/extractors/myhr_hierarchy_history_blob_extractor.py).
3. The extractor reads CSV files from Azure Blob Storage in production.
4. For each CSV row, it appends `source_file_name` using the blob file basename.
5. The extractor yields `ExtractionBatch` records directly to the standard `LandingRunner`, which writes `jsonl`.
6. Bronze depends directly on `landing_myhr_hierarchy_history`.
7. Silver reads from `bronze.myhr_hierarchy_history`.

### Incremental behavior

The extractor uses a cursor with:

- `last_modified`
- `last_object_name`

Files are sorted by `(last_modified, object_name)`.

A file is processed when:

- its `last_modified` is greater than the cursor `last_modified`, or
- the timestamps are equal and its `object_name` is greater than the cursor `last_object_name`

This avoids missing files that share the same timestamp.

### Production and integration split

Production code is Azure-only:

- [`src/tag_data_engineering/extractors/blob_source.py`](/c:/Users/aablanya/Data_Pipeline/src/tag_data_engineering/extractors/blob_source.py)
- [`src/tag_data_engineering/extractors/myhr_hierarchy_history_blob_extractor.py`](/c:/Users/aablanya/Data_Pipeline/src/tag_data_engineering/extractors/myhr_hierarchy_history_blob_extractor.py)

Integration tests use a MinIO-specific test extractor:

- [`tests_integration/myhr_hierarchy_history_blob_extractor.py`](/c:/Users/aablanya/Data_Pipeline/tests_integration/myhr_hierarchy_history_blob_extractor.py)

This keeps MinIO test infrastructure out of production code.

### Downstream shape

Landing rows include `source_file_name`.

Bronze uses:

- `["Employee Id", "source_file_name"]`

This preserves file-level history and prevents later files from overwriting earlier files for the same employee.
