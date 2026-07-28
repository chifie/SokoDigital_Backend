import json
from typing import Any

import httpx

from app.config import settings


# ── System prompt for the SokoDigital marketplace assistant ──────────────
SYSTEM_PROMPT = """You are SokoBot, a helpful AI shopping assistant for SokoDigital — an African e-commerce marketplace.

You help users with:
- Product discovery and recommendations
- Order tracking and support
- Marketplace policies and FAQs
- General shopping advice

Keep responses concise, friendly, and helpful. When you don't know something specific about a user's account or order, tell them what they can do in the app (e.g., "You can check your order status in the Orders section of your profile").

If asked about something outside shopping/marketplace, politely redirect to shopping topics.
"""


async def chat_with_ai(
    message: str,
    conversation_history: list[dict[str, str]] | None = None,
) -> str:
    """Send a message to an OpenAI-compatible API and return the assistant's reply.

    ``conversation_history`` should be a list of ``{"role": ..., "content": ...}``
    dicts, ordered oldest first.

    Falls back to a canned response if ``AI_API_KEY`` is not configured.
    """
    api_key = settings.AI_API_KEY

    if not api_key:
        return (
            "I'm currently in offline mode. Please configure an AI API key "
            "in the admin settings to enable full AI assistance. "
            "In the meantime, you can browse products, track orders, and "
            "manage your account through the app."
        )

    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    if conversation_history:
        messages.extend(conversation_history)

    messages.append({"role": "user", "content": message})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload: dict[str, Any] = {
        "model": settings.AI_MODEL,
        "messages": messages,
        "max_tokens": settings.AI_MAX_TOKENS,
        "temperature": 0.7,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            settings.AI_API_URL,
            headers=headers,
            json=payload,
        )

    if response.status_code != 200:
        try:
            detail = response.json()
        except (json.JSONDecodeError, ValueError):
            detail = response.text

        raise Exception(f"AI API error {response.status_code}: {detail}")

    result = response.json()
    return result["choices"][0]["message"]["content"].strip()
