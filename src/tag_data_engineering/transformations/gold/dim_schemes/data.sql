SELECT
    CAST(sector_customer_type_id AS INT)    AS sector_customer_type_id,
    CAST(sector_customer_type AS STRING)    AS sector_customer_type
FROM silver.ref_schemes
