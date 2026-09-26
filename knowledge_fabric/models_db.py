"""Phase 3 Knowledge Fabric durable schema."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    JSON,
    Index,
    UniqueConstraint,
)

from database.models import Base


class KFSource(Base):
    __tablename__ = "kf_sources"
    source_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    source_type = Column(String(64), nullable=False)  # document|web|conversation|task|workflow|user|agent|api|report
    title = Column(String(512), default="")
    location = Column(String(1024), nullable=True)  # path/url
    origin = Column(String(255), nullable=True)
    reliability = Column(String(32), default="UNVERIFIED")  # USER_CONFIRMED|SOURCE_VERIFIED|SYSTEM_OBSERVED|AGENT_DERIVED|UNVERIFIED
    version = Column(Integer, default=1)
    status = Column(String(32), default="active")  # active|invalidated|archived
    owner_id = Column(String(64), nullable=True)
    permissions = Column(JSON, default=list)  # e.g. ["org_read"]
    metadata_json = Column(JSON, default=dict)
    observed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (Index("ix_kf_sources_org_type", "organisation_id", "source_type"),)


class KFDocument(Base):
    __tablename__ = "kf_documents"
    document_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    source_id = Column(String(64), nullable=False, index=True)
    title = Column(String(512), default="")
    content_type = Column(String(64), default="text/plain")  # pdf|docx|txt|md|html|csv|json
    content = Column(Text, default="")
    status = Column(String(32), default="ingested")  # ingested|processed|indexed|invalidated
    version = Column(Integer, default=1)
    page_count = Column(Integer, nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (Index("ix_kf_docs_org", "organisation_id", "status"),)


class KFChunk(Base):
    __tablename__ = "kf_chunks"
    chunk_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    document_id = Column(String(64), nullable=False, index=True)
    source_id = Column(String(64), nullable=False, index=True)
    ordinal = Column(Integer, default=0)
    content = Column(Text, nullable=False)
    heading = Column(String(512), nullable=True)
    page = Column(Integer, nullable=True)
    section = Column(String(255), nullable=True)
    token_estimate = Column(Integer, default=0)
    status = Column(String(32), default="active")
    version = Column(Integer, default=1)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_kf_chunks_org_doc", "organisation_id", "document_id"),
        UniqueConstraint("document_id", "ordinal", "version", name="uq_kf_chunk_ord"),
    )


class KFEmbedding(Base):
    __tablename__ = "kf_embeddings"
    embedding_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    chunk_id = Column(String(64), nullable=False, index=True)
    provider = Column(String(64), nullable=False)
    model = Column(String(128), nullable=False)
    dimensions = Column(Integer, nullable=False)
    vector = Column(JSON, nullable=False)  # list[float] — persistent; cosine search in service layer
    embedding_version = Column(String(32), default="1")
    status = Column(String(32), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_kf_emb_org_chunk", "organisation_id", "chunk_id"),
        Index("ix_kf_emb_org_model", "organisation_id", "model"),
    )


class KFEntity(Base):
    __tablename__ = "kf_entities"
    entity_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    entity_type = Column(String(64), nullable=False, index=True)
    canonical_name = Column(String(512), nullable=False)
    aliases = Column(JSON, default=list)
    status = Column(String(32), default="active")
    confidence = Column(Float, default=0.5)
    metadata_json = Column(JSON, default=dict)
    provenance = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_kf_ent_org_type_name", "organisation_id", "entity_type", "canonical_name"),
    )


class KFRelationship(Base):
    __tablename__ = "kf_relationships"
    relationship_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    source_entity_id = Column(String(64), nullable=False, index=True)
    relationship_type = Column(String(128), nullable=False)
    target_entity_id = Column(String(64), nullable=False, index=True)
    confidence = Column(Float, default=0.5)
    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)
    status = Column(String(32), default="active")
    provenance = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_kf_rel_org_type", "organisation_id", "relationship_type"),
    )


class KFClaim(Base):
    __tablename__ = "kf_claims"
    claim_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    claim_text = Column(Text, nullable=False)
    subject = Column(String(512), nullable=True)
    predicate = Column(String(255), nullable=True)
    object_text = Column(Text, nullable=True)
    status = Column(String(32), default="UNVERIFIED")  # SUPPORTED|PARTIALLY_SUPPORTED|CONTRADICTED|UNVERIFIED|SUPERSEDED
    confidence = Column(Float, default=0.5)
    confidence_kind = Column(String(32), default="derived")  # user_provided|observed|source_supported|derived|inferred|unresolved
    version = Column(Integer, default=1)
    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)
    observed_at = Column(DateTime, nullable=True)
    source_id = Column(String(64), nullable=True, index=True)
    task_id = Column(String(64), nullable=True)
    workflow_id = Column(String(64), nullable=True)
    agent_key = Column(String(128), nullable=True)
    evidence_ids = Column(JSON, default=list)
    status_note = Column(Text, nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_kf_claims_org_status", "organisation_id", "status"),
    )


class KFEvidence(Base):
    __tablename__ = "kf_evidence"
    evidence_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    content = Column(Text, nullable=False)
    source_id = Column(String(64), nullable=True, index=True)
    document_id = Column(String(64), nullable=True)
    chunk_id = Column(String(64), nullable=True)
    claim_id = Column(String(64), nullable=True, index=True)
    confidence = Column(Float, default=0.5)
    confidence_kind = Column(String(32), default="source_supported")
    provenance = Column(JSON, default=dict)
    permissions = Column(JSON, default=list)
    status = Column(String(32), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("ix_kf_ev_org", "organisation_id", "status"),)


class KFMemory(Base):
    __tablename__ = "kf_memories"
    memory_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    memory_type = Column(String(32), nullable=False, index=True)  # working|episodic|semantic|conversational|task|workflow|organizational|agent
    content = Column(JSON, nullable=False)
    scope = Column(String(64), default="org")  # org|user|agent|task
    user_id = Column(String(64), nullable=True, index=True)
    agent_key = Column(String(128), nullable=True)
    task_id = Column(String(64), nullable=True, index=True)
    workflow_id = Column(String(64), nullable=True, index=True)
    status = Column(String(32), default="active")  # active|invalidated|archived
    trust_level = Column(String(32), default="AGENT_DERIVED")
    provenance = Column(JSON, default=dict)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_kf_mem_org_type", "organisation_id", "memory_type"),
    )


class KFRetrievalTrace(Base):
    __tablename__ = "kf_retrieval_traces"
    retrieval_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    requester = Column(String(128), nullable=True)
    agent_key = Column(String(128), nullable=True)
    task_id = Column(String(64), nullable=True)
    query = Column(Text, default="")
    strategy = Column(String(64), default="hybrid")
    filters = Column(JSON, default=dict)
    result_count = Column(Integer, default=0)
    selected = Column(JSON, default=list)
    ranking = Column(JSON, default=list)
    latency_ms = Column(Integer, default=0)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("ix_kf_ret_org", "organisation_id", "created_at"),)
