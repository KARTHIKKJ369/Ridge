#!/usr/bin/env python3
"""
Ridge: Admin User Creation / Password Reset Utility
===================================================
Creates or updates an administrator account in the SQLite users database.

Usage:
  python scripts/create_admin.py --username admin --password "kichu@5120"
  python scripts/create_admin.py --username admin --password "kichu@5120" --email "admin@ridge.ai"
"""

import os
import sys
import time
import sqlite3
import hashlib
import secrets
import argparse


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    ).hex()


def create_or_update_admin(
    username: str = "admin",
    password: str = "kichu@5120",
    email: str = "admin@ridge.ai",
    name: str = "Ridge Administrator",
    role: str = "admin",
    db_path: str = None,
):
    if not db_path:
        db_path = os.getenv("AUTH_DB_PATH", "./users.db")

    print(f"🔧 Target SQLite DB: {os.path.abspath(db_path)}")

    # Ensure parent directory exists
    parent_dir = os.path.dirname(os.path.abspath(db_path))
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create table if missing
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            is_active INTEGER NOT NULL DEFAULT 1,
            daily_request_limit INTEGER NOT NULL DEFAULT 50
        );
    """)

    # Check for existing user by username or email
    cursor.execute("SELECT id, username, email, role FROM users WHERE username = ? OR email = ?", (username.lower(), email.lower()))
    row = cursor.fetchone()

    salt = secrets.token_hex(16)
    pw_hash = hash_password(password, salt)
    now = int(time.time())

    if row:
        user_id = row[0]
        cursor.execute("""
            UPDATE users
            SET username = ?, email = ?, name = ?, password_hash = ?, salt = ?, role = ?, is_active = 1, daily_request_limit = 999999
            WHERE id = ?
        """, (username.lower(), email.lower(), name, pw_hash, salt, role, user_id))
        conn.commit()
        print(f"✅ Successfully updated user '{username}' (ID: {user_id}) to role '{role}' with new password!")
    else:
        user_id = f"usr_{secrets.token_hex(8)}"
        cursor.execute("""
            INSERT INTO users (id, username, email, name, password_hash, salt, created_at, role, is_active, daily_request_limit)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 999999)
        """, (user_id, username.lower(), email.lower(), name, pw_hash, salt, now, role))
        conn.commit()
        print(f"✅ Successfully created new admin account:")
        print(f"   ID:       {user_id}")
        print(f"   Username: {username}")
        print(f"   Email:    {email}")
    conn.close()

    # Sync with PostgreSQL if configured
    try:
        from app.db.database import get_db_session, is_postgres_configured
        import asyncio
        from sqlalchemy import text

        if is_postgres_configured():
            async def sync_pg():
                async with get_db_session() as s:
                    pg_check = await s.execute(text("SELECT id FROM users WHERE id = :uid OR username = :uname"), {"uid": user_id, "uname": username.lower()})
                    existing = pg_check.first()
                    if existing:
                        await s.execute(
                            text("UPDATE users SET username = :uname, email = :email, name = :name, password_hash = :hash, salt = :salt, role = :role, daily_request_limit = 999999 WHERE id = :uid"),
                            {"uname": username.lower(), "email": email.lower(), "name": name, "hash": pw_hash, "salt": salt, "role": role, "uid": existing[0]}
                        )
                    else:
                        from app.db.repositories.user_repo import DEFAULT_TENANT_ID
                        await s.execute(
                            text("INSERT INTO users (id, tenant_id, username, email, name, password_hash, salt, role, is_active, daily_request_limit) VALUES (:uid, :tid, :uname, :email, :name, :hash, :salt, :role, true, 999999)"),
                            {"uid": user_id, "tid": DEFAULT_TENANT_ID, "uname": username.lower(), "email": email.lower(), "name": name, "hash": pw_hash, "salt": salt, "role": role}
                        )
            asyncio.run(sync_pg())
            print(f"✅ Successfully synchronized admin user '{username}' to PostgreSQL.")
    except Exception as pg_err:
        pass



def main():
    parser = argparse.ArgumentParser(description="Create or update an admin user in Ridge SQLite database.")
    parser.add_argument("--username", default="admin", help="Admin username (default: admin)")
    parser.add_argument("--password", default="kichu@5120", help="Admin password (default: kichu@5120)")
    parser.add_argument("--email", default="admin@ridge.ai", help="Admin email (default: admin@ridge.ai)")
    parser.add_argument("--name", default="Ridge Administrator", help="Display name")
    parser.add_argument("--role", default="admin", choices=["admin", "user"], help="User role")
    parser.add_argument("--db-path", default=None, help="Path to users.db (default: $AUTH_DB_PATH or ./users.db)")

    args = parser.parse_args()
    create_or_update_admin(
        username=args.username,
        password=args.password,
        email=args.email,
        name=args.name,
        role=args.role,
        db_path=args.db_path,
    )


if __name__ == "__main__":
    main()
