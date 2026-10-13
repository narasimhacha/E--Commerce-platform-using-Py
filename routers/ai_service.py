import json
import os
import re
import time
from typing import Any

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

try:
    from google import genai
    from google.genai import errors, types
except ModuleNotFoundError:
    genai = None
    errors = None
    types = None

load_dotenv()
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

router = APIRouter(prefix="/ai", tags=["ai"])


class AIRequest(BaseModel):
    system: str
    user: str
    max_tokens: int = 1000


class AIServiceError(Exception):
    pass


def _get_client():
    if genai is None or types is None:
        raise AIServiceError("google-genai is not installed. Run `pip install google-genai`.")

    return genai.Client(
        api_key=os.getenv("GEMINI_API_KEY"),
        http_options=types.HttpOptions(timeout=20000),
    )


def call_json(system: str, user: str, max_tokens: int = 1000) -> dict[str, Any]:
    """Call the model and return parsed JSON, or raise AIServiceError."""
    if genai is None or types is None:
        raise AIServiceError("google-genai is not installed. Run `pip install google-genai`.")

    client = _get_client()
    config = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        max_output_tokens=max_tokens,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )
    last_error = None

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=user,
                config=config,
            )
            break
        except Exception as exc:  # pragma: no cover - simple retry logic
            last_error = exc
            if (
                errors is not None
                and isinstance(exc, errors.APIError)
                and exc.code in (429, 500, 503)
                and attempt < 2
            ):
                time.sleep(2 ** attempt)
                continue
            raise AIServiceError(f"API call failed: {exc}") from exc
    else:
        raise AIServiceError(f"API call failed: {last_error}")

    text = getattr(response, "text", None)
    if not text:
        raise AIServiceError("Model returned an empty response")

    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except (TypeError, ValueError) as exc:
        raise AIServiceError("Model returned invalid JSON") from exc


@router.post("/generate-json")
async def generate_json(payload: AIRequest):
    try:
        return call_json(payload.system, payload.user, payload.max_tokens)
    except AIServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
