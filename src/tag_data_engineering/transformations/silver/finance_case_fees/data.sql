-- Silver transformation for finance case fees
-- Reference table of fee amounts charged to companies per event type and sector

SELECT
    CAST(`sector`               AS STRING)          AS sector,
    CAST(`event_code`           AS STRING)          AS event_code,
    CAST(`event_name`           AS STRING)          AS event_name,
    CAST(`cost_amount`          AS DECIMAL(10,2))   AS cost_amount,
    CAST(`currency`             AS STRING)          AS currency,
    TO_DATE(CAST(`effective_from_date` AS STRING), 'dd/MM/yyyy') AS effective_from_date,
    TO_DATE(CAST(`effective_to_date`   AS STRING), 'dd/MM/yyyy') AS effective_to_date
FROM bronze.finance_case_fees
