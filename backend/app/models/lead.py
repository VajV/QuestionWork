from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _strip_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class LeadCreateRequest(BaseModel):
    email: EmailStr
    company_name: str = Field(..., min_length=2, max_length=120)
    contact_name: str = Field(..., min_length=2, max_length=120)
    use_case: str = Field(..., min_length=2, max_length=120)
    budget_band: Optional[str] = Field(None, max_length=80)
    message: Optional[str] = Field(None, max_length=2000)
    source: str = Field(..., min_length=2, max_length=120)
    utm_source: Optional[str] = Field(None, max_length=120)
    utm_medium: Optional[str] = Field(None, max_length=120)
    utm_campaign: Optional[str] = Field(None, max_length=120)
    utm_term: Optional[str] = Field(None, max_length=120)
    utm_content: Optional[str] = Field(None, max_length=120)
    ref: Optional[str] = Field(None, max_length=255)
    landing_path: Optional[str] = Field(None, max_length=255)
    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator(
        "company_name",
        "contact_name",
        "use_case",
        "source",
        mode="before",
    )
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("Поле должно быть строкой")
        stripped = value.strip()
        if not stripped:
            raise ValueError("Поле не может быть пустым")
        return stripped

    @field_validator(
        "budget_band",
        "message",
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "ref",
        "landing_path",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        return _strip_optional(value)


class LeadResponse(BaseModel):
    id: str
    email: EmailStr
    company_name: str
    contact_name: str
    use_case: str
    budget_band: Optional[str] = None
    message: Optional[str] = None
    source: str
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_term: Optional[str] = None
    utm_content: Optional[str] = None
    ref: Optional[str] = None
    landing_path: Optional[str] = None
    status: str = "new"
    last_contacted_at: Optional[datetime] = None
    next_contact_at: Optional[datetime] = None
    nurture_stage: str = "intake"
    converted_user_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))