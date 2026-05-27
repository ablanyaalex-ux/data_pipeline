-- silver.orn_ic_portal_wp_mwai_chats
-- What: One row per WordPress AI chat record from wp_mwai_chats.
-- Why: Creates a stable chat-level hub for downstream turn + retrieval analytics.
-- How: Casts core fields, preserves raw JSON columns (messages_json, extra_json)
--      for traceability, and extracts selected metadata fields from extra_json.

select
  cast(userId as bigint)                         as user_id,
  cast(ip as string)                             as ip_address,
  cast(botId as string)                          as bot_id,
  cast(chatId as string)                         as chat_id,
  cast(created as timestamp)                     as created_at,
  cast(updated as timestamp)                     as updated_at,
  cast(messages as string)                       as messages_json,
  cast(extra as string)                          as extra_json,
  cast(get_json_object(extra, '$.session') as string)                 as session_id,
  cast(get_json_object(extra, '$.model') as string)                   as model_name,
  cast(get_json_object(extra, '$.temperature') as double)             as temperature,
  cast(get_json_object(extra, '$.previousResponseId') as string)      as previous_response_id,
  cast(get_json_object(extra, '$.previousResponseDate') as timestamp) as previous_response_date,
  cast(get_json_object(extra, '$.context') as string)                 as context_raw
from bronze.orn_ic_portal_wp_mwai_chats
where chatId is not null;
