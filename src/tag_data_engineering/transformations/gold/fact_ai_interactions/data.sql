/*
===============================================================================
Object: gold.fact_ai_interactions
What:
    Provide the primary interaction event fact table for ORN AI chat analytics.

Why:
    This table captures the behavioural sequence of AI chat sessions. Each row
    represents a single interaction turn, such as a user message or an
    assistant response.

    This model currently represents the ORN WordPress Mwai AI chat source.
    However, the gold layer is being designed so additional AI/bot systems can
    be introduced later without changing the core fact/dimension structure.

    For that reason, an ai_system column is included as a source/system marker.
    This allows future interaction data from other AI platforms to align to the
    same warehouse fact model.

    The table supports analytics such as:
    - session length
    - assistant vs user interaction ratios
    - turn-level behavioural analysis
    - identifying assistant responses that used document retrieval

    Future AI evaluation signals such as classifier outputs, hallucination
    flags, answer quality scores, or outcome signals may later join to this
    fact using (chat_id, turn_index), or a broader future cross-system
    interaction key if introduced.

How:
    - Reads curated turn-level rows from
      silver.orn_ic_portal_wp_mwai_chat_turns
    - Flags assistant and user turns for easier aggregation
    - Derives a turn-level retrieval flag from
      silver.orn_ic_portal_wp_mwai_chat_turn_retrieval_contexts
    - Presents a business-facing fact structure without exposing raw JSON

Grain:
    One row per ai_system + chat_id + turn_index.

Design notes:
    - role remains the source-of-truth descriptive field.
    - is_assistant_turn and is_user_turn are included to simplify reporting and
      semantic model calculations.
    - has_retrieval is included as a turn-level behavioural flag.
    - ai_system identifies the originating AI platform and is included to
      future-proof the model for additional AI/bot sources.
===============================================================================
*/

with interaction_turn_source as (
  select
    chat_id,
    turn_index,
    role,
    content,
    has_turn_extra
  from silver.orn_ic_portal_wp_mwai_chat_turns
),

retrieval_flagged_turns as (
  select distinct
    chat_id,
    turn_index
  from silver.orn_ic_portal_wp_mwai_chat_turn_retrieval_contexts
)

select
  'orn_ic_portal_mwai' as ai_system,
  t.chat_id as chat_id,
  t.turn_index as turn_index,
  t.role as role,
  t.content as content,
  case when t.role = 'assistant' then 1 else 0 end as is_assistant_turn,
  case when t.role = 'user' then 1 else 0 end as is_user_turn,
  t.has_turn_extra as has_turn_extra,
  case
    when r.chat_id is not null then 1
    else 0
  end as has_retrieval
from interaction_turn_source t
left join retrieval_flagged_turns r
  on r.chat_id = t.chat_id
 and r.turn_index = t.turn_index;
