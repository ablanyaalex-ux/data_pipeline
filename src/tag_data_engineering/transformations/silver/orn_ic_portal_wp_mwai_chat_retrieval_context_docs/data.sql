/*
===============================================================================
Object: silver.orn_ic_portal_wp_mwai_chat_retrieval_context_docs
Purpose:
    Parse and expose retrieval context documents for each chat from the
    conversation-level extra_json.context held in silver.orn_ic_portal_wp_mwai_chats.

Why this exists:
    The ORN chat source stores retrieval context text in the chat-level
    extra_json.context field, not in assistant turn metadata.

Important design note:
    assistant_turn_meta.assistant_extra_json only contains embeddings and does
    not contain the full retrieval context blob. Therefore this object must be
    built from:
        silver.orn_ic_portal_wp_mwai_chats.extra_json.context
    and not from:
        silver.orn_ic_portal_wp_mwai_chat_assistant_turn_meta

Role in model:
    This object provides the parsed, document-level representation of retrieved
    context content so that downstream joins can link assistant-turn embeddings
    to business-readable context documents.

Expected contents:
    One row per parsed retrieval context document, with fields such as:
    - chat_id
    - context_id
    - context_title
    - context_url
    - context_key_themes
    - context_summary
    - context_text_full
    - context_block_text

Data quality / testing note:
    Retrieval context test data includes multiline text fields. Expected CSV
    test files must use LF line endings to match Linux/docker pipeline output.
===============================================================================
*/

with source_chat_context as (
  select
    chat_id,
    get_json_object(extra_json, '$.context') as context_raw
  from silver.orn_ic_portal_wp_mwai_chats
  where extra_json is not null
    and get_json_object(extra_json, '$.context') is not null
),

normalized_chat_context as (
  select
    chat_id,

    -- Turn the "---- Field: value ---- Field2: value2 ----" string
    -- into a newline-delimited block that is easy to parse.
    trim(
      regexp_replace(
        regexp_replace(context_raw, '\\s*----\\s*', '\n'),
        '^\\n+|\\n+$',
        ''
      )
    ) as context_block
  from source_chat_context
),

parsed_chat_context_docs as (
  select
    chat_id,
    trim(regexp_extract(context_block, '(?m)^Title:\\s*(.*)$', 1)) as context_title,
    trim(regexp_extract(context_block, '(?m)^ID:\\s*(.*)$', 1)) as context_id,
    trim(regexp_extract(context_block, '(?m)^URL:\\s*(.*)$', 1)) as context_url,
    trim(regexp_extract(context_block, '(?m)^Key Themes:\\s*(.*)$', 1)) as context_key_themes,
    trim(regexp_extract(context_block, '(?m)^Summary:\\s*(.*)$', 1)) as context_summary
  from normalized_chat_context
)

select
  cast(chat_id as string) as chat_id,
  cast(context_id as string) as context_id,
  cast(context_title as string) as context_title,
  cast(context_url as string) as context_url,
  cast(context_key_themes as string) as context_key_themes,
  cast(context_summary as string) as context_summary,
  concat_ws('\n',
    concat('Title: ', context_title),
    concat('ID: ', context_id),
    concat('URL: ', context_url),
    concat('Key Themes: ', context_key_themes),
    concat('Summary: ', context_summary)
  ) as context_text_full,
concat_ws('\n',
    concat('title: ', context_title),
    concat('id: ', context_id),
    concat('url: ', context_url),
    concat('key_themes: ', context_key_themes),
    concat('summary: ', context_summary)
  ) as context_block_text
from parsed_chat_context_docs
where context_id is not null;
