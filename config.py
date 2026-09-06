"""
Configuration module for the Nevis FDE Agentic Data Pipeline.
Reads secrets from .env and maintains system constants, model parameters, and FX rates.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List

# Load environment variables, allowing .env to take precedence
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
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
    
    # Secrets (Loaded from .env)
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip().strip("'\"")
    google_cloud_project: str = os.getenv("GOOGLE_CLOUD_PROJECT", "291630468248")
    google_cloud_location: str = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    
    # Model Selection
    gemini_model: str = "gemini-2.5-flash"
    gemini_fallback_models: tuple = ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash")
    embedding_model: str = "text-embedding-004"
    
    # Local Knowledge & Vector Cache
    knowledge_db_path: Path = outputs_dir / "knowledge_store.db"
    
    # Pipeline Confidence Routing Thresholds
    # >= 0.85: Auto-committed to canonical output
    # 0.50 - 0.84: Staged for Operator Review in UI
    # < 0.50 or Policy Gate: Clarifications Round 2 for Dana Ruiz
    confidence_high_threshold: float = float(os.getenv("CONFIDENCE_HIGH_THRESHOLD", "0.85"))
    confidence_low_threshold: float = float(os.getenv("CONFIDENCE_LOW_THRESHOLD", "0.50"))
    
    # Web Server Settings
    server_host: str = os.getenv("SERVER_HOST", "0.0.0.0")
    server_port: int = int(os.getenv("SERVER_PORT", "8000"))
    
    # Foreign Exchange Benchmarks (Quarter-End FX Rates to USD for reporting)
    # Note: Dana confirmed in Slack Round 1 to convert foreign currency (EUR, CHF) to USD
    fx_rates_to_usd: Dict[str, float] = field(default_factory=lambda: {
        "USD": 1.0,
        "EUR": 1.0710,
        "CHF": 1.1140,
        "GBP": 1.2680,
        "CAD": 0.7310,
    })

    # Target Firm Dynamic Resolution
    firm_name: Optional[str] = field(default=None)

    # Telemetry and Tracing
    enable_telemetry: bool = True
    trace_service_name: str = "nevis-adk-pipeline"

    # Canonical Enum Values (Strictly matching Nevis Canonical Schema)
    HOUSEHOLD_STATUSES: tuple = ("ACTIVE", "INACTIVE", "PROSPECT")
    CLIENT_ROLES: tuple = ("PRIMARY", "SPOUSE", "DEPENDENT", "SIGNER", "OTHER")
    ACCOUNT_TYPES: tuple = ("INDIVIDUAL", "JOINT", "TRUST", "IRA", "ROTH_IRA", "CORPORATE", "OTHER")
    INTERACTION_TYPES: tuple = ("REVIEW", "PROSPECTING", "ONBOARDING", "OTHER")

    def __post_init__(self):
        env_firm = os.getenv("FIRM_NAME")
        if env_firm:
            object.__setattr__(self, "firm_name", env_firm)
            return

        slack_path = self.sources_dir / "ops_slack_thread.md"
        if slack_path.exists():
            import re
            content = slack_path.read_text(encoding="utf-8")[:1000]
            m = re.search(r"\(([^,]+),\s*(?:a\s+fictional\s+RIA|an?\s+RIA)\)", content, re.IGNORECASE)
            if m:
                object.__setattr__(self, "firm_name", m.group(1).strip())
                return

        object.__setattr__(self, "firm_name", "Target RIA Firm")

config = PipelineConfig()
