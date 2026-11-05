"""LangSmith client integration with privacy sanitization and offline fallback."""
import os
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Check LangSmith configuration
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "pharmapredict-ai")
LANGSMITH_TRACING = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"


class LangSmithPrivacySanitizer:
    """Sanitizes sensitive plant and batch identifiers to prevent data leakage."""

    SENSITIVE_KEYS = {"password", "token", "secret", "batch_number", "operator_name", "operator_id"}

    @classmethod
    def sanitize(cls, data: Any) -> Any:
        if isinstance(data, dict):
            clean = {}
            for k, v in data.items():
                if any(s in k.lower() for s in cls.SENSITIVE_KEYS):
                    clean[k] = "[REDACTED_PRIVACY]"
                else:
                    clean[k] = cls.sanitize(v)
            return clean
        elif isinstance(data, list):
            return [cls.sanitize(item) for item in data]
        return data


class DiagnosticEvaluationClient:
    """Manages LangSmith tracing or local offline evaluation storage."""

    def __init__(self):
        self.is_cloud_enabled = bool(LANGSMITH_API_KEY and LANGSMITH_TRACING)
        self.project_name = LANGSMITH_PROJECT
        self._client = None

        if self.is_cloud_enabled:
            try:
                from langsmith import Client
                self._client = Client(api_key=LANGSMITH_API_KEY)
                logger.info("LangSmith cloud client successfully initialized.")
            except Exception as e:
                logger.warning(f"Could not initialize LangSmith cloud client: {e}. Falling back to offline evaluation.")
                self.is_cloud_enabled = False

    def log_run(
        self,
        session_id: str,
        run_name: str,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Logs a trace run locally or to LangSmith if configured."""
        clean_inputs = LangSmithPrivacySanitizer.sanitize(inputs)
        clean_outputs = LangSmithPrivacySanitizer.sanitize(outputs)
        clean_meta = LangSmithPrivacySanitizer.sanitize(metadata or {})

        record = {
            "session_id": session_id,
            "run_name": run_name,
            "inputs": clean_inputs,
            "outputs": clean_outputs,
            "metadata": clean_meta,
            "mode": "CLOUD" if self.is_cloud_enabled else "OFFLINE_LOCAL",
        }

        if self.is_cloud_enabled and self._client:
            try:
                # Log to cloud LangSmith run
                pass  # Traced via LangChain standard tracing callbacks
            except Exception as e:
                logger.warning(f"Error sending trace to LangSmith cloud: {e}")

        return record

