"""
Knowledge Layer & Declarative Business Rules Engine.
Extracts operational business rules from stakeholder communications (Dana Ruiz's Slack Round 1)
using Google GenAI models, generates vector embeddings with text-embedding-004, persists them
to SQLite, and provides both deterministic lookup and semantic similarity retrieval.
"""

import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple

from google.adk.agents import BaseAgent
from config import config
from pipeline.llm_client import llm_client
from pipeline.agent_tools import knowledge_db
from pipeline.telemetry import telemetry

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeRule:
    rule_id: str
    category: str
    description: str
    stakeholder: str
    source_reference: str
    scope: str
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


class KnowledgeMiningAgent(BaseAgent):
    """Google ADK agent that extracts, indexes, and retrieves institutional business rules."""

    name: str = "KnowledgeMiningAgent"
    description: str = "Extracts and retrieves institutional knowledge rules from Slack and documentation."

    def __init__(self, slack_path: Optional[Path] = None, force_refresh: bool = False, **data):
        super().__init__(**data)
        object.__setattr__(self, "rules", {})
        object.__setattr__(self, "slack_path", slack_path or (config.sources_dir / "ops_slack_thread.md"))
        self.load_rules(force_refresh=force_refresh)

    def load_rules(self, force_refresh: bool = False):
        """Loads rules from SQLite cache or extracts dynamically via LLM."""
        with telemetry.trace_agent(self.name, action="load_rules"):
            cached_rules = knowledge_db.get_all_rules()
            if cached_rules and not force_refresh:
                logger.info("Loading %d operational rules from SQLite cache.", len(cached_rules))
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

            self._extract_and_embed_rules()

    def _segment_slack_transcript(self, text: str) -> List[Dict[str, str]]:
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
                "content": text.strip(),
            })
        return segments

    def _extract_and_embed_rules(self):
        logger.info("Extracting operational rules from %s...", self.slack_path)
        if not self.slack_path.exists():
            logger.warning("Slack thread not found at %s.", self.slack_path)
            return

        slack_text = self.slack_path.read_text(encoding="utf-8")
        prompt_path = config.prompts_dir / "slack_rule_extraction.txt"
        system_prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""

        segments = self._segment_slack_transcript(slack_text)
        for seg in segments:
            thread_prompt = (
                f"Conversational Thread: {seg['thread_id']} ({seg['header']})\n\n"
                f"{seg['content']}\n\n"
                f"Extract all operational business rules decided or confirmed in this specific thread."
            )
            try:
                with telemetry.trace_tool("extract_rules_from_thread", thread_id=seg["thread_id"]):
                    data = llm_client.generate_json(system_prompt=system_prompt, user_prompt=thread_prompt)
                    extracted = data.get("rules", [])

                for item in extracted:
                    rule_id = item.get("rule_id")
                    desc = item.get("description", "")

                    embedding = None
                    try:
                        with telemetry.trace_tool("embed_rule_text", rule_id=rule_id):
                            vecs = llm_client.embed_text(desc)
                            if vecs:
                                embedding = vecs[0]
                    except Exception as exc:
                        logger.debug("Embedding skipped for rule %s: %s", rule_id, exc)

                    if embedding:
                        similar = knowledge_db.find_similar_rules(embedding, top_k=1)
                        if similar and similar[0].get("similarity", 0) >= 0.90:
                            rule_id = similar[0]["rule_id"]

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
        with telemetry.trace_tool("find_rules_by_topic", topic=topic):
            try:
                vecs = llm_client.embed_text(topic)
                if vecs:
                    similar = knowledge_db.find_similar_rules(vecs[0], top_k=top_k)
                    return [self.rules[r["rule_id"]] for r in similar if r["rule_id"] in self.rules]
            except Exception as e:
                logger.debug("Semantic rule search fallback: %s", e)

            matches = []
            for r in self.rules.values():
                if any(term in r.description.lower() or term in r.category.lower() for term in topic.lower().split()):
                    matches.append(r)
            return matches[:top_k]

    def map_client_status(self, raw_status: str) -> Tuple[str, List[str], Optional[KnowledgeRule]]:
        clean = raw_status.strip().title() if raw_status else "ACTIVE"
        clean_lower = clean.lower()

        # Check dynamic declarative rules
        for r in self.rules.values():
            trigger = (r.metadata.get("source_status") or r.metadata.get("source_status_tag") or "").lower()
            if trigger and trigger == clean_lower:
                target_status = r.metadata.get("target_status") or r.metadata.get("canonical_status", "ACTIVE")
                tag = r.metadata.get("additional_tag") or r.metadata.get("tag") or r.metadata.get("note")
                if tag:
                    tag = str(tag).replace("_", " ").strip()
                tags = [tag] if tag else []
                return target_status.upper(), tags, r

        if clean_lower == "legacy":
            rule = next((r for r in self.rules.values() if "legacy" in r.rule_id.lower() or "legacy" in r.description.lower()), None)
            tag = None
            if rule:
                tag = rule.metadata.get("additional_tag") or rule.metadata.get("tag")
                if tag:
                    tag = str(tag).replace("_", " ").strip()
                elif "harborline" in rule.description.lower():
                    tag = "acquired from Harborline"
            tags = [tag] if tag else ["acquired from Harborline"]
            return "ACTIVE", tags, rule
        elif clean_lower in ("prospect", "lead"):
            return "PROSPECT", [], None
        elif clean_lower in ("former", "churned", "inactive"):
            return "INACTIVE", [], None
        elif clean_lower in ("active", "client"):
            return "ACTIVE", [], None
        else:
            return "ACTIVE", [f"raw_status:{clean}"], None

    def is_departed_staff(self, name: str) -> bool:
        if not name:
            return False
        name_lower = name.lower().strip()
        for r in self.rules.values():
            if r.category == "DEPARTED_STAFF":
                candidates = []
                for k in ("staff_identifier", "full_name", "staff_name"):
                    if k in r.metadata:
                        candidates.append(r.metadata[k])
                if "departed_staff_names" in r.metadata:
                    candidates.extend(r.metadata["departed_staff_names"])

                for cand in candidates:
                    cand_lower = str(cand).lower().strip()
                    if cand_lower and (cand_lower in name_lower or name_lower in cand_lower):
                        return True
                if name_lower in r.description.lower():
                    return True
        return False

    def find_deduplication_rule(self, entity_name: str) -> Optional[KnowledgeRule]:
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

    def convert_currency_to_usd(self, currency: str, amount: float) -> Tuple[float, float, str]:
        curr = currency.upper().strip() if currency else "USD"
        if curr in config.fx_rates_to_usd:
            rate = config.fx_rates_to_usd[curr]
            reasoning = f"Converted {amount:,.2f} {curr} to USD @ {rate:.4f} (benchmark rate)"
        else:
            rate = 1.0
            logger.warning("Unconfigured currency '%s' encountered. Assuming parity 1.0; review recommended.", curr)
            reasoning = f"Unconfigured currency '{curr}'; assumed parity 1.0 pending rate verification."
        usd_val = round(amount * rate, 2)
        return usd_val, rate, reasoning


# Backward compatibility alias
KnowledgeEngine = KnowledgeMiningAgent
