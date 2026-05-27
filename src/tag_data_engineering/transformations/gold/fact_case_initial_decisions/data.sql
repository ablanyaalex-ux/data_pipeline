-- Fact: Case Initial Decisions
-- Maps each case to its latest non-final decision
-- Replaces latest_nonfinal_decisions CTE in queries

WITH ranked_decisions AS (
    SELECT
        case_id,
        decision_id,
        created_date,
        ROW_NUMBER() OVER (
            PARTITION BY case_id
            ORDER BY created_date DESC, decision_id DESC
        ) AS rn
    FROM gold.fact_decisions
    WHERE is_final = 0
)
SELECT
    case_id,
    decision_id AS initial_decision_id
FROM ranked_decisions
WHERE rn = 1
