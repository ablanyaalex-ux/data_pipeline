-- Silver transformation for complaints
-- Excludes sensitive fields and formats data types properly

SELECT
    CAST(id AS BIGINT) AS id,
    CAST(reference AS STRING) AS reference,
    CAST(status AS STRING) AS status,
    CAST(prev_status AS STRING) AS prev_status,
    CAST(status_details AS STRING) AS status_details,
    CAST(status_changed_at AS TIMESTAMP) AS status_changed_at,
    CAST(company_id AS BIGINT) AS company_id,
    CAST(sector_id AS BIGINT) AS sector_id,
    CAST(service_type_id AS BIGINT) AS service_type_id,
    CAST(channel_id AS INT) AS channel_id,
    CAST(consumer_id AS BIGINT) AS consumer_id,
    CAST(user_datum_id AS BIGINT) AS user_datum_id,
    CAST(representative_datum_id AS BIGINT) AS representative_datum_id,
    CAST(correspondence_datum_id AS BIGINT) AS correspondence_datum_id,
    CAST(company_response_id AS BIGINT) AS company_response_id,
    CAST(issue_id AS BIGINT) AS issue_id,
    CAST(customer_type AS STRING) AS customer_type,
    -- CAST(business AS BOOLEAN) AS business,
    CAST(existing_customer AS BOOLEAN) AS existing_customer,
    CAST(company_referral AS BOOLEAN) AS company_referral,
    CAST(referral_type AS STRING) AS referral_type,
    CAST(first_complained_at AS TIMESTAMP) AS first_complained_at,
    -- CAST(response_at AS TIMESTAMP) AS response_at,
    CAST(decision_at AS TIMESTAMP) AS decision_at,
    CAST(next_action_at AS TIMESTAMP) AS next_action_at,
    CAST(prev_next_action_at AS TIMESTAMP) AS prev_next_action_at,
    CAST(created_at AS TIMESTAMP) AS created_at,
    CAST(updated_at AS TIMESTAMP) AS updated_at
FROM bronze.cms_complaints
