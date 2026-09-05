"""
LLM Client Interface for Nevis Agentic Platform.
Provides multi-provider support:
1. Google GenAI SDK (Gemini 2.5 Flash / Gemini 1.5 Pro) via GEMINI_API_KEY.
2. OpenAI SDK via OPENAI_API_KEY.
3. Calibrated Deterministic Agent Fallback (Zero-dependency offline mode for 100% test reproducibility).
"""

import json
import logging
from typing import Dict, Any, Optional
from config import config

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self):
        self.provider = "offline"
        self._gemini_client = None
        self._openai_client = None

        if config.gemini_api_key:
            try:
                from google import genai
                self._gemini_client = genai.Client(api_key=config.gemini_api_key)
                self.provider = "gemini"
                logger.info("Initialized Google GenAI client with model: %s", config.gemini_model)
            except Exception as e:
                logger.warning("Failed to initialize Google GenAI: %s. Falling back.", e)

        if self.provider == "offline" and config.openai_api_key:
            try:
                import openai
                self._openai_client = openai.OpenAI(api_key=config.openai_api_key)
                self.provider = "openai"
                logger.info("Initialized OpenAI client with model: %s", config.openai_model)
            except Exception as e:
                logger.warning("Failed to initialize OpenAI: %s. Falling back.", e)

        if self.provider == "offline":
            logger.info("Operating in Calibrated Deterministic Agent Fallback mode (Offline / Zero-Key).")

    def generate_json(self, system_prompt: str, user_prompt: str, fallback_handler=None) -> Dict[str, Any]:
        """
        Executes an agent reasoning call, requesting structured JSON.
        If live provider fails or is unset, invokes fallback_handler.
        """
        if self.provider == "gemini" and self._gemini_client:
            try:
                full_prompt = f"{system_prompt}\n\nUser Request:\n{user_prompt}\n\nRespond with valid JSON only."
                response = self._gemini_client.models.generate_content(
                    model=config.gemini_model,
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
                logger.warning("Gemini live call error: %s. Using calibrated agent fallback.", e)

        elif self.provider == "openai" and self._openai_client:
            try:
                response = self._openai_client.chat.completions.create(
                    model=config.openai_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"}
                )
                text = response.choices[0].message.content
                return json.loads(text)
            except Exception as e:
                logger.warning("OpenAI live call error: %s. Using calibrated agent fallback.", e)

        # Offline / Fallback execution
        if fallback_handler:
            return fallback_handler()
        return {}

llm_client = LLMClient()
