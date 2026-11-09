"""
LLM client for Wayfare.

Supports two providers behind a single interface:
  - Google Gemini  (llm_provider=gemini)  — default
  - IBM watsonx.ai (llm_provider=watsonx) — optional

Both expose the same async generate() / generate_json() methods.
FakeGraniteClient is kept for automated tests only.
"""
from __future__ import annotations
import logging
from functools import lru_cache
from ..config import get_settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Base interface every LLM client must implement."""

    async def generate(self, prompt: str, system: str | None = None) -> str:
        raise NotImplementedError

    async def generate_json(self, prompt: str, system: str | None = None) -> str:
        json_system = (system or "") + "\nRespond with valid JSON only. No explanation outside the JSON object."
        return await self.generate(prompt, system=json_system)


# ── Google Gemini ─────────────────────────────────────────────────────────────

class GeminiClient(LLMClient):
    """Google Gemini via the google-genai SDK (current, non-deprecated)."""

    def __init__(self, api_key: str, model: str = "gemini-3.8-flash") -> None:
        self.model_id = model
        self._api_key = api_key
        self._available = False
        try:
            from google import genai  # noqa: F401 – just check it's importable
            self._available = bool(api_key)
            if self._available:
                logger.info("Gemini client ready: %s", model)
            else:
                logger.warning("Gemini client: GEMINI_API_KEY is empty")
        except ImportError as exc:
            logger.warning("google-genai not installed: %s", exc)

    async def generate(self, prompt: str, system: str | None = None) -> str:
        if not self._available:
            raise RuntimeError("Gemini not configured. Set GEMINI_API_KEY in .env")
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        try:
            from google import genai
            client = genai.Client(api_key=self._api_key)
            response = await client.aio.models.generate_content(
                model=self.model_id,
                contents=full_prompt,
            )
            return response.text
        except Exception as exc:
            logger.error("Gemini generation failed: %s", exc)
            raise


# ── IBM watsonx.ai / Granite ──────────────────────────────────────────────────

class GraniteClient(LLMClient):
    """IBM Granite via watsonx.ai – used when llm_provider=watsonx."""

    def __init__(self, url: str, api_key: str, project_id: str, model_id: str) -> None:
        self.model_id = model_id
        self._available = False
        try:
            from ibm_watsonx_ai import Credentials
            from ibm_watsonx_ai.foundation_models import ModelInference
            creds = Credentials(url=url, api_key=api_key)
            self._model = ModelInference(
                model_id=model_id,
                credentials=creds,
                project_id=project_id,
                params={"max_new_tokens": 2048, "temperature": 0.1, "repetition_penalty": 1.1},
            )
            self._available = True
            logger.info("Granite client ready: %s", model_id)
        except Exception as exc:
            logger.warning("Granite client unavailable: %s", exc)
            self._model = None

    async def generate(self, prompt: str, system: str | None = None) -> str:
        if not self._available or self._model is None:
            raise RuntimeError("IBM Granite not configured. Set WATSONX_API_KEY and WATSONX_PROJECT_ID.")
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: self._model.generate_text(prompt=full_prompt))
            return response
        except Exception as exc:
            logger.error("Granite generation failed: %s", exc)
            raise


# ── Test stub ─────────────────────────────────────────────────────────────────

class FakeGraniteClient(LLMClient):
    """
    TESTS ONLY – deterministic stub, never used in the running app.
    Named FakeGraniteClient for backward compatibility with existing tests.
    """

    def __init__(self) -> None:
        self.model_id = "fake-llm"
        self._available = True

    async def generate(self, prompt: str, system: str | None = None) -> str:
        p = prompt.lower()
        if "extract_preferences" in p or "preference" in p:
            return ('{"origin":"Delhi","destination":"Mumbai","start_date":"2025-03-01",'
                    '"end_date":"2025-03-05","num_adults":2,"num_children":0,'
                    '"budget_inr":20000,"trip_type":"domestic","transport_preference":"train",'
                    '"accommodation_type":"stays","interests":[],"clarifying_question":null}')
        if "itinerary" in p or "build" in p:
            return '{"title":"Delhi to Mumbai","granite_summary":"A great trip.","tool_calls":[]}'
        if "replan" in p:
            return '{"granite_explanation":"Train cancelled. Next available alternative found. Hotel check-in adjusted.","tool_calls":[]}'
        if "compare" in p or "price" in p:
            return '{"granite_reason":"The overnight train offers great value.","tool_calls":[]}'
        return '{"tool_calls":[],"reply":"How can I help you plan your trip?"}'


# ── Factory ───────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_granite_client() -> LLMClient:
    """
    Returns the configured LLM client.
    Function name kept as get_granite_client() so existing imports don't break.
    """
    s = get_settings()
    if s.llm_provider == "watsonx":
        return GraniteClient(
            url=s.watsonx_url,
            api_key=s.watsonx_api_key,
            project_id=s.watsonx_project_id,
            model_id=s.granite_model_id,
        )
    # Default: Gemini
    return GeminiClient(api_key=s.gemini_api_key, model=s.gemini_model)


# Alias so existing code that imports GraniteClient still works
get_llm_client = get_granite_client
