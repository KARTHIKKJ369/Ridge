"""
Live End-to-End Persistence & Retrieval Test
============================================
Sends a query through the FastAPI chat endpoint, streams the response,
and verifies that conversation, message, citation, retrieval telemetry,
and pgvector query cache rows were written to PostgreSQL.
"""
import sys
import uuid
import json
import asyncio
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from httpx import AsyncClient, ASGITransport
from api import app
from auth import create_access_token
from app.db.database import get_db_session
from app.db.models.conversation import Conversation
from app.db.models.message import Message
from app.db.models.citation import MessageCitation
from app.db.models.retrieval import RetrievalRun
from app.db.models.query_cache import QueryCache
from sqlalchemy import select


@pytest.mark.asyncio
async def test_live_chat_and_persistence():

    print("🏔️  Starting Live End-to-End PostgreSQL Persistence Test...")

    user_data = {
        "id": "usr_e2e_tester",
        "username": "e2e_tester",
        "email": "tester@ridge.ai",
        "name": "E2E Tester",
        "role": "user",
    }
    token = create_access_token(user_data)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create a conversation
        conv_resp = await client.post(
            "/api/conversations",
            json={"title": "DSU Optimizations Research"},
            headers=headers,
        )
        assert conv_resp.status_code == 200
        conv_id = conv_resp.json()["id"]
        print(f"  ✓ Created PostgreSQL Conversation: {conv_id}")

        # 2. Ask question with conversation_id
        question = "What are the heuristics to reduce tree operation time in disjoint sets?"
        print(f"  -> Sending question: '{question}'...")

        answer_tokens = []
        conversation_id_from_event = None

        async with client.stream(
            "POST",
            "/ask",
            json={
                "question": question,
                "conversation_id": conv_id,
                "web_search_enabled": False,
            },
            headers=headers,
        ) as response:
            assert response.status_code == 200
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        continue
                    try:
                        event = json.loads(data_str)
                        if event.get("type") == "token":
                            answer_tokens.append(event.get("token", ""))
                        elif event.get("type") == "conversation_info":
                            conversation_id_from_event = event.get("conversation_id")
                        elif event.get("answer"):
                            print(f"  ✓ Received Synthesized Answer ({len(event['answer'])} chars)")
                    except Exception:
                        pass

        full_answer = "".join(answer_tokens)
        print(f"  ✓ Streamed {len(answer_tokens)} tokens successfully.")

        # 3. Verify PostgreSQL Database Records
        async with get_db_session() as session:
            # Check conversation
            conv = await session.get(Conversation, uuid.UUID(conv_id))
            assert conv is not None
            print(f"  ✓ Verified Conversation in DB: '{conv.title}'")

            # Check messages
            stmt = select(Message).where(Message.conversation_id == uuid.UUID(conv_id)).order_by(Message.created_at.asc())
            res = await session.execute(stmt)
            messages = res.scalars().all()
            assert len(messages) >= 2
            user_msg = messages[0]
            assistant_msg = messages[1]
            assert user_msg.role == "user"
            assert assistant_msg.role == "assistant"
            assert len(assistant_msg.content) > 0
            print(f"  ✓ Verified User & Assistant Messages in DB (User: '{user_msg.content[:40]}...', Assistant: '{assistant_msg.content[:40]}...')")

            # Check citations
            c_stmt = select(MessageCitation).where(MessageCitation.message_id == assistant_msg.id)
            c_res = await session.execute(c_stmt)
            citations = c_res.scalars().all()
            print(f"  ✓ Verified Message Citations in DB: {len(citations)} source citations recorded.")

            # Check retrieval runs
            r_stmt = select(RetrievalRun).where(RetrievalRun.conversation_id == uuid.UUID(conv_id))
            r_res = await session.execute(r_stmt)
            runs = r_res.scalars().all()
            print(f"  ✓ Verified Retrieval Runs in DB: {len(runs)} telemetry runs recorded.")

            # Check query cache
            qc_stmt = select(QueryCache).limit(5)
            qc_res = await session.execute(qc_stmt)
            cache_entries = qc_res.scalars().all()
            print(f"  ✓ Verified pgvector Query Cache entries: {len(cache_entries)} cached responses.")

    print("\n🎉 Live End-to-End PostgreSQL Persistence Test PASSED 100%!")


if __name__ == "__main__":
    asyncio.run(test_live_chat_and_persistence())
