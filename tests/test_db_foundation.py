"""
Tests for Phase 1 & 2: Database Schema, Models, and Repositories
"""
import uuid
import pytest
from app.db.database import get_db_session
from app.db.repositories import (
    user_repo,
    conversation_repo,
    document_repo,
    glossary_repo,
    cache_repo,
)


@pytest.mark.asyncio
async def test_user_and_usage_crud():
    async with get_db_session() as session:
        test_username = f"testuser_{uuid.uuid4().hex[:6]}"
        user = await user_repo.create_user(
            session=session,
            username=test_username,
            email=f"{test_username}@test.com",
            password="SecurePassword123!",
            name="Test Climber",
        )
        assert user.id is not None
        assert user.username == test_username

        # Verify credentials
        verified = await user_repo.verify_user_credentials(
            session=session,
            identifier=test_username,
            password="SecurePassword123!",
        )
        assert verified is not None
        assert verified.id == user.id

        # Verify daily usage quota
        allowed, count, limit = await user_repo.check_and_increment_usage(
            session=session,
            user_id=user.id,
        )
        assert allowed is True
        assert count == 1
        assert limit == 50


@pytest.mark.asyncio
async def test_conversation_and_message_crud():
    async with get_db_session() as session:
        user = await user_repo.create_user(
            session=session,
            username=f"conv_user_{uuid.uuid4().hex[:6]}",
            email=f"conv_{uuid.uuid4().hex[:6]}@test.com",
            password="SecurePassword123!",
            name="Conv User",
        )

        # 1. Create conversation
        conv = await conversation_repo.create_conversation(
            session=session,
            user_id=user.id,
            title="Research on Corrective RAG",
        )
        assert conv.id is not None
        assert conv.title == "Research on Corrective RAG"

        # 2. Add user message
        msg1 = await conversation_repo.add_message(
            session=session,
            conversation_id=str(conv.id),
            role="user",
            content="Explain task decomposition in LLMs",
        )
        assert msg1.id is not None

        # 3. Add assistant message with citation
        msg2 = await conversation_repo.add_message(
            session=session,
            conversation_id=str(conv.id),
            role="assistant",
            content="Task decomposition breaks complex tasks into smaller steps.",
            metadata_json={"confidence": {"score": 95, "level": "HIGH"}},
        )
        assert msg2.id is not None

        citation = await conversation_repo.add_citation(
            session=session,
            message_id=msg2.id,
            citation_index=1,
            relevance_score=0.92,
            quoted_text="Task decomposition can be achieved by LLM with Chain of Thought.",
        )
        assert citation.id is not None

        # 4. Fetch messages
        messages = await conversation_repo.get_conversation_messages(
            session=session,
            conversation_id=str(conv.id),
            user_id=user.id,
        )
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert len(messages[1]["citations"]) == 1


@pytest.mark.asyncio
async def test_query_cache_pgvector():
    async with get_db_session() as session:
        # Create a mock 1024-dim vector
        mock_vec = [0.05] * 1024

        # Store cache
        await cache_repo.store_cached_response(
            session=session,
            question="What is CRAG in LangGraph?",
            answer="Corrective RAG adds evaluators and self-correction to standard RAG.",
            confidence={"score": 98, "level": "HIGH"},
            conflict_data={"detected": False},
            query_vector=mock_vec,
        )

        # Lookup with exact match
        hit = await cache_repo.get_cached_response(
            session=session,
            query="What is CRAG in LangGraph?",
            query_vector=mock_vec,
            threshold=0.95,
        )
        assert hit is not None
        assert hit["cache_hit"] is True
        assert hit["similarity"] >= 0.99
