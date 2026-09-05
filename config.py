"""
Configuration module for the Nevis FDE Agentic Data Pipeline.
Reads from environment variables and provides structured defaults.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict

# Try importing dotenv if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent

@dataclass(frozen=True)
class PipelineConfig:
    # Directories
    base_dir: Path = BASE_DIR
    sources_dir: Path = BASE_DIR / os.getenv("SOURCES_DIR", "nevis-fde-hometask/sources")
    outputs_dir: Path = BASE_DIR / os.getenv("OUTPUTS_DIR", "outputs")
    prompts_dir: Path = BASE_DIR / "prompts"
    
    # LLM Settings
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "").strip()
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
    
    # Routing & Confidence Thresholds
    # >= 0.85: Auto-committed to canonical output
    # 0.50 - 0.85: Staged for Operator Review in UI
    # < 0.50 or Policy Gate: Clarifications Round 2 for Dana Ruiz
    confidence_high_threshold: float = float(os.getenv("CONFIDENCE_HIGH_THRESHOLD", "0.85"))
    confidence_low_threshold: float = float(os.getenv("CONFIDENCE_LOW_THRESHOLD", "0.50"))
    
    # Web Server
    server_host: str = os.getenv("SERVER_HOST", "0.0.0.0")
    server_port: int = int(os.getenv("SERVER_PORT", "8000"))
    
    # Financial Benchmarks (Q2 2025 Quarter-End FX Rates to USD)
    # 2025-06-30 benchmark: EUR/USD ~ 1.071, CHF/USD ~ 1.114
    fx_rates_to_usd: Dict[str, float] = field(default_factory=lambda: {
        "USD": 1.0,
        "EUR": 1.0710,
        "CHF": 1.1140,
        "GBP": 1.2680,
        "CAD": 0.7310,
    })

    # Canonical Enum Values
    HOUSEHOLD_STATUSES: tuple = ("ACTIVE", "INACTIVE", "PROSPECT")
    CLIENT_ROLES: tuple = ("PRIMARY", "SPOUSE", "DEPENDENT", "SIGNER", "OTHER")
    ACCOUNT_TYPES: tuple = ("INDIVIDUAL", "JOINT", "TRUST", "IRA", "ROTH_IRA", "CORPORATE", "OTHER")
    INTERACTION_TYPES: tuple = ("REVIEW", "PROSPECTING", "ONBOARDING", "OTHER")

config = PipelineConfig()
