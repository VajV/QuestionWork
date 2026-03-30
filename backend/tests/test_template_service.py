"""Tests for template_service helpers and edge cases."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.services import template_service


def test_row_to_dict_handles_malformed_skills_json(caplog):
    row = {
        "id": "tpl_1",
        "owner_id": "user_1",
        "name": "Template",
        "title": "Title",
        "description": "Desc",
        "required_grade": "novice",
        "skills": "{bad json",
        "budget": 100,
        "currency": "RUB",
        "is_urgent": False,
        "required_portfolio": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    result = template_service._row_to_dict(row)

    assert result["skills"] == []
    assert "Malformed skills JSON in template tpl_1" in caplog.text


@pytest.mark.asyncio
async def test_create_template_serializes_skills_and_returns_payload():
    conn = AsyncMock()

    result = await template_service.create_template(
        conn,
        "user_1",
        name="Backend Starter",
        title="FastAPI API",
        skills=["python", "fastapi"],
        budget=1500,
    )

    insert_args = conn.execute.await_args.args
    assert json.loads(insert_args[7]) == ["python", "fastapi"]
    assert result["owner_id"] == "user_1"
    assert result["skills"] == ["python", "fastapi"]


@pytest.mark.asyncio
async def test_update_template_returns_existing_row_when_no_mutable_fields_provided():
    existing = {
        "id": "tpl_1",
        "owner_id": "user_1",
        "name": "Template",
        "title": "Title",
        "description": "Desc",
        "required_grade": "novice",
        "skills": "[\"python\"]",
        "budget": 100,
        "currency": "RUB",
        "is_urgent": False,
        "required_portfolio": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=existing)

    result = await template_service.update_template(
        conn,
        "tpl_1",
        "user_1",
        unknown_field="ignored",
    )

    assert result is not None
    assert result["id"] == "tpl_1"
    assert result["skills"] == ["python"]
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_template_serializes_skills_and_returns_updated_row():
    now = datetime.now(timezone.utc)
    existing = {
        "id": "tpl_1",
        "owner_id": "user_1",
        "name": "Template",
        "title": "Title",
        "description": "Desc",
        "required_grade": "novice",
        "skills": "[\"python\"]",
        "budget": 100,
        "currency": "RUB",
        "is_urgent": False,
        "required_portfolio": False,
        "created_at": now,
        "updated_at": now,
    }
    updated = {
        **existing,
        "skills": "[\"python\", \"sql\"]",
        "title": "Updated Title",
        "updated_at": now,
    }
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=[existing, updated])

    result = await template_service.update_template(
        conn,
        "tpl_1",
        "user_1",
        title="Updated Title",
        skills=["python", "sql"],
    )

    assert result is not None
    assert result["title"] == "Updated Title"
    assert result["skills"] == ["python", "sql"]
    update_args = conn.fetchrow.await_args_list[1].args
    assert "skills = $" in update_args[0]
    assert json.loads(update_args[3]) == ["python", "sql"]


@pytest.mark.asyncio
async def test_delete_template_returns_true_when_row_deleted():
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="DELETE 1")

    deleted = await template_service.delete_template(conn, "tpl_1", "user_1")

    assert deleted is True