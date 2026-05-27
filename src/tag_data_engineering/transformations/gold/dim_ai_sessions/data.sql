/*
===============================================================================
Object: gold.dim_ai_sessions
What:
    Provide a business-facing AI session dimension for ORN bot analytics, with
    one row per chat/session.

Why:
    This table is the descriptive session-level object for the AI analytics
    model. It exposes stable attributes about each AI chat so downstream facts,
    semantic models, and reporting can slice and filter interaction behaviour
    by bot, model, session, and time.

    This model currently represents the ORN WordPress Mwai AI chat source.
    However, the gold layer is being shaped to support future AI/bot analytics
    across additional systems without requiring a redesign of the core model.

    For that reason, an ai_system column is included as a source/system marker.
    This allows future AI interaction data from other platforms to align to the
    same dimensional model.

    Additional derived signals may be introduced later by Data Science or other
    pipelines, such as:
    - classifier outputs
    - evaluation metrics
    - hallucination or quality flags
    - token or cost usage
    - user feedback or outcome data

    Those future signals should be added as separate fact tables rather than
    altering the foundational session dimension unnecessarily.

How:
    - Reads curated session/chat-level attributes from
      silver.orn_ic_portal_wp_mwai_chats
    - Derives a session-level has_retrieval flag from
      silver.orn_ic_portal_wp_mwai_chat_turn_retrieval_contexts
    - Presents a business-facing dimensional structure without exposing raw JSON

Grain:
    One row per ai_system + chat_id.

Design notes:
    - chat_id is currently the stable warehouse key for the session dimension.
    - session_id is retained as an attribute because future sources may use it
      as a broader analytical session reference.
    - has_retrieval is included here as a useful reporting/session attribute,
      while detailed retrieval events remain in a separate fact table.
    - ai_system identifies the originating AI platform and is included to
      future-proof the model for additional AI/bot sources.
===============================================================================
*/

with session_source_chats as (
  select
    chat_id,
    bot_id,
    created_at,
    updated_at,
    session_id,
    model_name,
    temperature,
    previous_response_id,
    previous_response_date
  from silver.orn_ic_portal_wp_mwai_chats
),

session_retrieval_flags  as (
  select
    chat_id,
    1 as has_retrieval
  from silver.orn_ic_portal_wp_mwai_chat_turn_retrieval_contexts
  group by chat_id
)

select
  'orn_ic_portal_mwai' as ai_system,
  c.chat_id as chat_id,
  c.bot_id as bot_id,
  c.created_at as created_at,
  c.updated_at as updated_at,
  c.session_id as session_id,
  c.model_name as model_name,
  c.temperature as temperature,
  c.previous_response_id as previous_response_id,
  c.previous_response_date as previous_response_date,
  coalesce(r.has_retrieval, 0) as has_retrieval
from session_source_chats  c
left join session_retrieval_flags  r
  on r.chat_id = c.chat_id;
