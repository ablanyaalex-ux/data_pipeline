-- Silver layer: Normalize column names for verint_activity_mapping
-- Converts column names to lowercase with underscores and applies proper typing
SELECT
    CAST(`ActivityMappingID` AS INTEGER) AS activity_mapping_id,
    CAST(`ActivityName` AS STRING) AS activity_name,
    CAST(`ActivityType` AS STRING) AS activity_type,
    CAST(`ActivityGrouping` AS STRING) AS activity_group,
    CAST(`Active` AS INTEGER) AS is_active,
    CAST(`ActiveStart` AS DATE) AS active_start_date,
    CAST(`ActiveEnd` AS DATE) AS active_end_date,
    CAST(`source_file_name` AS STRING) AS source_file_name,
    TO_DATE(REGEXP_REPLACE(ELEMENT_AT(SPLIT(CAST(`source_file_name` AS STRING), '_'), -1), '\\.csv$', ''), 'yyyyMMdd') AS source_file_date
FROM bronze.verint_activity_mapping
