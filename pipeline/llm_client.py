"""
LLM Client Interface for Nevis Agentic Platform.
Native integration with Google GenAI SDK (Gemini 2.5 Flash / Gemini 2.0 Flash / Gemini 1.5 Flash).
Includes Calibrated Deterministic Agent Fallback (Zero-dependency offline mode for 100% test reproducibility).
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

        if config.gemini_api_key:
            try:
                from google import genai
                self._gemini_client = genai.Client(api_key=config.gemini_api_key)
                self.provider = "gemini"
                logger.info("Initialized Google GenAI client with model: %s", config.gemini_model)
            except Exception as e:
                logger.warning("Failed to initialize Google GenAI: %s. Operating in calibrated fallback mode.", e)

        if self.provider == "offline":
            logger.info("Operating in Calibrated Deterministic Agent Fallback mode (Offline / Zero-Key).")

    def generate_json(self, system_prompt: str, user_prompt: str, fallback_handler=None) -> Dict[str, Any]:
        """
        Executes an agent reasoning call with Google Gemini, requesting structured JSON.
        If live provider fails or is unset, invokes fallback_handler.
        """
        if self.provider == "gemini" and self._gemini_client:
            full_prompt = f"{system_prompt}\n\nUser Request:\n{user_prompt}\n\nRespond with valid JSON only."
            
            # Try primary model and fallbacks
            for model_name in config.gemini_fallback_models:
                try:
                    response = self._gemini_client.models.generate_content(
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
                    continue

            logger.info("Gemini live call unavailable or restricted. Seamlessly executing via calibrated agent fallback.")

        # Offline / Fallback execution
        if fallback_handler:
            return fallback_handler()
        return {}

llm_client = LLMClient()
