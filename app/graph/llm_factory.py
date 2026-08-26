"""
Ridge: Multi-Provider LLM Factory
=================================
Unified initialization layer for Google Gemini and Groq.
Supports multi-tier workload routing:
- Fast / Intermediate reasoning (Decomposition, Grading, Rewriting, Hallucination Audit, Ingestion) -> Gemini 3.5 Flash Lite (15 RPM Tier)
- Grounded Final Synthesis -> Gemini 3.7 Flash / 3.6 Flash (5 RPM Tier) with auto-failover to Gemini 3.5 Flash Lite on 429 rate limit.
"""
from __future__ import annotations

import os
import logging
from typing import Optional, List
from langchain_core.language_models.chat_models import BaseChatModel

logger = logging.getLogger(__name__)


def get_llm_provider() -> str:
    """Detects active LLM provider from settings or environment variables."""
    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    if provider:
        return provider

    # Auto-detection based on configured keys
    if os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"):
        return "gemini"
    if os.getenv("GROQ_API_KEY"):
        return "groq"
    return "gemini"


def create_llm(
    model_name: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: Optional[int] = 800,
    tags: Optional[List[str]] = None,
    is_fast_model: bool = False,
    api_key: Optional[str] = None,
) -> BaseChatModel:
    """
    Instantiates a BaseChatModel compatible LLM based on provider configuration.
    Supports Google Gemini (ChatGoogleGenerativeAI) and Groq (ChatGroq).
    Routes high-frequency calls to the 15 RPM model and final synthesis to the 5 RPM model
    with automatic 429 rate-limit failover.
    """
    provider = get_llm_provider()
    google_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    groq_key = api_key or os.getenv("GROQ_API_KEY")

    if provider in ["gemini", "google"]:
        # If Gemini requested but no Google key set and Groq key is present, fallback gracefully
        if not google_key and groq_key:
            logger.info("[LLM Factory] GOOGLE_API_KEY not set; auto-falling back to configured Groq key")
            from langchain_groq import ChatGroq
            default_model = (
                os.getenv("GROQ_FAST_MODEL", "openai/gpt-oss-20b")
                if is_fast_model
                else os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
            )
            return ChatGroq(
                api_key=groq_key,
                model_name=model_name or default_model,
                temperature=temperature,
                max_tokens=max_tokens,
                max_retries=2,
                tags=tags or [],
            )

        from langchain_google_genai import ChatGoogleGenerativeAI

        effective_key = google_key or "AIzaSyDummyKeyForTestingPurposesOnly12345"
        fast_model_name = os.getenv("GEMINI_FAST_MODEL", "gemini-3.5-flash-lite")
        gen_model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

        if is_fast_model:
            # High-frequency operational tier (15 RPM tier)
            selected_model = model_name or fast_model_name
            logger.info(f"[LLM Factory] Fast Tier (15 RPM): Initializing {selected_model}")
            return ChatGoogleGenerativeAI(
                model=selected_model,
                google_api_key=effective_key,
                temperature=temperature,
                max_output_tokens=max_tokens or 1000,
                max_retries=2,
                timeout=15,
                tags=tags or [],
            )

        # High-reasoning generation tier (5 RPM tier) with automatic failover to 15 RPM tier
        selected_model = model_name or gen_model_name
        logger.info(f"[LLM Factory] Generation Tier (5 RPM with 15 RPM Failover): Initializing {selected_model}")
        
        primary_llm = ChatGoogleGenerativeAI(
            model=selected_model,
            google_api_key=effective_key,
            temperature=temperature,
            max_output_tokens=max_tokens or 1200,
            max_retries=1,
            timeout=15,
            tags=tags or [],
        )

        # Resilient failover model on 429 RateLimit, timeout, or service spike
        failover_llm = ChatGoogleGenerativeAI(
            model=fast_model_name,
            google_api_key=effective_key,
            temperature=temperature,
            max_output_tokens=max_tokens or 1000,
            max_retries=2,
            timeout=15,
            tags=(tags or []) + ["rate_limit_failover_15rpm"],
        )

        return primary_llm.with_fallbacks([failover_llm])

    # Default to Groq
    from langchain_groq import ChatGroq
    default_model = (
        os.getenv("GROQ_FAST_MODEL", "openai/gpt-oss-20b")
        if is_fast_model
        else os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    )
    selected_model = model_name or default_model

    logger.info(f"[LLM Factory] Initializing Groq model: {selected_model}")
    return ChatGroq(
        api_key=groq_key or "gsk_dummy_for_testing",
        model_name=selected_model,
        temperature=temperature,
        max_tokens=max_tokens,
        max_retries=2,
        tags=tags or [],
    )
