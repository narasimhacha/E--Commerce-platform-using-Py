import json
import os
 
from dotenv import load_dotenv
from google import genai
from google.genai import types
 
load_dotenv()
 
_API_KEY = os.getenv("GEMINI_API_KEY")
_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")  # confirm current free-tier model in AI Studio
_client = genai.Client(api_key=_API_KEY) if _API_KEY else None
 
 
class AIServiceError(Exception):
    """Raised when the LLM provider is unavailable or returns unusable output."""
 
 
def generate_json(system_prompt: str, user_prompt: str) -> dict:
    if _client is None:
        raise AIServiceError("GEMINI_API_KEY is not configured")
    try:
        response = _client.models.generate_content(
            model=_MODEL,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                temperature=0.3,
            ),
        )
        return json.loads(response.text)
    except json.JSONDecodeError as exc:
        raise AIServiceError("Model returned invalid JSON") from exc
    except Exception as exc:
        raise AIServiceError(f"AI provider call failed: {exc}") from exc
 