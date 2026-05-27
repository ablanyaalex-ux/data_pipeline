SELECT
    DATE_FORMAT(initial_decision_date, 'yyyy-MMM') as year_month,

    -- Maintained
    SUM(CASE WHEN initial_decision_outcome = 'Maintained' THEN 1 ELSE 0 END) as maintained_decisions,
    ROUND(AVG(CASE WHEN initial_decision_outcome = 'Maintained' THEN days_to_initial_decision END), 2) as maintained_avg_days,

    -- Not Upheld
    SUM(CASE WHEN initial_decision_outcome = 'Not Upheld' THEN 1 ELSE 0 END) as not_upheld_decisions,
    ROUND(AVG(CASE WHEN initial_decision_outcome = 'Not Upheld' THEN days_to_initial_decision END), 2) as not_upheld_avg_days,

    -- Upheld
    SUM(CASE WHEN initial_decision_outcome = 'Upheld' THEN 1 ELSE 0 END) as upheld_decisions,
    ROUND(AVG(CASE WHEN initial_decision_outcome = 'Upheld' THEN days_to_initial_decision END), 2) as upheld_avg_days,

    -- Total
    COUNT(*) as total_decisions,
    ROUND(AVG(days_to_initial_decision), 2) as total_avg_days

FROM results
GROUP BY DATE_FORMAT(initial_decision_date, 'yyyy-MMM')
ORDER BY MIN(initial_decision_date) DESC
;
