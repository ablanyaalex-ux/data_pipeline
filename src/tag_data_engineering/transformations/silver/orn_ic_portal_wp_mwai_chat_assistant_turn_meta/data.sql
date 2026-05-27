-- silver.orn_ic_portal_wp_mwai_chat_assistant_turn_meta
-- What: One row per assistant turn, enriched with chat-level metadata.
-- Why: Supports assistant-turn analytics and provides the assistant turn extra
--      payload needed for downstream retrieval linking.
-- How: Filters assistant turns from silver.orn_ic_portal_wp_mwai_chat_turns
--      and joins chat-level metadata from silver.orn_ic_portal_wp_mwai_chats.

with assistant_turn_chat_metadata as (
  select
    chat_id,
    session_id,
    model_name,
    temperature,
    previous_response_id,
    previous_response_date
  from silver.orn_ic_portal_wp_mwai_chats
  where chat_id is not null
),

filtered_assistant_turns as (
  select
    chat_id,
    turn_index,
    turn_extra_json
  from silver.orn_ic_portal_wp_mwai_chat_turns
  where role = 'assistant'
)

select
  at.chat_id as chat_id,
  at.turn_index as turn_index,
  c.session_id as session_id,
  c.model_name as model_name,
  c.temperature as temperature,
  c.previous_response_id as previous_response_id,
  c.previous_response_date as previous_response_date,
  -- assistant turn extra (contains embeddings)
  at.turn_extra_json as assistant_extra_json
from filtered_assistant_turns at
join assistant_turn_chat_metadata c
  on c.chat_id = at.chat_id;
