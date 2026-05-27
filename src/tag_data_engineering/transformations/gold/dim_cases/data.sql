SELECT
    CAST(comp.id AS BIGINT)                AS case_id,
    sct.sector_customer_type_id,
    CAST(comp.status AS STRING)            AS current_status,
    CAST(comp.company_id AS BIGINT)        AS company_id,
    CAST(comp.created_at AS TIMESTAMP)     AS created_at
FROM silver.cms_complaints comp
LEFT JOIN silver.cms_sectors s
    ON comp.sector_id = s.id
LEFT JOIN bronze.cms_complaints compbronze
    ON comp.id = compbronze.id
LEFT JOIN gold.dim_schemes sct
    ON sct.sector_customer_type = CASE
        WHEN s.name = 'Communications' THEN 'Communications'
        WHEN s.name = 'Energy'
             AND LOWER(COALESCE(compbronze.usage, '')) LIKE '%business%' THEN 'Energy B2B'
        WHEN s.name = 'Energy' THEN 'Energy B2C'
        ELSE 'FRS'
    END
