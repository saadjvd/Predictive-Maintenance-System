from typing import List, Dict, Any, Optional
from app.extensions import db
from app.models.diagnostic import KnowledgeDocument, DocumentChunk
from app.ai_engine.rag.chunking import DocumentChunker
from app.ai_engine.rag.embeddings import EmbeddingProvider
from app.ai_engine.rag.knowledge_filters import KnowledgeSecurityFilter


class TechnicalKnowledgeStore:
    """Manages document chunking, vector indexing, and tenant-isolated retrieval."""

    @classmethod
    def index_document(
        cls,
        document_id: Optional[str] = None,
        text: Optional[str] = None,
        organization_id: Optional[str] = None,
        title: Optional[str] = None,
        content: Optional[str] = None,
        document_type: str = "SOP",
        machine_type: Optional[str] = None,
        component_type: Optional[str] = None,
        is_standard: bool = False,
        document_metadata: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Chunks document text, generates vector embeddings, and persists chunks in DB."""
        # Convenience mode: If title and content are provided, create the KnowledgeDocument first
        if title and (content or text):
            doc_content = content or text
            doc = KnowledgeDocument(
                organization_id=organization_id,
                title=title,
                document_type=document_type,
                component_type=component_type,
                source_filename=f"{title.lower().replace(' ', '_')}.pdf",
                is_standard=is_standard,
                approval_status="APPROVED",
            )
            db.session.add(doc)
            db.session.commit()
            document_id = doc.id
            text_to_chunk = doc_content
        else:
            if not document_id:
                raise ValueError("Either (title, content) or document_id must be provided.")
            doc = KnowledgeDocument.query.filter_by(id=document_id).first()
            if not doc:
                raise ValueError(f"KnowledgeDocument '{document_id}' not found.")
            text_to_chunk = text or ""

        # Delete existing chunks if re-indexing
        DocumentChunk.query.filter_by(document_id=document_id).delete()

        chunks = DocumentChunker.chunk_text(
            text=text_to_chunk,
            chunk_size=300,
            overlap=40,
            metadata=document_metadata or metadata or {},
        )

        for ch in chunks:
            sanitized_content = KnowledgeSecurityFilter.sanitize_passage(ch["content"])
            vec = EmbeddingProvider.generate_embedding(sanitized_content)

            chunk_obj = DocumentChunk(
                document_id=doc.id,
                organization_id=organization_id or doc.organization_id,
                chunk_index=ch["chunk_index"],
                content=sanitized_content,
                metadata_payload=ch["metadata"],
                embedding=vec,
            )
            db.session.add(chunk_obj)

        db.session.commit()
        return doc if (title and (content or text)) else len(chunks)

    @classmethod
    def similarity_search(
        cls,
        organization_id: str,
        query: str,
        category_id: Optional[str] = None,
        machine_type: Optional[str] = None,
        component_type: Optional[str] = None,
        top_k: int = 5,
        min_score: float = 0.05,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves top-k relevant technical passages strictly bounded by tenant organization.
        """
        query_vec = EmbeddingProvider.generate_embedding(query)

        # Retrieve candidate chunks belonging to tenant OR standard documents
        query_db = (
            DocumentChunk.query.join(KnowledgeDocument, DocumentChunk.document_id == KnowledgeDocument.id)
            .filter(
                (DocumentChunk.organization_id == organization_id) | (KnowledgeDocument.is_standard == True)
            )
            .filter(KnowledgeDocument.approval_status == "APPROVED")
        )

        if category_id:
            query_db = query_db.filter(
                (KnowledgeDocument.category_id == category_id) | (KnowledgeDocument.category_id.is_(None))
            )
        if component_type:
            query_db = query_db.filter(
                (KnowledgeDocument.component_type == component_type) | (KnowledgeDocument.component_type.is_(None))
            )

        chunks = query_db.all()
        scored_chunks: List[Dict[str, Any]] = []

        for ch in chunks:
            # Deterministic tenant isolation check
            if not KnowledgeSecurityFilter.validate_tenant_access(
                organization_id=organization_id,
                document_organization_id=ch.organization_id,
                is_standard=ch.document.is_standard if ch.document else False,
            ):
                continue

            score = EmbeddingProvider.compute_similarity(query_vec, ch.embedding or [])
            if score >= min_score:
                scored_chunks.append({
                    "document_id": ch.document_id,
                    "title": ch.document.title if ch.document else "Technical Guide",
                    "document_type": ch.document.document_type if ch.document else "SOP",
                    "chunk_index": ch.chunk_index,
                    "content_excerpt": ch.content,
                    "section": ch.metadata_payload.get("section") if ch.metadata_payload else "General",
                    "page_number": ch.metadata_payload.get("page_number") if ch.metadata_payload else None,
                    "source_filename": ch.document.source_filename if ch.document else "unknown.pdf",
                    "relevance_score": round(score, 3),
                    "is_standard": ch.document.is_standard if ch.document else False,
                })

        # Sort descending by relevance score
        scored_chunks.sort(key=lambda x: x["relevance_score"], reverse=True)
        return scored_chunks[:top_k]
