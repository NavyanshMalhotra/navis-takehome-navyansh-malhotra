"""
LLM Client Interface for Nevis Agentic Platform.
Native integration with Google GenAI SDK (Gemini 2.5 Flash / 2.0 Flash / 1.5 Flash)
and Google Text Embeddings (text-embedding-004) using a unified API key.
"""

import json
import logging
from typing import Dict, Any, List, Union, Optional
from config import config

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base exception for LLM-related errors."""
    pass


class APIKeyMissingError(LLMError):
    """Raised when an operation requiring an LLM or embedding is invoked without an API key."""
    pass


class LLMExecutionError(LLMError):
    """Raised when an LLM API call fails across all available model candidates."""
    pass


class LLMClient:
    def __init__(self):
        self._client = None
        self._is_vertex = False

        if config.gemini_api_key:
            try:
                from google import genai
                if config.gemini_api_key.startswith("AQ."):
                    self._client = genai.Client(
                        vertexai=True,
                        api_key=config.gemini_api_key,
                        project=config.google_cloud_project,
                        location=config.google_cloud_location,
                    )
                    self._is_vertex = True
                    logger.info("Initialized Google GenAI Vertex client (Project: %s, Location: %s)",
                                config.google_cloud_project, config.google_cloud_location)
                else:
                    self._client = genai.Client(api_key=config.gemini_api_key)
                    logger.info("Initialized Google GenAI client with model: %s", config.gemini_model)
            except Exception as e:
                logger.error("Failed to initialize Google GenAI client: %s", e)
                self._client = None
        else:
            logger.warning("No GEMINI_API_KEY found in configuration. LLM reasoning and embeddings are unavailable.")

    @property
    def is_available(self) -> bool:
        """Returns True if the client is initialized with an active API key."""
        return self._client is not None

    def _ensure_available(self):
        if not self.is_available:
            raise APIKeyMissingError(
                "GEMINI_API_KEY is not configured or failed initialization. "
                "Supply a valid Google Gemini API key in .env to run agentic reasoning."
            )

    def generate_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """
        Executes an agent reasoning call with Google Gemini, requesting structured JSON.
        """
        self._ensure_available()

        full_prompt = f"{system_prompt}\n\nUser Request:\n{user_prompt}\n\nRespond with valid JSON only."
        last_error = None

        for model_name in config.gemini_fallback_models:
            try:
                response = self._client.models.generate_content(
                    model=model_name,
                    contents=full_prompt,
                )
                text = response.text.strip()
                # Strip markdown code fences if present
                if text.startswith("```"):
                    lines = text.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    text = "\n".join(lines).strip()
                return json.loads(text)
            except Exception as e:
                logger.debug("Gemini call with %s failed: %s", model_name, e)
                last_error = e
                continue

        raise LLMExecutionError(f"All Gemini models failed. Last error: {last_error}")

    def generate_text(self, prompt: str, system_prompt: str = "") -> str:
        """
        Executes a freeform agent generation call (e.g. for ReAct thoughts or clarification drafting).
        """
        self._ensure_available()

        contents = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        last_error = None

        for model_name in config.gemini_fallback_models:
            try:
                response = self._client.models.generate_content(
                    model=model_name,
                    contents=contents,
                )
                return response.text.strip()
            except Exception as e:
                logger.debug("Gemini text call with %s failed: %s", model_name, e)
                last_error = e
                continue

        raise LLMExecutionError(f"All Gemini models failed for text generation. Last error: {last_error}")

    def embed_text(self, texts: Union[str, List[str]]) -> List[List[float]]:
        """
        Generates vector embeddings using Google's text-embedding-004 endpoint.
        Returns a list of 768-dimensional float vectors.
        """
        self._ensure_available()

        if isinstance(texts, str):
            input_list = [texts]
        else:
            input_list = texts

        embeddings: List[List[float]] = []
        for text in input_list:
            try:
                resp = self._client.models.embed_content(
                    model=config.embedding_model,
                    contents=text,
                )
                if hasattr(resp, "embeddings") and resp.embeddings:
                    embeddings.append(list(resp.embeddings[0].values))
                elif hasattr(resp, "embedding") and hasattr(resp.embedding, "values"):
                    embeddings.append(list(resp.embedding.values))
                else:
                    raise ValueError("Unexpected embedding response structure from Google GenAI SDK")
            except Exception as e:
                logger.error("Failed to generate embedding for text snippet: %s", e)
                raise LLMExecutionError(f"Google embedding endpoint failed: {e}")

        return embeddings


llm_client = LLMClient()
