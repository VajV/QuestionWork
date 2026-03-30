from pydantic import BaseModel, Field


class WebSocketTicketResponse(BaseModel):
    ticket: str = Field(..., min_length=16)
    expires_in_seconds: int = Field(..., ge=1)
