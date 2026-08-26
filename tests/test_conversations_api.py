"""
Tests for Conversation Persistence Endpoints with AsyncClient
"""
import pytest
from httpx import AsyncClient, ASGITransport
from api import app
from auth import create_access_token


@pytest.fixture
def auth_headers():
    user_data = {
        "id": "usr_test_climber",
        "username": "test_climber",
        "email": "climber@ridge.ai",
        "name": "Test Climber",
        "role": "user",
    }
    token = create_access_token(user_data)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_conversation_lifecycle_api(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create a conversation
        resp = await client.post(
            "/api/conversations",
            json={"title": "Test Research Ascent"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        conv_id = data["id"]
        assert data["title"] == "Test Research Ascent"

        # 2. List conversations
        list_resp = await client.get("/api/conversations", headers=auth_headers)
        assert list_resp.status_code == 200
        convs = list_resp.json().get("conversations", [])
        assert any(c["id"] == conv_id for c in convs)

        # 3. Get conversation detail
        detail_resp = await client.get(f"/api/conversations/{conv_id}", headers=auth_headers)
        assert detail_resp.status_code == 200
        assert detail_resp.json()["title"] == "Test Research Ascent"

        # 4. Patch conversation title
        patch_resp = await client.patch(
            f"/api/conversations/{conv_id}",
            json={"title": "Renamed Research Ascent"},
            headers=auth_headers,
        )
        assert patch_resp.status_code == 200

        # 5. Fetch messages (should be empty initially)
        msgs_resp = await client.get(f"/api/conversations/{conv_id}/messages", headers=auth_headers)
        assert msgs_resp.status_code == 200
        assert msgs_resp.json()["messages"] == []

        # 6. Delete conversation
        del_resp = await client.delete(f"/api/conversations/{conv_id}", headers=auth_headers)
        assert del_resp.status_code == 200


@pytest.mark.asyncio
async def test_document_content_preview_api(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Ingest a test document
        ingest_res = await client.post(
            "/ingest",
            json={"text_or_url": "Deep Learning Architecture for Ridge RAG State Machines.", "is_shared": True},
            headers=auth_headers,
        )
        assert ingest_res.status_code == 200

        # Query document content
        content_res = await client.get(
            "/api/v1/documents/content?source=Deep Learning Architecture for Ridge RAG State Machines.",
            headers=auth_headers,
        )
        assert content_res.status_code == 200
        data = content_res.json()
        assert "full_text" in data
        assert "chunks" in data
        assert "Deep Learning" in data["full_text"]


@pytest.mark.asyncio
async def test_websocket_chat_ping():
    from starlette.testclient import TestClient
    with TestClient(app) as client:
        with client.websocket_connect("/ws/chat") as websocket:
            websocket.send_json({"action": "ping"})
            data = websocket.receive_json()
            assert data == {"type": "pong"}
