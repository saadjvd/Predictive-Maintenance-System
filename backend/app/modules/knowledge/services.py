"""Service layer for technical documentation indexing and retrieval."""
import logging
from typing import Dict, Any, List, Optional
from app.extensions import db
from app.models.diagnostic import KnowledgeDocument, DocumentChunk
from app.ai_engine.rag.vector_store import TechnicalKnowledgeStore

logger = logging.getLogger(__name__)


class KnowledgeService:
    """Manages technical documents, vector embeddings, and RAG retrieval."""

    @classmethod
    def create_document(
        cls,
        organization_id: str,
        title: str,
        document_type: str,
        content: str,
        machine_type: Optional[str] = None,
        component_type: Optional[str] = None,
        is_standard: bool = False,
        document_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Indexes and vectorizes a new technical document."""
        if not title or not content:
            raise ValueError("title and content are required.")

        doc = TechnicalKnowledgeStore.index_document(
            organization_id=organization_id,
            title=title.strip(),
            document_type=document_type or "SOP",
            content=content.strip(),
            machine_type=machine_type,
            component_type=component_type,
            is_standard=is_standard,
            document_metadata=document_metadata,
        )
        return doc.to_dict()

    @classmethod
    def list_documents(
        cls,
        organization_id: str,
        document_type: Optional[str] = None,
        machine_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Lists accessible technical documents (organization-owned or standard)."""
        query = KnowledgeDocument.query.filter(
            (KnowledgeDocument.organization_id == organization_id) | (KnowledgeDocument.is_standard == True)
        )
        if document_type:
            query = query.filter_by(document_type=document_type)
        if machine_type:
            query = query.filter_by(machine_type=machine_type)

        docs = query.order_by(KnowledgeDocument.created_at.desc()).limit(limit).all()
        return [d.to_dict() for d in docs]

    @classmethod
    def get_document(cls, document_id: str, organization_id: str) -> Dict[str, Any]:
        """Retrieves document details and its indexed chunks."""
        doc = KnowledgeDocument.query.filter(
            (KnowledgeDocument.id == document_id) &
            ((KnowledgeDocument.organization_id == organization_id) | (KnowledgeDocument.is_standard == True))
        ).first()
        if not doc:
            raise ValueError(f"Document {document_id} not found.")

        chunks = DocumentChunk.query.filter_by(document_id=doc.id).order_by(DocumentChunk.chunk_index.asc()).all()
        data = doc.to_dict()
        data["chunks"] = [c.to_dict() for c in chunks]
        return data

    @classmethod
    def test_retrieval(
        cls,
        organization_id: str,
        query: str,
        machine_type: Optional[str] = None,
        component_type: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Tests vector similarity retrieval with security filters."""
        if not query:
            raise ValueError("query is required.")
        return TechnicalKnowledgeStore.similarity_search(
            organization_id=organization_id,
            query=query,
            machine_type=machine_type,
            component_type=component_type,
            top_k=top_k,
        )

