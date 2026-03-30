"""Pydantic models for shortlists."""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import List


class ShortlistEntry(BaseModel):
    id: str
    client_id: str
    freelancer_id: str
    created_at: datetime


class ShortlistResponse(BaseModel):
    entries: List[ShortlistEntry] = Field(default_factory=list)
    total: int = 0
