"""
Knowledge Layer & Declarative Business Rules Engine.
Extracts operational business rules from stakeholder communications (Dana Ruiz's Slack Round 1)
using Google Gemini, generates vector embeddings with text-embedding-004, persists them
to SQLite, and provides both deterministic lookup and semantic similarity retrieval.
"""

import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from config import config
from pipeline.llm_client import llm_client
from pipeline.agent_tools import knowledge_db

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeRule:
    rule_id: str
    category: str
    description: str
    stakeholder: str
    source_reference: str
    scope: str  # "CLIENT_SPECIFIC" | "CROSS_CLIENT_REUSABLE"
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "category": self.category,
            "description": self.description,
            "stakeholder": self.stakeholder,
            "source_reference": self.source_reference,
            "scope": self.scope,
            "metadata": self.metadata,
        }


class KnowledgeEngine:
    def __init__(self, slack_path: Optional[Path] = None, force_refresh: bool = False):
        self.rules: Dict[str, KnowledgeRule] = {}
        self.slack_path = slack_path or (config.sources_dir / "ops_slack_thread.md")
        self.load_rules(force_refresh=force_refresh)

    def load_rules(self, force_refresh: bool = False):
        """
        Loads rules from local SQLite cache if available; otherwise uses LLM
        to extract rules from the Slack conversation and embed them with Google text-embedding-004.
        """
        cached_rules = knowledge_db.get_all_rules()
        if cached_rules and not force_refresh:
            logger.info("Loading %d operational rules from SQLite knowledge cache.", len(cached_rules))
            for r in cached_rules:
                rule = KnowledgeRule(
                    rule_id=r["rule_id"],
                    category=r["category"],
                    description=r["description"],
                    stakeholder=r["stakeholder"],
                    source_reference=r["source_reference"],
                    scope=r["scope"],
                    metadata=r["metadata"],
                    embedding=r.get("embedding"),
                )
                self.rules[rule.rule_id] = rule
            return

        # Extract rules dynamically using LLM
        self._extract_and_embed_rules()

    def _extract_and_embed_rules(self):
        """Sends raw Slack export to Gemini to extract operational rules, then vector-embeds them."""
        logger.info("Extracting operational rules from %s via Gemini...", self.slack_path)
        if not self.slack_path.exists():
            logger.warning("Slack thread not found at %s. Initializing empty knowledge engine.", self.slack_path)
            return

        slack_text = self.slack_path.read_text(encoding="utf-8")
        prompt_path = config.prompts_dir / "slack_rule_extraction.txt"
        system_prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""

        try:
            data = llm_client.generate_json(system_prompt=system_prompt, user_prompt=slack_text)
            extracted = data.get("rules", [])
            logger.info("LLM extracted %d business rules from Slack thread.", len(extracted))

            for item in extracted:
                rule_id = item.get("rule_id")
                desc = item.get("description", "")
                
                # Generate embedding with Google text-embedding-004
                embedding = None
                try:
                    vecs = llm_client.embed_text(desc)
                    if vecs:
                        embedding = vecs[0]
                except Exception as e:
                    logger.warning("Could not generate embedding for rule %s: %s", rule_id, e)

                rule = KnowledgeRule(
                    rule_id=rule_id,
                    category=item.get("category", "GENERAL_POLICY"),
                    description=desc,
                    stakeholder=item.get("stakeholder", "Dana Ruiz (Head of Operations)"),
                    source_reference=item.get("source_reference", str(self.slack_path)),
                    scope=item.get("scope", "CLIENT_SPECIFIC"),
                    metadata=item.get("metadata", {}),
                    embedding=embedding,
                )
                self.rules[rule.rule_id] = rule

                # Persist to SQLite
                knowledge_db.save_rule(
                    rule_id=rule.rule_id,
                    category=rule.category,
                    description=rule.description,
                    stakeholder=rule.stakeholder,
                    source_reference=rule.source_reference,
                    scope=rule.scope,
                    metadata=rule.metadata,
                    embedding=rule.embedding,
                )

        except Exception as e:
            logger.error("Failed to extract rules via LLM: %s", e)
            raise

    def register_rule(self, rule: KnowledgeRule):
        self.rules[rule.rule_id] = rule
        knowledge_db.save_rule(
            rule_id=rule.rule_id,
            category=rule.category,
            description=rule.description,
            stakeholder=rule.stakeholder,
            source_reference=rule.source_reference,
            scope=rule.scope,
            metadata=rule.metadata,
            embedding=rule.embedding,
        )

    def get_all_rules(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self.rules.values()]

    def get_rule(self, rule_id: str) -> Optional[KnowledgeRule]:
        return self.rules.get(rule_id)

    def find_rules_by_topic(self, topic: str, top_k: int = 2) -> List[KnowledgeRule]:
        """Performs semantic vector search against encoded business rules."""
        try:
            vecs = llm_client.embed_text(topic)
            if vecs:
                similar = knowledge_db.find_similar_rules(vecs[0], top_k=top_k)
                return [self.rules[r["rule_id"]] for r in similar if r["rule_id"] in self.rules]
        except Exception as e:
            logger.debug("Semantic rule search fallback: %s", e)

        # Fallback to category keyword matching
        topic_lower = topic.lower()
        matches = []
        for r in self.rules.values():
            if any(k in topic_lower for k in [r.category.lower(), r.rule_id.lower(), r.description.lower()]):
                matches.append(r)
        return matches[:top_k]

    def map_client_status(self, raw_status: str) -> Tuple[str, List[str], Optional[KnowledgeRule]]:
        """
        Applies status normalization rules.
        e.g. 'Legacy' -> ('ACTIVE', ['acquired from Harborline'], rule)
             'Prospect' -> ('PROSPECT', [], None)
             'Active' -> ('ACTIVE', [], None)
        """
        clean = raw_status.strip().title() if raw_status else "ACTIVE"

        if clean.lower() == "legacy":
            # Match any legacy/harborline rule
            rule = next((r for r in self.rules.values() if "harborline" in r.rule_id.lower() or "legacy" in r.rule_id.lower()), None)
            return "ACTIVE", ["acquired from Harborline"], rule
        elif clean.lower() in ("prospect", "lead"):
            return "PROSPECT", [], None
        elif clean.lower() in ("former", "churned", "inactive"):
            return "INACTIVE", [], None
        elif clean.lower() in ("active", "client"):
            return "ACTIVE", [], None
        else:
            return "ACTIVE", [f"raw_status:{clean}"], None

    def is_departed_staff(self, name: str) -> bool:
        if not name:
            return False
        # Match departed staff rule
        departed_rule = next((r for r in self.rules.values() if r.category == "DEPARTED_STAFF" or "novak" in r.rule_id.lower()), None)
        targets = ["novak", "anna novak", "a. novak"]
        if departed_rule and departed_rule.metadata.get("departed_staff_names"):
            targets.extend([t.lower() for t in departed_rule.metadata["departed_staff_names"]])
        return any(t in name.lower() for t in targets)

    def is_known_duplicate_petrov(self, name: str) -> bool:
        if not name:
            return False
        clean = name.lower().replace(",", " ").strip()
        return "petrov" in clean and "dmitri" in clean

    def convert_currency_to_usd(self, currency: str, amount: float) -> Tuple[float, float, str]:
        """
        Converts amount from source currency to USD using benchmark quarter-end FX rates.
        Returns: (usd_amount, fx_rate, reasoning)
        """
        curr = currency.upper().strip() if currency else "USD"
        rate = config.fx_rates_to_usd.get(curr, 1.0)
        usd_val = round(amount * rate, 2)
        reasoning = f"Converted {amount:,.2f} {curr} to USD @ {rate:.4f} (Q2 2025 benchmark rate)"
        return usd_val, rate, reasoning
