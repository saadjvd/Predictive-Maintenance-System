from typing import List, Dict, Any, Optional
from app.ai_engine.rag.vector_store import TechnicalKnowledgeStore
from app.ai_engine.schemas.diagnostic_state import RetrievedEvidenceItem


class TechnicalRetriever:
    """RAG interface for Root Cause Analysis Agent."""

    @classmethod
    def retrieve_relevant_knowledge(
        cls,
        organization_id: str,
        machine_name: str,
        category_id: Optional[str],
        observed_symptoms: List[str],
        top_k: int = 4,
    ) -> List[RetrievedEvidenceItem]:
        """
        Retrieves technical excerpts for symptoms and machine context.
        """
        query_text = f"{machine_name} " + " ".join(observed_symptoms)
        raw_results = TechnicalKnowledgeStore.similarity_search(
            organization_id=organization_id,
            query=query_text,
            category_id=category_id,
            top_k=top_k,
        )

        items = []
        for r in raw_results:
            items.append(
                RetrievedEvidenceItem(
                    document_id=r["document_id"],
                    title=r["title"],
                    document_type=r["document_type"],
                    section=r["section"],
                    page_number=r["page_number"],
                    content_excerpt=r["content_excerpt"],
                    relevance_score=r["relevance_score"],
                    source_filename=r["source_filename"],
                )
            )
        return items

