"""
Learning Voice Service
Generates section intro scripts via OpenRouter LLM, then synthesises speech via edge-tts.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import AsyncIterator

import edge_tts
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

VOICE = "ru-RU-SvetlanaNeural"  # female Russian TTS voice

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
# Fast completion model — try in order until one responds (free tier may vary by availability)
OPENROUTER_MODEL = "google/gemma-3-4b-it:free"
_FALLBACK_MODELS = [
    "google/gemma-3-4b-it:free",
    "google/gemma-3-12b-it:free",
    "meta-llama/llama-3.2-3b-instruct:free",
]

VALID_SECTIONS = frozenset({"human-languages", "llm-ai", "programming"})

SECTION_META: dict[str, dict[str, str]] = {
    "human-languages": {
        "title": "Разговорные языки",
        "description": (
            "Здесь собраны интерактивные курсы по разговорным языкам — "
            "английскому, немецкому, французскому и другим. "
            "Занятия построены на диалоговых сценариях и живой практике."
        ),
    },
    "llm-ai": {
        "title": "LLM и нейросети",
        "description": (
            "Курсы по работе с большими языковыми моделями: "
            "Prompt Engineering, RAG-системы, файн-тюнинг и деплой. "
            "Подходит как для разработчиков, так и для аналитиков."
        ),
    },
    "programming": {
        "title": "Языки программирования",
        "description": (
            "Практические курсы по Python, JavaScript/TypeScript, Rust, Go и другим языкам. "
            "Упор на реальные проекты и работу с кодом."
        ),
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# LLM script generation
# ──────────────────────────────────────────────────────────────────────────────

async def generate_voice_script(section: str) -> str:
    """
    Call OpenRouter to produce a short (~50 word) Russian voice intro for the given section.
    Falls back to a static description if the API key is absent or the call fails.
    """
    meta = SECTION_META[section]

    if not settings.OPENROUTER_API_KEY:
        logger.warning("OPENROUTER_API_KEY not set — using static fallback script")
        return _fallback_script(section)

    system_prompt = (
        "Ты дружелюбный голосовой ассистент русскоязычного образовательного сайта QuestionWork. "
        "Говори тепло и лаконично. Никаких списков, только связный текст. "
        "Максимум 3 предложения. Никаких скобок, звёздочек и лишних символов."
    )
    user_prompt = (
        f"Поприветствуй пользователя и кратко расскажи про раздел «{meta['title']}»: "
        f"{meta['description']}"
    )

    # Merge system instructions into user message so models that ban system role still work
    combined_user_prompt = f"{system_prompt}\n\n{user_prompt}"

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            last_exc: Exception | None = None
            for model in _FALLBACK_MODELS:
                resp = await client.post(
                    OPENROUTER_API_URL,
                    headers={
                        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                        "HTTP-Referer": "https://questionwork.com",
                        "X-Title": "QuestionWork Learning",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "user", "content": combined_user_prompt},
                        ],
                        "max_tokens": 150,
                        "temperature": 0.7,
                    },
                )
                if resp.status_code in (400, 404, 429):
                    logger.warning("Model %s returned %s, trying next", model, resp.status_code)
                    last_exc = Exception(f"Model {model!r} returned {resp.status_code}")
                    continue
                resp.raise_for_status()
                data = resp.json()
                text: str = data["choices"][0]["message"]["content"].strip()
                if "<think>" in text:
                    end = text.find("</think>")
                    text = text[end + 8:].strip() if end != -1 else text.split("</think>")[-1].strip()
                return text or _fallback_script(section)
            raise last_exc or Exception("All models unavailable")
    except Exception as exc:
        logger.error("OpenRouter call failed for section=%s: %s", section, exc)
        return _fallback_script(section)


def _fallback_script(section: str) -> str:
    meta = SECTION_META[section]
    return f"Добро пожаловать в раздел «{meta['title']}»! {meta['description']}"


# ──────────────────────────────────────────────────────────────────────────────
# TTS synthesis
# ──────────────────────────────────────────────────────────────────────────────

async def stream_tts_audio(text: str) -> AsyncIterator[bytes]:
    """Yield raw audio bytes (MP3) from edge-tts Svetlana voice."""
    communicate = edge_tts.Communicate(text, VOICE)
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            yield chunk["data"]


# ──────────────────────────────────────────────────────────────────────────────
# Intro audio cache  (avoids LLM + TTS cost on repeated requests)
# ──────────────────────────────────────────────────────────────────────────────

_intro_cache: dict[str, tuple[bytes, float]] = {}  # section → (audio_bytes, timestamp)
_INTRO_CACHE_TTL = 1800.0  # 30 minutes
_intro_cache_lock = asyncio.Lock()


async def get_intro_audio(section: str) -> bytes:
    """Return cached intro audio or generate + cache a fresh one."""
    now = time.monotonic()
    cached = _intro_cache.get(section)
    if cached and (now - cached[1]) < _INTRO_CACHE_TTL:
        logger.debug("Cache hit for section=%s", section)
        return cached[0]

    async with _intro_cache_lock:
        # Double-check after acquiring lock
        cached = _intro_cache.get(section)
        if cached and (now - cached[1]) < _INTRO_CACHE_TTL:
            return cached[0]

        script = await generate_voice_script(section)
        chunks: list[bytes] = []
        async for chunk in stream_tts_audio(script):
            chunks.append(chunk)
        audio = b"".join(chunks)
        _intro_cache[section] = (audio, time.monotonic())
        logger.info("Cached intro audio for section=%s (%d bytes)", section, len(audio))
        return audio


async def warmup_intro_cache() -> None:
    """Pre-generate all section intro audio at startup so first requests are instant."""
    for section in VALID_SECTIONS:
        try:
            await get_intro_audio(section)
            logger.info("Intro warmup complete for section=%s", section)
        except Exception as exc:
            logger.warning("Intro warmup failed for section=%s: %s", section, exc)


# ──────────────────────────────────────────────────────────────────────────────
# Chat response generation
# ──────────────────────────────────────────────────────────────────────────────

_CHAT_SYSTEM_PROMPT_TEMPLATE = (
    "Ты голосовой ассистент обучающей платформы QuestionWork. "
    "Ты помогаешь пользователю в разделе «{title}»: {description} "
    "Отвечай коротко, тепло и по делу — максимум 3 предложения. "
    "Только связный текст, никаких списков, скобок, звёздочек и лишних символов."
)


async def generate_chat_script(
    section: str,
    history: list[dict],
    user_message: str,
) -> str:
    """
    Call OpenRouter to generate a short chat reply in context of the section.
    history is a list of {role: user|assistant, content: str} dicts (last 6 entries used).
    Falls back to a static reply on any failure.
    """
    meta = SECTION_META[section]

    if not settings.OPENROUTER_API_KEY:
        return "Задайте вопрос — я постараюсь помочь!"

    # Build messages list without system role — inject context into user turn for universal compatibility
    chat_messages: list[dict] = []
    chat_messages.extend(history[-6:])
    context_prefix = (
        f"[Контекст сессии: ты голосовой ассистент раздела «{meta['title']}». "
        f"{meta['description']} Отвечай коротко — максимум 3 предложения, без списков и символов.]\n\n"
    )
    chat_messages.append({"role": "user", "content": context_prefix + user_message})

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            last_exc2: Exception | None = None
            for model in _FALLBACK_MODELS:
                resp = await client.post(
                    OPENROUTER_API_URL,
                    headers={
                        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                        "HTTP-Referer": "https://questionwork.com",
                        "X-Title": "QuestionWork Learning",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": chat_messages,
                        "max_tokens": 150,
                        "temperature": 0.7,
                    },
                )
                if resp.status_code in (400, 404, 429):
                    logger.warning("Chat model %s returned %s, trying next", model, resp.status_code)
                    last_exc2 = Exception(f"Model {model!r} returned {resp.status_code}")
                    continue
                resp.raise_for_status()
                data = resp.json()
                text: str = data["choices"][0]["message"]["content"].strip()
                if "<think>" in text:
                    end = text.find("</think>")
                    text = text[end + 8:].strip() if end != -1 else text.split("</think>")[-1].strip()
                return text or "Интересный вопрос! Попробуйте переформулировать."
            raise last_exc2 or Exception("All models unavailable")
    except Exception as exc:
        logger.error("Chat LLM failed for section=%s: %s", section, exc)
        return "Извините, не смог обработать запрос. Попробуйте ещё раз."
