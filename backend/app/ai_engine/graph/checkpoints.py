"""Checkpoint management for durable LangGraph state retention and session recovery."""
import logging
from typing import Optional, Dict, Any
from langgraph.checkpoint.memory import MemorySaver
from app.extensions import db
from app.models.diagnostic import DiagnosticSession, AgentExecution

logger = logging.getLogger(__name__)

# Global singleton memory checkpointer for active threads
_memory_saver: Optional[MemorySaver] = None


def get_memory_saver() -> MemorySaver:
    """Returns the process-level MemorySaver checkpointer."""
    global _memory_saver
    if _memory_saver is None:
        _memory_saver = MemorySaver()
    return _memory_saver


def persist_diagnostic_checkpoint(state_dict: Dict[str, Any], session_id: str, stage_name: str) -> None:
    """Persists intermediate state snapshot into the PostgreSQL database for audit trail compliance."""
    try:
        session = DiagnosticSession.query.filter_by(id=session_id).first()
        if session:
            session.current_stage = stage_name
            # Preserve state checkpoint in session metadata
            meta = session.session_metadata or {}
            checkpoints = meta.get("checkpoints", [])
            checkpoints.append({
                "stage": stage_name,
                "timestamp": state_dict.get("report", {}).get("generated_at") if state_dict.get("report") else None,
                "errors": state_dict.get("agent_errors", []),
            })
            meta["checkpoints"] = checkpoints[-20:]  # Keep last 20 checkpoints
            session.session_metadata = meta
            db.session.commit()
    except Exception as e:
        logger.warning(f"Failed to persist state checkpoint for session {session_id}: {e}")
        try:
            db.session.rollback()
        except Exception:
            pass

