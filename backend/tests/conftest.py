"""Pytest fixtures for Gauntlet integration tests."""

from __future__ import annotations

import pytest
from httpx import Client, WSGITransport

from app.server import app


@pytest.fixture
def client():
    """Sync HTTP client pointed at the FastAPI app (no server needed)."""
    # FastAPI's TestClient uses httpx under the hood; we use WSGITransport
    # to call the ASGI app directly without a running server.
    from fastapi.testclient import TestClient

    tc = TestClient(app)
    return tc
