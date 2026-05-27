-- Silver layer: Flatten Verint employee expected adherence activities
-- Each scheduled activity becomes a separate row
-- Migth need to discuss if we need to seperate the actual and scheduled activities into different tables

WITH parsed_activities AS (
    SELECT
        CAST(attributes_employeeIdentifier AS STRING) AS employee_identifier,
        CAST(attributes_employeeLookupKey AS STRING) AS employee_lookup_key,
        CAST(attributes_adherenceStartDate AS TIMESTAMP) AS adherence_start_date,
        CAST(attributes_adherenceEndDate AS TIMESTAMP) AS adherence_end_date,
        TRANSFORM(
            SPLIT(
                REGEXP_REPLACE(
                    REGEXP_REPLACE(CAST(attributes_scheduledActivityList AS STRING), '^\\[\\{', ''),
                    '\\}\\]$',
                    ''
                ),
                '\\}, \\{'
            ),
            item -> STRUCT(
                ELEMENT_AT(SPLIT(item, ', '), 2) AS activityName,
                ELEMENT_AT(SPLIT(item, ', '), 3) AS activityStartTime,
                ELEMENT_AT(SPLIT(item, ', '), 1) AS activityEndTime,
                ELEMENT_AT(SPLIT(item, ', '), 4) AS isPaid
            )
        ) AS scheduled_activities
    FROM bronze.verint_employee_adherence
    WHERE attributes_scheduledActivityList IS NOT NULL
      AND CAST(attributes_scheduledActivityList AS STRING) <> '[]'
)
SELECT
    employee_identifier,
    employee_lookup_key,
    adherence_start_date,
    adherence_end_date,
    'scheduled' AS activity_type,
    CAST(activity.activityName AS STRING) AS activity_name,
    CAST(activity.activityStartTime AS TIMESTAMP) AS activity_start_time,
    CAST(activity.activityEndTime AS TIMESTAMP) AS activity_end_time,
    CASE WHEN LOWER(CAST(activity.isPaid AS STRING)) = 'true' THEN TRUE ELSE FALSE END AS is_paid
FROM parsed_activities
LATERAL VIEW EXPLODE(scheduled_activities) AS activity

