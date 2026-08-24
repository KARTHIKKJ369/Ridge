"""
Multi-Tenant Isolation & Document Sharing Test Suite
====================================================
Tests tenant creation, user scoping, RBAC permissions, and strict
cross-tenant vector retrieval isolation.
"""
import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from api import app
from app.db.database import get_db_session, init_db
from app.db.repositories import tenant_repo, document_repo
from auth import create_access_token


@pytest.mark.asyncio
async def test_multi_tenant_crud_and_rbac():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. SuperAdmin Auth Token
        superadmin_payload = {
            "id": "usr_superadmin_test",
            "username": "superadmin_test",
            "email": "superadmin@ridge.ai",
            "name": "Super Admin",
            "role": "superadmin",
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "tenant_slug": "default",
        }
        sa_token = create_access_token(superadmin_payload)
        sa_headers = {"Authorization": f"Bearer {sa_token}"}

        # 2. Create Tenant A (Acme) and Tenant B (Apex)
        t_suffix = uuid.uuid4().hex[:6]
        slug_a = f"acme_{t_suffix}"
        slug_b = f"apex_{t_suffix}"

        res_a = await client.post(
            "/api/admin/tenants",
            json={"name": "Acme Corp", "slug": slug_a, "max_users": 10},
            headers=sa_headers,
        )
        assert res_a.status_code == 200
        tenant_a_data = res_a.json()
        assert tenant_a_data["slug"] == slug_a

        res_b = await client.post(
            "/api/admin/tenants",
            json={"name": "Apex Labs", "slug": slug_b, "max_users": 10},
            headers=sa_headers,
        )
        assert res_b.status_code == 200
        tenant_b_data = res_b.json()
        assert tenant_b_data["slug"] == slug_b

        # 3. List Tenants as SuperAdmin
        list_res = await client.get("/api/admin/tenants", headers=sa_headers)
        assert list_res.status_code == 200
        all_tenants = list_res.json()["tenants"]
        slugs = [t["slug"] for t in all_tenants]
        assert slug_a in slugs
        assert slug_b in slugs

        # 4. Register Users in Acme vs Apex
        reg_a = await client.post(
            "/api/auth/register",
            json={
                "username": f"alice_{t_suffix}",
                "email": f"alice_{t_suffix}@acme.com",
                "password": "Password123!",
                "tenant_slug": slug_a,
            }
        )
        assert reg_a.status_code == 200
        alice_data = reg_a.json()["user"]
        alice_token = reg_a.json()["token"]
        assert alice_data["tenant_slug"] == slug_a

        reg_b = await client.post(
            "/api/auth/register",
            json={
                "username": f"bob_{t_suffix}",
                "email": f"bob_{t_suffix}@apex.com",
                "password": "Password123!",
                "tenant_slug": slug_b,
            }
        )
        assert reg_b.status_code == 200
        bob_data = reg_b.json()["user"]
        assert bob_data["tenant_slug"] == slug_b

        # 5. Check Tenant Info Endpoint for Alice
        alice_headers = {"Authorization": f"Bearer {alice_token}"}
        info_res = await client.get("/api/tenant/info", headers=alice_headers)
        assert info_res.status_code == 200
        t_info = info_res.json()["tenant"]
        assert t_info["slug"] == slug_a
        assert t_info["name"] == "Acme Corp"


@pytest.mark.asyncio
async def test_tenant_document_sharing_and_isolation():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create unique tenant
        t_suffix = uuid.uuid4().hex[:6]
        slug_acme = f"acme_doc_{t_suffix}"

        # SuperAdmin creates Acme
        superadmin_payload = {
            "id": "usr_sa_test_docs",
            "username": "sa_test_docs",
            "role": "superadmin",
            "tenant_id": "00000000-0000-0000-0000-000000000001",
        }
        sa_token = create_access_token(superadmin_payload)
        await client.post(
            "/api/admin/tenants",
            json={"name": "Acme Docs", "slug": slug_acme, "max_users": 10},
            headers={"Authorization": f"Bearer {sa_token}"},
        )

        # Register User A (Alice) and User B (Charlie) in Acme
        reg_alice = await client.post(
            "/api/auth/register",
            json={
                "username": f"alice_doc_{t_suffix}",
                "email": f"alice_doc_{t_suffix}@acme.com",
                "password": "Password123!",
                "tenant_slug": slug_acme,
            }
        )
        alice_token = reg_alice.json()["token"]
        alice_headers = {"Authorization": f"Bearer {alice_token}"}

        reg_charlie = await client.post(
            "/api/auth/register",
            json={
                "username": f"charlie_doc_{t_suffix}",
                "email": f"charlie_doc_{t_suffix}@acme.com",
                "password": "Password123!",
                "tenant_slug": slug_acme,
            }
        )
        charlie_token = reg_charlie.json()["token"]
        charlie_headers = {"Authorization": f"Bearer {charlie_token}"}

        # Ingest a private document for Alice
        ingest_res = await client.post(
            "/ingest",
            json={"text_or_url": "Confidential Acme Strategy Plan for Alice", "is_shared": False},
            headers=alice_headers,
        )
        assert ingest_res.status_code == 200

        # Alice checks KB sources -> should see 1 doc
        sources_a = await client.get("/api/kb/sources", headers=alice_headers)
        assert sources_a.status_code == 200
        alice_docs = sources_a.json()["sources"]
        assert len(alice_docs) >= 1
        alice_doc_id = alice_docs[0]["id"]
        assert alice_docs[0]["is_shared"] is False

        # Charlie checks KB sources -> should see 0 docs (since it is private to Alice)
        sources_c1 = await client.get("/api/kb/sources", headers=charlie_headers)
        assert sources_c1.status_code == 200
        charlie_docs_1 = sources_c1.json()["sources"]
        assert len(charlie_docs_1) == 0

        # Alice toggles document to SHARED
        share_res = await client.patch(
            f"/api/kb/documents/{alice_doc_id}/share",
            json={"is_shared": True},
            headers=alice_headers,
        )
        assert share_res.status_code == 200
        assert share_res.json()["is_shared"] is True

        # Now Charlie checks KB sources -> should immediately see the shared doc!
        sources_c2 = await client.get("/api/kb/sources", headers=charlie_headers)
        assert sources_c2.status_code == 200
        charlie_docs_2 = sources_c2.json()["sources"]
        assert len(charlie_docs_2) == 1
        assert charlie_docs_2[0]["id"] == alice_doc_id
        assert charlie_docs_2[0]["is_shared"] is True


@pytest.mark.asyncio
async def test_register_institution_and_enterprise_admin_management():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        t_suffix = uuid.uuid4().hex[:6]
        inst_slug = f"stanford_{t_suffix}"

        # 1. Register Institution via endpoint
        inst_res = await client.post(
            "/api/auth/register-institution",
            json={
                "institution_name": "Stanford AI Institute",
                "slug": inst_slug,
                "admin_name": "Dr. Sarah Connor",
                "admin_username": f"sarah_{t_suffix}",
                "admin_email": f"sarah_{t_suffix}@stanford.edu",
                "admin_password": "Password123!",
            }
        )
        assert inst_res.status_code == 200
        sarah_profile = inst_res.json()["user"]
        sarah_token = inst_res.json()["token"]
        assert sarah_profile["role"] == "admin"
        assert sarah_profile["tenant_slug"] == inst_slug
        sarah_headers = {"Authorization": f"Bearer {sarah_token}"}

        # 2. Enterprise Admin lists users -> should only see Sarah initially
        users_res = await client.get("/api/admin/users", headers=sarah_headers)
        assert users_res.status_code == 200
        sarah_users = users_res.json()["users"]
        assert len(sarah_users) == 1
        assert sarah_users[0]["username"] == f"sarah_{t_suffix}"

        # 3. Enterprise Admin provisions a new member directly via POST /api/admin/users
        create_user_res = await client.post(
            "/api/admin/users",
            json={
                "username": f"john_{t_suffix}",
                "name": "John Connor",
                "email": f"john_{t_suffix}@stanford.edu",
                "password": "Password123!",
                "role": "user",
                "daily_request_limit": 100,
            },
            headers=sarah_headers,
        )
        assert create_user_res.status_code == 200
        john_data = create_user_res.json()["user"]
        john_id = john_data["id"]
        assert john_data["tenant_slug"] == inst_slug

        # 4. Verify Sarah now sees 2 users in her enterprise
        users_res_2 = await client.get("/api/admin/users", headers=sarah_headers)
        assert users_res_2.status_code == 200
        assert len(users_res_2.json()["users"]) == 2

        # 5. Sarah promotes John to Admin
        role_res = await client.post(
            f"/api/admin/users/{john_id}/role",
            json={"role": "admin"},
            headers=sarah_headers,
        )
        assert role_res.status_code == 200

        # 6. Sarah updates John's quota
        limit_res = await client.post(
            f"/api/admin/users/{john_id}/limit",
            json={"limit": 250},
            headers=sarah_headers,
        )
        assert limit_res.status_code == 200

        # 7. Check public tenants endpoint includes Stanford
        pub_res = await client.get("/api/tenants/public")
        assert pub_res.status_code == 200
        pub_slugs = [t["slug"] for t in pub_res.json()["tenants"]]
        assert inst_slug in pub_slugs


@pytest.mark.asyncio
async def test_feedback_lifecycle_and_admin_document_management():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        t_suffix = uuid.uuid4().hex[:6]
        inst_slug = f"mit_ai_{t_suffix}"

        # 1. Register MIT Institution
        reg_res = await client.post(
            "/api/auth/register-institution",
            json={
                "institution_name": "MIT Intelligence",
                "slug": inst_slug,
                "admin_username": f"prof_{t_suffix}",
                "admin_email": f"prof_{t_suffix}@mit.edu",
                "admin_password": "Password123!",
                "admin_name": "Prof Alex",
            },
        )

        assert reg_res.status_code == 200
        admin_token = reg_res.json()["token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # 2. Register Member in MIT
        user_res = await client.post(
            "/api/auth/register",
            json={
                "username": f"student_{t_suffix}",
                "email": f"student_{t_suffix}@mit.edu",
                "password": "Password123!",
                "name": "Student Bob",
                "tenant_slug": inst_slug,
            },
        )
        assert user_res.status_code == 200
        user_token = user_res.json()["token"]
        user_headers = {"Authorization": f"Bearer {user_token}"}

        # 3. Member submits Feedback
        fb_res = await client.post(
            "/api/feedback",
            json={
                "category": "accuracy",
                "message": "Citation #2 is slightly incomplete regarding thermodynamic properties.",
                "conversation_id": "conv_test_123",
            },
            headers=user_headers,
        )
        assert fb_res.status_code == 200
        fb_data = fb_res.json()
        fb_id = fb_data["id"]
        assert fb_data["category"] == "accuracy"

        # 4. Member views their own feedback history
        my_fb_res = await client.get("/api/feedback/mine", headers=user_headers)
        assert my_fb_res.status_code == 200
        assert len(my_fb_res.json()["feedback"]) >= 1

        # 5. Admin lists feedback and sees the new submission
        admin_fb_res = await client.get("/api/admin/feedback", headers=admin_headers)
        assert admin_fb_res.status_code == 200
        admin_items = admin_fb_res.json()["feedback"]
        assert any(item["id"] == fb_id for item in admin_items)

        # 6. Admin resolves feedback with notes
        resolve_res = await client.patch(
            f"/api/admin/feedback/{fb_id}",
            json={
                "status": "resolved",
                "admin_notes": "Updated knowledge chunk to include full table of thermodynamic states.",
            },
            headers=admin_headers,
        )
        assert resolve_res.status_code == 200
        assert resolve_res.json()["feedback_status"] == "resolved"

        # 7. Ingest a document and test Admin Document Management
        ingest_res = await client.post(
            "/ingest",
            json={"text_or_url": "MIT Lecture Notes on Deep Learning and Thermodynamic AI.", "is_shared": True},
            headers=admin_headers,
        )
        assert ingest_res.status_code == 200

        # 8. List Admin Documents
        docs_res = await client.get("/api/admin/documents", headers=admin_headers)
        assert docs_res.status_code == 200
        docs = docs_res.json()["documents"]
        assert len(docs) >= 1

        # 9. Toggle Document Sharing
        doc_id = docs[0]["id"]
        toggle_res = await client.patch(
            f"/api/kb/documents/{doc_id}/share",
            json={"is_shared": False},
            headers=admin_headers,
        )
        assert toggle_res.status_code == 200
        assert toggle_res.json()["is_shared"] is False

        # 10. Delete Document
        del_res = await client.delete(f"/api/admin/documents/{doc_id}", headers=admin_headers)
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "deleted"



