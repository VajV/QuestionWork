from contextlib import asynccontextmanager

import pytest
from fastapi import HTTPException

from app.db import session


@pytest.mark.asyncio
async def test_get_db_connection_maps_connection_refused_to_503(monkeypatch):
    @asynccontextmanager
    async def fake_acquire_db_connection():
        raise ConnectionRefusedError("db down")
        yield

    monkeypatch.setattr(session, "acquire_db_connection", fake_acquire_db_connection)

    generator = session.get_db_connection()

    with pytest.raises(HTTPException) as exc_info:
        await anext(generator)

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Database temporarily unavailable"


@pytest.mark.asyncio
async def test_get_db_connection_does_not_mask_non_connectivity_errors(monkeypatch):
    @asynccontextmanager
    async def fake_acquire_db_connection():
        raise RuntimeError("schema mismatch")
        yield

    monkeypatch.setattr(session, "acquire_db_connection", fake_acquire_db_connection)

    generator = session.get_db_connection()

    with pytest.raises(RuntimeError, match="schema mismatch"):
        await anext(generator)