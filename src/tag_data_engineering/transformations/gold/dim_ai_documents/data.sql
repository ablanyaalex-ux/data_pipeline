/*
===============================================================================
Object: gold.dim_ai_documents
What:
    Provide a document dimension representing knowledge documents retrieved by
    the AI assistant during chat responses.

Why:
    AI retrieval systems (RAG) reference documents from a knowledge base when
    generating responses. This dimension describes those documents so analytics
    can examine:
    - which documents are retrieved most often
    - which themes appear in AI responses
    - which knowledge areas support answers
    - document-level retrieval behaviour

    This model currently represents documents retrieved by the ORN WordPress
    Mwai AI chat system.

    The ai_system column is included so additional AI systems or knowledge
    sources can later align to the same document dimension.

    Future extensions may include additional metadata such as:
    - document version
    - knowledge base identifier
    - document embeddings
    - document classification tags

How:
    Reads document metadata from
    silver.orn_ic_portal_wp_mwai_chat_retrieval_context_docs.

    Gold does not perform additional parsing here; it presents the curated
    document attributes in a business-facing dimensional structure.

Grain:
    One row per ai_system + context_id.

Design notes:
    - context_text_full is retained for debugging and DS experimentation but
      may be moved to a separate document store if document volumes grow
      significantly.
    - ai_system identifies the originating AI platform.
===============================================================================
*/

select
    'orn_ic_portal_mwai' as ai_system,
    context_id,
    context_title,
    context_url,
    context_key_themes,
    context_summary,
    context_text_full
from silver.orn_ic_portal_wp_mwai_chat_retrieval_context_docs;
