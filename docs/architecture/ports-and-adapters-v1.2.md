# v1.2 Ports and Adapters

Ports are owned by the consumer. `application/practice` owns the small
`PracticeWorkflowPort`; the Stage 5 service is its SQLAlchemy adapter. Tutor
owns `TutorDependencies`, which supplies only public-question, retrieval,
learning-profile/memory, grading, source projection and explicit-confusion
operations. The fixed Tutor v1 runtime still consists solely of
`AgentRunner`, `ToolRegistry`, `ModelGateway`, `AgentContext`, `AgentEvent`
and `AgentResult`.

`agent_runtime` no longer opens sessions, queries ORM models, calls RAG, or
persists learning memory. Those operations are in `adapters/tutor_dependencies`.
The OpenAI-compatible implementation is also an adapter and converts provider
failures to the small internal error taxonomy. Fakes exercise Tutor execution
without an LLM, Qdrant, Redis, or PostgreSQL.

The boundary is selective: existing `rag_service` remains the Qdrant/metadata
adapter rather than being rewritten as a parallel RAG system.
