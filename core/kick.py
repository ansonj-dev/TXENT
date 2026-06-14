from __future__ import annotations

from typing import Any
import numpy as np
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    from layers.l1_surface import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

class KickDetector:
    """
    Detects contradictions between surface alert symptoms and deep structural patterns.
    Triggers when a surface alert represents a downstream symptom rather than the true root cause.
    """

    def __init__(self, model: SentenceTransformer, threshold: float = 0.42) -> None:
        self.model = model
        self.threshold = threshold

    def check(self, query: str, l1_results: list[dict[str, Any]], l3_schemas: list[dict[str, Any]]) -> dict[str, Any]:
        if not l1_results or not l3_schemas:
            return {
                "fired": False,
                "divergence": 0.0,
                "contradiction_score": 0.0,
                "message": "Insufficient data for Kick check",
                "reason": "No L1 or L3 data matching the incident context.",
                "severity": "none",
                "threshold": self.threshold,
            }

        # 1. Calculate standard vector divergence (1.0 - cosine similarity of centroids)
        l1_texts = [str(item.get("text", "")).strip() for item in l1_results if str(item.get("text", "")).strip()]
        l3_texts = [
            str(item.get("description", "")).strip()
            for item in l3_schemas
            if str(item.get("description", "")).strip()
        ]
        
        if not l1_texts or not l3_texts:
            return {
                "fired": False,
                "divergence": 0.0,
                "contradiction_score": 0.0,
                "message": "Insufficient data for Kick check",
                "reason": "No text content found in L1 or L3 search results.",
                "severity": "none",
                "threshold": self.threshold,
            }

        l1_vectors = np.asarray(self.model.encode(l1_texts, normalize_embeddings=True, show_progress_bar=False), dtype=float)
        l3_vectors = np.asarray(self.model.encode(l3_texts, normalize_embeddings=True, show_progress_bar=False), dtype=float)
        l1_centroid = np.mean(l1_vectors, axis=0).reshape(1, -1)
        l3_centroid = np.mean(l3_vectors, axis=0).reshape(1, -1)
        
        similarity = float(cosine_similarity(l1_centroid, l3_centroid)[0][0])
        divergence = round(1.0 - similarity, 3)

        # 2. Calculate semantic contradiction score (rules comparing symptoms vs root causes)
        q_lower = query.lower()
        matched_l3_names = [p.get("name", "") for p in l3_schemas]
        
        semantic_contradiction = 0.0
        reason = "Surface facts align with structural patterns."

        # Alert is Database Timeout but L3 is Cache Saturation
        if ("db" in q_lower or "database" in q_lower or "timeout" in q_lower or "latency" in q_lower) and "Cache Saturation" in matched_l3_names:
            semantic_contradiction = 0.85
            reason = "Surface alert indicates a database timeout/latency issue, but historical patterns suggest Cache Saturation may be the true downstream culprit."
        
        # Alert is Database Timeout but L3 is Configuration Drift
        elif ("db" in q_lower or "database" in q_lower or "timeout" in q_lower) and "Configuration Drift" in matched_l3_names:
            semantic_contradiction = 0.90
            reason = "Surface alert suggests database connectivity failures, but historical patterns point to recent Configuration Drift (misconfigured deployment)."

        # Alert is Latency/Error but L3 is Dependency Failure
        elif ("latency" in q_lower or "error" in q_lower) and "Dependency Failure" in matched_l3_names:
            semantic_contradiction = 0.80
            reason = "Surface alert reports high API error rates or latency, but historical patterns suggest an upstream Dependency Failure."

        # Combine vector divergence and semantic contradiction
        contradiction_score = max(divergence, semantic_contradiction)
        fired = contradiction_score > self.threshold

        if not fired:
            severity = "none"
            message = "Layers consistent - surface symptoms align with structural pattern"
        elif contradiction_score > 0.75:
            severity = "critical"
            message = "Critical contradiction - surface alert appears to be a downstream symptom"
        else:
            severity = "medium"
            message = "Moderate conflict - surface alert partially diverges from structural pattern"

        return {
            "fired": fired,
            "divergence": divergence,
            "contradiction_score": contradiction_score,
            "severity": severity,
            "message": message,
            "reason": reason,
            "threshold": self.threshold,
        }
