from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db_connection
from app.main import app
from app.services.lead_service import create_lead


def _make_conn():
    conn = AsyncMock()
    txn = AsyncMock()
    txn.__aenter__.return_value = None
    txn.__aexit__.return_value = None
    conn.transaction = MagicMock(return_value=txn)
    return conn


class TestLeadService:
    @pytest.mark.asyncio
    async def test_create_lead_persists_normalized_payload(self):
        conn = _make_conn()

        result = await create_lead(
            conn,
            email=" SALES@Example.COM ",
            company_name="Guild Systems",
            contact_name="Mira Stone",
            use_case="FastAPI backend",
            budget_band="$800 - $3,000",
            message="Need help with API and auth hardening",
            source="for_clients_page",
            utm_source="google",
            utm_medium="cpc",
            utm_campaign="spring-demand",
            utm_term=None,
            utm_content=None,
            ref="google-search",
            landing_path="/for-clients?utm_source=google",
        )

        assert result["email"] == "sales@example.com"
        assert result["source"] == "for_clients_page"
        assert isinstance(result["created_at"], datetime)

        executed_query = conn.execute.await_args.args[0]
        assert "INSERT INTO growth_leads" in executed_query
        conn.transaction.assert_called_once()


class TestLeadEndpoint:
    def test_create_lead_endpoint_returns_201(self, monkeypatch):
        conn = _make_conn()
        now = datetime.now(timezone.utc)

        async def _mock_conn_dep():
            yield conn

        mocked_create = AsyncMock(
            return_value={
                "id": "lead_1",
                "email": "buyer@example.com",
                "company_name": "Quest Ops",
                "contact_name": "Elena Vale",
                "use_case": "Urgent bugfix",
                "budget_band": "$300 - $1,500",
                "message": "Need production fix this week",
                "source": "hire_urgent_bugfix",
                "utm_source": None,
                "utm_medium": None,
                "utm_campaign": None,
                "utm_term": None,
                "utm_content": None,
                "created_at": now,
            }
        )

        monkeypatch.setattr("app.api.v1.endpoints.leads.lead_service.create_lead", mocked_create)
        app.dependency_overrides[get_db_connection] = _mock_conn_dep
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.post(
                    "/api/v1/leads/",
                    json={
                        "email": "buyer@example.com",
                        "company_name": "Quest Ops",
                        "contact_name": "Elena Vale",
                        "use_case": "Urgent bugfix",
                        "budget_band": "$300 - $1,500",
                        "message": "Need production fix this week",
                        "source": "hire_urgent_bugfix",
                    },
                )
        finally:
            app.dependency_overrides.pop(get_db_connection, None)

        assert response.status_code == 201
        payload = response.json()
        assert payload["email"] == "buyer@example.com"
        assert payload["source"] == "hire_urgent_bugfix"

    def test_create_lead_endpoint_maps_service_error_to_400(self, monkeypatch):
        conn = _make_conn()

        async def _mock_conn_dep():
            yield conn

        monkeypatch.setattr(
            "app.api.v1.endpoints.leads.lead_service.create_lead",
            AsyncMock(side_effect=ValueError("Lead payload invalid")),
        )
        app.dependency_overrides[get_db_connection] = _mock_conn_dep
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.post(
                    "/api/v1/leads/",
                    json={
                        "email": "buyer@example.com",
                        "company_name": "Quest Ops",
                        "contact_name": "Elena Vale",
                        "use_case": "Urgent bugfix",
                        "source": "hire_urgent_bugfix",
                    },
                )
        finally:
            app.dependency_overrides.pop(get_db_connection, None)

        assert response.status_code == 400
        assert response.json()["detail"] == "Lead payload invalid"