# Phase 3 — Intelligence & Knowledge Fabric

## Package

`knowledge_fabric/` — sources, documents, chunks, embeddings, entities, relationships,
claims, evidence, memory, hybrid retrieval, context assembly.

## Architecture

```
Agents / Agent OS
        ↓
KnowledgeFabric / MemoryService / ContextAssembler
        ↓
RetrievalEngine (semantic + lexical + hybrid)
        ↓
Persistent tables (kf_*)
```

## Embedding

`EmbeddingProvider` abstraction. Default: deterministic `HashEmbeddingProvider` for offline/tests.
Production can inject OpenAI/etc. without changing agents.

Vectors are **persisted** in `kf_embeddings` (JSON array). Similarity uses cosine in the service layer
(SQLite-compatible; pgvector can replace storage later behind the same interface).

## Security

- Organisation-scoped all queries
- `restricted` sources excluded from retrieval without `org_read`
- Retrieved content marked `role: retrieved_knowledge` (DATA, not instructions)
- Invalidated sources/chunks/embeddings excluded from search

## Tests

`tests/test_phase3_knowledge_fabric.py`
