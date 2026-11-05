from typing import List, Dict, Any, Optional
from app.ai_engine.rag.retriever import TechnicalRetriever
from app.ai_engine.schemas.diagnostic_state import RetrievedEvidenceItem


class DocumentTools:
    """RAG tool for agents to query equipment manuals, SOPs, and troubleshooting guides."""

    @classmethod
    def search_technical_documentation(
        cls,
        organization_id: str,
        machine_name: str,
        category_id: Optional[str],
        symptoms: List[str],
        top_k: int = 4,
    ) -> List[RetrievedEvidenceItem]:
        """Queries approved technical documents for matching symptoms."""
        return TechnicalRetriever.retrieve_relevant_knowledge(
            organization_id=organization_id,
            machine_name=machine_name,
            category_id=category_id,
            observed_symptoms=symptoms,
            top_k=top_k,
        )

