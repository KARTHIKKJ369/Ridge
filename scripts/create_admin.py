#!/usr/bin/env python3
"""
Ridge: Admin User Creation & Management Utility (PostgreSQL)
============================================================
Creates or updates an administrator account directly in PostgreSQL.

Usage:
  python scripts/create_admin.py --username admin --password "Kichu@5120"
  python scripts/create_admin.py --username admin --password "Kichu@5120" --email "admin@ridge.ai"
"""

import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import hashlib
import secrets
import argparse

from sqlalchemy import text
from app.db.database import get_sync_session, is_postgres_configured
from app.db.repositories.user_repo import DEFAULT_TENANT_ID



def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    ).hex()


def create_or_update_admin(
    username: str = "admin",
    password: str = "Kichu@5120",
    email: str = "admin@ridge.ai",
    name: str = "Ridge Administrator",
    role: str = "admin",
):
    salt = secrets.token_hex(16)
    pw_hash = hash_password(password, salt)
    uname = username.strip().lower()
    em = email.strip().lower()

    try:
        with get_sync_session() as session:
            # Check for existing user by username or email
            existing = session.execute(
                text("SELECT id, username, email FROM users WHERE username = :uname OR email = :email"),
                {"uname": uname, "email": em}
            ).first()

            if existing:
                user_id = existing[0]
                session.execute(
                    text("""
                        UPDATE users
                        SET username = :uname, email = :email, name = :name, password_hash = :hash, salt = :salt, role = :role, is_active = true, daily_request_limit = 999999
                        WHERE id = :uid
                    """),
                    {"uname": uname, "email": em, "name": name, "hash": pw_hash, "salt": salt, "role": role, "uid": user_id}
                )
                session.commit()
                print(f"✅ Successfully updated user '{username}' (ID: {user_id}) to role '{role}' with new password in PostgreSQL!")
            else:
                user_id = f"usr_{secrets.token_hex(8)}"
                session.execute(
                    text("""
                        INSERT INTO users (id, tenant_id, username, email, name, password_hash, salt, role, is_active, daily_request_limit)
                        VALUES (:uid, :tid, :uname, :email, :name, :hash, :salt, :role, true, 999999)
                    """),
                    {"uid": user_id, "tid": DEFAULT_TENANT_ID, "uname": uname, "email": em, "name": name, "hash": pw_hash, "salt": salt, "role": role}
                )
                session.commit()
                print(f"✅ Successfully created new admin account in PostgreSQL:")
                print(f"   ID:       {user_id}")
                print(f"   Username: {username}")
                print(f"   Email:    {email}")
                print(f"   Role:     {role}")
    except Exception as e:
        print(f"❌ Error creating/updating admin user: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Create or update an admin user in Ridge PostgreSQL database.")
    parser.add_argument("--username", default="admin", help="Admin username (default: admin)")
    parser.add_argument("--password", default="Kichu@5120", help="Admin password (default: Kichu@5120)")
    parser.add_argument("--email", default="admin@ridge.ai", help="Admin email (default: admin@ridge.ai)")
    parser.add_argument("--name", default="Ridge Administrator", help="Display name")
    parser.add_argument("--role", default="admin", choices=["admin", "user"], help="User role")

    args = parser.parse_args()
    create_or_update_admin(
        username=args.username,
        password=args.password,
        email=args.email,
        name=args.name,
        role=args.role,
    )


if __name__ == "__main__":
    main()

