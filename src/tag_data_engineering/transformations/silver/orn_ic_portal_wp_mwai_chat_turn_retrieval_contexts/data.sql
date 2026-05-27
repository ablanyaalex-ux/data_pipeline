/*
===============================================================================
Object: silver.orn_ic_portal_wp_mwai_chat_turn_retrieval_contexts
Purpose:
    Link assistant chat turns to the retrieval context documents used for those
    turns, using embeddings metadata plus parsed context docs.

Why this exists:
    Assistant turns contain embeddings metadata identifying retrieved items,
    while the readable context document details are parsed separately from the
    chat-level context blob.

Important design note:
    This object should continue to use:
        silver.orn_ic_portal_wp_mwai_chat_assistant_turn_meta
    for embeddings metadata
    and join to:
        silver.orn_ic_portal_wp_mwai_chat_retrieval_context_docs
    for the parsed context document details.

Design separation:
    - assistant_turn_meta = assistant-turn embedding metadata / retrieval references
    - retrieval_context_docs = parsed document details from chat extra_json.context

This separation is intentional:
    assistant_turn_meta.assistant_extra_json only contains embeddings, not the
    full context blob, so it cannot by itself provide the document text, title,
    summary, themes, or URL.

Role in model:
    This object is the bridge between:
    - assistant turn retrieval metadata
    and
    - business-readable retrieval context docs

Expected contents:
    One row per turn-to-context match, with fields such as:
    - chat_id
    - turn_index
    - context_id
    - post_id_hash
    - doc_type
    - doc_title
    - context_score
    - matched context doc attributes from retrieval_context_docs

Data quality / testing note:
    Downstream test outputs involving multiline context content must be compared
    using LF-normalized expected CSV files, as Linux/docker output will not
    match CRLF-based expected files byte-for-byte.
===============================================================================
*/

with assistant_turn_embedding_source as (
  select
    chat_id,
    turn_index,
    assistant_extra_json
  from silver.orn_ic_portal_wp_mwai_chat_assistant_turn_meta
  where assistant_extra_json is not null
),

parsed_assistant_turn_embeddings as (
  select
    chat_id,
    turn_index,
    from_json(
      assistant_extra_json,
      'struct<embeddings:array<struct<id:string,type:string,title:string,ref:string,score:double>>>'
    ) as extra_struct
  from assistant_turn_embedding_source
),

exploded_assistant_turn_embeddings as (
  select
    chat_id,
    turn_index,
    emb.id     as post_id_hash,
    emb.type   as doc_type,
    emb.title  as doc_title,
    cast(emb.ref as string) as context_id,
    emb.score  as context_score
  from parsed_assistant_turn_embeddings
  lateral view explode_outer(extra_struct.embeddings) e as emb
  where emb.ref is not null
),

retrieval_context_doc_lookup as (
  select
    chat_id,
    context_id,
    context_title,
    context_url,
    context_key_themes,
    context_summary,
    context_text_full
  from silver.orn_ic_portal_wp_mwai_chat_retrieval_context_docs
)

select
  e.chat_id as chat_id,
  e.turn_index as turn_index,
  e.context_id as context_id,
  cast(e.post_id_hash as string) as post_id_hash,
  cast(e.doc_type as string) as doc_type,
  cast(e.doc_title as string) as doc_title,
  cast(e.context_score as double) as context_score,
  d.context_title as context_title,
  d.context_url as context_url,
  d.context_key_themes as context_key_themes,
  d.context_summary as context_summary,
  d.context_text_full as context_text_full
from exploded_assistant_turn_embeddings e
left join retrieval_context_doc_lookup d
  on d.chat_id = e.chat_id
 and d.context_id = e.context_id;
