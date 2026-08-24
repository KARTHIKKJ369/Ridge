import os
import sys
import pytest
import pytest_asyncio

# Ensure root directory is on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.database import engine

@pytest_asyncio.fixture(autouse=True)
async def cleanup_db_connections():
    yield
    # Dispose connections tied to the test's event loop
    await engine.dispose()
