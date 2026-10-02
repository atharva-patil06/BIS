import os
import time
from pathlib import Path

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Anthropic account had no credit balance on build night; swapped to the
# Gemini free-tier API per user instruction. Prompts/logic are unchanged.
# gemini-flash-latest returns intermittent 503 "high demand" errors on the
# free tier, so we retry it briefly, then fall back to other flash models.
# Note: the "2.5" model family shows up in models.list() but 404s as
# "no longer available to new users" — stick to -latest aliases and 3.x.
MODEL_CHAIN = ["gemini-flash-latest", "gemini-flash-lite-latest", "gemini-3.5-flash", "gemini-3.5-flash-lite"]


def _is_model_dead(error: genai_errors.ClientError) -> bool:
    return error.code == 404


_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def ask_llm(system: str, user_message: str, max_tokens: int = 1024, retries_per_model: int = 2) -> str:
    last_error = None
    for model in MODEL_CHAIN:
        for attempt in range(retries_per_model):
            try:
                response = _client.models.generate_content(
                    model=model,
                    contents=user_message,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        max_output_tokens=max_tokens,
                    ),
                )
                return response.text or ""
            except genai_errors.ServerError as e:
                last_error = e
                time.sleep(1.5 * (attempt + 1))
            except genai_errors.ClientError as e:
                last_error = e
                if _is_model_dead(e):
                    break  # skip retries on this model, move to next in chain
                time.sleep(1.5 * (attempt + 1))
    raise last_error
