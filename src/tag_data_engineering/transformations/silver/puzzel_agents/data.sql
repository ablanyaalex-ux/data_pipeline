-- Silver layer: Clean and type agents records

SELECT
  CAST(agent_id AS INT) AS agent_id,
  CAST(customer_key AS STRING) AS customer_key,
  CAST(user_name AS STRING) AS user_name,
  CAST(user_num AS STRING) AS user_num,
  CAST(full_name AS STRING) AS full_name,
  CAST(usergroup_id AS INT) AS usergroup_id,
  CAST(usergroup_name AS STRING) AS usergroup_name,
  CAST(email AS STRING) AS email,
  CAST(mobile AS STRING) AS mobile,
  CAST(dte_updated AS TIMESTAMP) AS dte_updated,
  CAST(chat_role AS BOOLEAN) AS chat_role,
  CAST(chat_master_user_id AS INT) AS chat_master_user_id,
  CAST(unblockable_role AS INT) AS unblockable_role,
  CAST(unblockable_group AS INT) AS unblockable_group,
  CAST(deleted AS BOOLEAN) AS deleted,
  CAST(puzzel_id AS STRING) AS puzzel_id
FROM bronze.puzzel_agents;
