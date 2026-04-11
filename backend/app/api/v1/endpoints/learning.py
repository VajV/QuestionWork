"""
Learning endpoints
POST /learning/voice-intro  — serve cached TTS audio for a section intro
POST /learning/chat         — interactive chat with voice response
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import require_auth
from app.core.ratelimit import check_rate_limit, get_client_ip
from app.services.learning_voice_service import (
    VALID_SECTIONS,
    generate_chat_script,
    get_intro_audio,
    stream_tts_audio,
)

router = APIRouter(prefix="/learning", tags=["Обучение"])

SectionType = Literal["human-languages", "llm-ai", "programming"]


class VoiceIntroRequest(BaseModel):
    section: SectionType


class ChatMessageSchema(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=500)


class LearningChatRequest(BaseModel):
    section: SectionType
    history: list[ChatMessageSchema] = Field(default_factory=list, max_length=20)
    message: str = Field(..., min_length=1, max_length=500)


@router.post("/voice-intro")
async def voice_intro(body: VoiceIntroRequest, request: Request, _=Depends(require_auth)) -> Response:
    """
    Serve intro audio for the requested learning section.
    Audio is generated once and cached in memory for 30 minutes.
    Rate limited to 5 requests per minute per IP.
    """
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="learning_voice_intro", limit=5, window_seconds=60)

    if body.section not in VALID_SECTIONS:
        raise HTTPException(status_code=400, detail=f"Unknown section: {body.section!r}")

    audio_bytes = await get_intro_audio(body.section)

    return Response(content=audio_bytes, media_type="audio/mpeg")


@router.post("/chat")
async def learning_chat(body: LearningChatRequest, request: Request, _=Depends(require_auth)) -> StreamingResponse:
    """
    Interactive voice chat about the learning section.
    AI reply text is returned in the X-Response-Text header alongside the audio body.
    Rate limited to 20 requests per minute per IP.
    """
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="learning_chat", limit=20, window_seconds=60)

    if body.section not in VALID_SECTIONS:
        raise HTTPException(status_code=400, detail=f"Unknown section: {body.section!r}")

    history = [m.model_dump() for m in body.history]
    script = await generate_chat_script(body.section, history, body.message)

    # URL-encode so it's safe as a header value (HTTP headers must be ASCII-only)
    from urllib.parse import quote
    encoded_script = quote(script)

    return StreamingResponse(
        stream_tts_audio(script),
        media_type="audio/mpeg",
        headers={
            "X-Response-Text": encoded_script,
        },
    )
