/*
===============================================================================
Object: gold.fact_ai_retrievals
What:
    Provide the retrieval event fact table for ORN AI chat analytics, with one
    row per retrieved document for a given assistant turn.

Why:
    This table captures retrieval behaviour from the AI assistant, allowing
    downstream analytics, semantic models, and Data Science work to examine:
    - which documents were retrieved
    - how often documents were retrieved
    - retrieval score patterns
    - retrieval behaviour by interaction turn
    - retrieval behaviour by AI system

    This model currently represents the ORN WordPress Mwai AI chat source.
    However, the gold layer is being designed so additional AI/bot systems can
    be added later without redesigning the fact/dimension structure.

    For that reason, an ai_system column is included as a source/system marker.
    This allows future retrieval data from other AI platforms to align to the
    same analytics model.

How:
    - Reads curated turn-level retrieval rows from
      silver.orn_ic_portal_wp_mwai_chat_turn_retrieval_contexts
    - Keeps one row per retrieved document per assistant turn
    - Preserves document identifiers, retrieval score, and descriptive document
      metadata for immediate analytical use
    - Presents a business-facing fact structure without exposing raw JSON

Grain:
    One row per ai_system + chat_id + turn_index + context_id.

Design notes:
    - context_id links to gold.dim_ai_documents
    - chat_id + turn_index links to gold.fact_ai_interactions
    - descriptive document fields are retained here for ease of DS exploration
      and analytical use, even though the document dimension also exists
    - ai_system identifies the originating AI platform and is included to
      future-proof the model for additional AI/bot sources
===============================================================================
*/

select
  'orn_ic_portal_mwai' as ai_system,
  chat_id,
  turn_index,
  context_id,
  post_id_hash,
  doc_type,
  doc_title,
  context_score,
  context_title,
  context_url,
  context_key_themes,
  context_summary,
  context_text_full
from silver.orn_ic_portal_wp_mwai_chat_turn_retrieval_contexts;
