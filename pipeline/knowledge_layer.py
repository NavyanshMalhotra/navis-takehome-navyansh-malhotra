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

    def _segment_slack_transcript(self, text: str) -> List[Dict[str, str]]:
        """
        Segments raw Slack channel exports into atomic conversational thread blocks.
        Splits by topic turns initiated by the onboarding team to ensure granular,
        scalable rule extraction without context-window overflow.
        """
        import re
        pattern = re.compile(r"(?=\*\*Alex\*\* —)", re.MULTILINE)
        raw_chunks = pattern.split(text)

        segments = []
        for i, chunk in enumerate(raw_chunks):
            chunk_clean = chunk.strip()
            if not chunk_clean or "**Dana Ruiz**" not in chunk_clean:
                continue
            first_line = chunk_clean.splitlines()[0] if chunk_clean else f"Exchange {i+1}"
            segments.append({
                "thread_id": f"THREAD-{i+1}",
                "header": first_line,
                "content": chunk_clean,
            })

        if not segments:
            segments.append({
                "thread_id": "THREAD-FULL",
                "header": "Full Thread",
                "content": text.strip()
            })
        return segments

    def _extract_and_embed_rules(self):
        """
        Extracts operational rules using a thread-segmented windowing architecture.
        Each thread is processed independently for scalable extraction, atomic provenance,
        and vector deduplication against SQLite.
        """
        logger.info("Extracting operational rules from %s via scalable thread windowing...", self.slack_path)
        if not self.slack_path.exists():
            logger.warning("Slack thread not found at %s. Initializing empty knowledge engine.", self.slack_path)
            return

        slack_text = self.slack_path.read_text(encoding="utf-8")
        prompt_path = config.prompts_dir / "slack_rule_extraction.txt"
        system_prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""

        segments = self._segment_slack_transcript(slack_text)
        logger.info("Segmented Slack channel into %d conversational threads for incremental ingestion.", len(segments))

        for seg in segments:
            thread_prompt = (
                f"Conversational Thread: {seg['thread_id']} ({seg['header']})\n\n"
                f"{seg['content']}\n\n"
                f"Extract all operational business rules decided or confirmed in this specific thread."
            )
            try:
                data = llm_client.generate_json(system_prompt=system_prompt, user_prompt=thread_prompt)
                extracted = data.get("rules", [])

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

                    # Deduplication via vector similarity against SQLite knowledge store
                    if embedding:
                        similar = knowledge_db.find_similar_rules(embedding, top_k=1)
                        if similar and similar[0].get("similarity", 0) >= 0.90:
                            existing_id = similar[0]["rule_id"]
                            logger.info("Rule '%s' matches existing rule '%s' (sim: %.2f) - updating metadata.",
                                        rule_id, existing_id, similar[0]["similarity"])
                            rule_id = existing_id

                    rule = KnowledgeRule(
                        rule_id=rule_id,
                        category=item.get("category", "GENERAL_POLICY"),
                        description=desc,
                        stakeholder=item.get("stakeholder", "Dana Ruiz (Head of Operations)"),
                        source_reference=f"sources/ops_slack_thread.md#{seg['thread_id']}",
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
                logger.error("Failed to extract rules from %s: %s", seg["thread_id"], e)

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
        matches = []
        for r in self.rules.values():
            if any(term in r.description.lower() or term in r.category.lower() for term in topic.lower().split()):
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
        """Checks if name matches any departed staff member identified in declarative rules."""
        if not name:
            return False
        name_lower = name.lower().strip()
        for r in self.rules.values():
            if r.category == "DEPARTED_STAFF":
                staff_names = [s.lower().strip() for s in r.metadata.get("departed_staff_names", [])]
                if any(s in name_lower or name_lower in s for s in staff_names if s):
                    return True
        return False

    def find_deduplication_rule(self, entity_name: str) -> Optional[KnowledgeRule]:
        """
        Dynamically finds any declarative deduplication rule matching the given entity name
        using rule metadata (entity_name, duplicate_variants) extracted from institutional lore.
        """
        if not entity_name:
            return None
        clean = entity_name.lower().replace(",", " ").strip()
        clean_tokens = set(clean.split())

        for r in self.rules.values():
            if r.category in ("ENTITY_DEDUPLICATION", "DEDUPLICATION", "DATA_HYGIENE"):
                variants = [v.lower().replace(",", " ").strip() for v in r.metadata.get("duplicate_variants", [])]
                target_entity = r.metadata.get("entity_name", "").lower().replace(",", " ").strip()
                if clean in variants or target_entity == clean:
                    return r
                if target_entity and set(target_entity.split()).issubset(clean_tokens):
                    return r
        return None

    def is_known_duplicate_petrov(self, name: str) -> bool:
        """Compatibility method delegating to dynamic find_deduplication_rule."""
        return self.find_deduplication_rule(name) is not None

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
