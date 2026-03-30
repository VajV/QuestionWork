"""Probe OpenRouter free models for system-message support."""
import asyncio
import httpx

MODELS = [
    "google/gemma-3-4b-it:free",
    "google/gemma-3-12b-it:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "qwen/qwen3-4b:free",
    "google/gemma-3-27b-it:free",
    "mistralai/mistral-7b-instruct:free",
]

CONTEXT = "Ты образовательный ИИ-ассистент QuestionWork. Отвечай кратко по-русски."
MSGS = [
    {"role": "user", "content": f"{CONTEXT}\n\nПривет, что такое LLM?"},
]


async def probe():
    with open("C:/QuestionWork/backend/.env") as f:
        for line in f:
            if line.startswith("OPENROUTER_API_KEY="):
                api_key = line.split("=", 1)[1].strip()
                break

    async with httpx.AsyncClient(timeout=30.0) as c:
        for model in MODELS:
            try:
                r = await c.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"model": model, "messages": MSGS, "max_tokens": 80, "temperature": 0.7},
                )
                if r.status_code == 200:
                    reply = r.json()["choices"][0]["message"]["content"][:80]
                    print(f"✅ {model} -> {reply}")
                else:
                    err = r.json().get("error", {}).get("message", "?")[:80]
                    print(f"❌ {model} -> {r.status_code}: {err}")
            except Exception as e:
                print(f"💥 {model} -> exception: {e}")


asyncio.run(probe())
