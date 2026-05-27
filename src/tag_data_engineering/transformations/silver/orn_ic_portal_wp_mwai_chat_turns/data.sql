-- silver.orn_ic_portal_wp_mwai_chat_turns
-- What: One row per message/turn in a chat (turn_index = array position).
-- Why: Creates the turn-level grain for chat analytics, including role, content,
--      and any turn-level extra payload needed downstream.
-- How: Reads messages_json from silver.orn_ic_portal_wp_mwai_chats, normalizes
--      object-or-array message JSON into a consistent array structure, then uses
--      posexplode for stable turn ordering.

with source_chat_messages as (
  select
    chat_id,
    messages_json
  from silver.orn_ic_portal_wp_mwai_chats
  where chat_id is not null
    and messages_json is not null
),

normalized_chat_messages as (
  select
    chat_id,
    case
      when trim(messages_json) like '[%' then messages_json
      else concat('[', messages_json, ']')
    end as messages_array_json
  from source_chat_messages
),

parsed_chat_message_array as (
  select
    chat_id,
    from_json(
      messages_array_json,
      'array<struct<
         role:string,
         content:string,
         extra:struct<
           embeddings:array<struct<
             id:string,
             type:string,
             title:string,
             ref:string,
             score:double
           >>
         >
       >>'
    ) as messages_arr
  from normalized_chat_messages
),

exploded_chat_turns as (
  select
    chat_id,
    cast(pos as int) as turn_index,
    cast(msg.role as string) as role,
    cast(msg.content as string) as content,
    to_json(msg.extra) as turn_extra_json,
    case when msg.extra is not null then 1 else 0 end as has_turn_extra
  from parsed_chat_message_array
  lateral view posexplode_outer(messages_arr) t as pos, msg
)

select
  chat_id,
  turn_index,
  role,
  content,
  turn_extra_json,
  has_turn_extra
from exploded_chat_turns;
