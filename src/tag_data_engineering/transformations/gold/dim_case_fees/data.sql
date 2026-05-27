-- Dimension: Case Fees
-- Reference table of fees charged to companies per case event type, sector, and effective date range

SELECT
    SHA2(CONCAT(sector, '|', event_code, '|', CAST(effective_from_date AS STRING)), 256) AS case_fee_id,
    CAST(sector             AS STRING)      AS sector,
    CAST(event_code         AS STRING)      AS event_code,
    CAST(event_name         AS STRING)      AS event_name,
    CAST(cost_amount        AS DECIMAL(10,2)) AS cost_amount,
    CAST(currency           AS STRING)      AS currency,
    CAST(effective_from_date AS DATE)       AS effective_from_date,
    CAST(effective_to_date   AS DATE)       AS effective_to_date
FROM silver.finance_case_fees
