"""
Central Agent Tools & Knowledge Persistence Layer for Nevis Platform.
Provides deterministic data lookups, FX calculations, SQLite vector storage,
and inter-agent delegation primitives.
"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from config import config

logger = logging.getLogger(__name__)


class KnowledgeStoreDB:
    """
    SQLite-backed knowledge and vector store for local execution.
    Caches extracted business rules and text-embedding-004 vectors.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or config.knowledge_db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_rules (
                    rule_id TEXT PRIMARY KEY,
                    category TEXT,
                    description TEXT,
                    stakeholder TEXT,
                    source_reference TEXT,
                    scope TEXT,
                    metadata_json TEXT,
                    embedding_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def save_rule(
        self,
        rule_id: str,
        category: str,
        description: str,
        stakeholder: str,
        source_reference: str,
        scope: str,
        metadata: Dict[str, Any],
        embedding: Optional[List[float]] = None,
    ):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO knowledge_rules (
                    rule_id, category, description, stakeholder, source_reference, scope, metadata_json, embedding_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rule_id,
                category,
                description,
                stakeholder,
                source_reference,
                scope,
                json.dumps(metadata),
                json.dumps(embedding) if embedding else None,
            ))
            conn.commit()

    def get_all_rules(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM knowledge_rules")
            rows = cursor.fetchall()
            results = []
            for r in rows:
                results.append({
                    "rule_id": r["rule_id"],
                    "category": r["category"],
                    "description": r["description"],
                    "stakeholder": r["stakeholder"],
                    "source_reference": r["source_reference"],
                    "scope": r["scope"],
                    "metadata": json.loads(r["metadata_json"]) if r["metadata_json"] else {},
                    "embedding": json.loads(r["embedding_json"]) if r["embedding_json"] else None,
                })
            return results

    def find_similar_rules(self, query_vector: List[float], top_k: int = 3) -> List[Dict[str, Any]]:
        """Cosine similarity search against stored rule embeddings."""
        rules = self.get_all_rules()
        scored_rules = []

        import math

        def cosine_similarity(v1: List[float], v2: List[float]) -> float:
            if not v1 or not v2 or len(v1) != len(v2):
                return 0.0
            dot = sum(a * b for a, b in zip(v1, v2))
            mag1 = math.sqrt(sum(a * a for a in v1))
            mag2 = math.sqrt(sum(b * b for b in v2))
            if mag1 == 0 or mag2 == 0:
                return 0.0
            return dot / (mag1 * mag2)

        for r in rules:
            if r.get("embedding"):
                sim = cosine_similarity(query_vector, r["embedding"])
                scored_rules.append((sim, r))

        scored_rules.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored_rules[:top_k]]


# Singleton knowledge store instance
knowledge_db = KnowledgeStoreDB()
