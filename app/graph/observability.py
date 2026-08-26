"""
Ridge: Observability & Tracing Engine (Langfuse)
================================================
Provides zero-overhead LLM trace instrumentation, latency breakdowns,
and token accounting via Langfuse.
"""
import os
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)

_langfuse_handler = None
_langfuse_client = None
_langfuse_initialized = False


def get_langfuse_handler() -> Optional[Any]:
    """
    Returns a cached Langfuse CallbackHandler instance if environment credentials exist.
    Returns None gracefully if Langfuse is unconfigured or not installed.
    """
    global _langfuse_handler, _langfuse_initialized, _langfuse_client
    if _langfuse_initialized:
        return _langfuse_handler

    _langfuse_initialized = True
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com").strip()

    if not public_key or not secret_key:
        logger.debug("Langfuse tracing disabled: LANGFUSE_PUBLIC_KEY or LANGFUSE_SECRET_KEY not set.")
        return None

    # Export to environment for standard SDK discovery
    os.environ["LANGFUSE_PUBLIC_KEY"] = public_key
    os.environ["LANGFUSE_SECRET_KEY"] = secret_key
    os.environ["LANGFUSE_HOST"] = host

    try:
        # Langfuse v3 / v4 integration
        try:
            from langfuse.langchain import CallbackHandler
            _langfuse_handler = CallbackHandler()
            logger.info("✓ Langfuse observability callback initialized successfully.")
        except (ImportError, TypeError):
            # Langfuse v2 legacy callback handler
            from langfuse.callback import CallbackHandler
            _langfuse_handler = CallbackHandler(
                public_key=public_key,
                secret_key=secret_key,
                host=host,
            )
            logger.info("✓ Langfuse v2 callback initialized successfully.")
    except Exception as e:
        logger.warning(f"Langfuse callback initialization note: {e}")
        _langfuse_handler = None

    return _langfuse_handler


def flush_langfuse() -> None:
    """Flushes any queued Langfuse traces/spans to ensure immediate cloud ingestion."""
    global _langfuse_handler
    if not _langfuse_handler:
        return
    try:
        if hasattr(_langfuse_handler, "flush"):
            _langfuse_handler.flush()
        elif hasattr(_langfuse_handler, "langfuse") and hasattr(_langfuse_handler.langfuse, "flush"):
            _langfuse_handler.langfuse.flush()
    except Exception as e:
        logger.debug(f"Langfuse flush note: {e}")

