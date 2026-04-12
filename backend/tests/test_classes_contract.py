from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.v1.endpoints import classes


@pytest.mark.asyncio
async def test_get_my_class_returns_empty_state_when_user_has_no_class(monkeypatch):
    monkeypatch.setattr(classes.class_service, "get_user_class_info", AsyncMock(return_value=None))
    monkeypatch.setattr(classes, "check_rate_limit", AsyncMock(return_value=None))

    result = await classes.get_my_class(
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"), headers={}),
        current_user=SimpleNamespace(id="user_1"),
        conn=AsyncMock(),
    )

    assert result.has_class is False
    assert result.class_id == ""
    assert result.name_ru == "Класс не выбран"