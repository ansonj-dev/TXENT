from __future__ import annotations

import time
import uuid
import re
from typing import Any

import numpy as np

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    HAS_QDRANT = True
except ImportError:
    HAS_QDRANT = False
    
    class MockPointStruct:
        def __init__(self, id, vector, payload):
            self.id = id
            self.vector = vector
            self.payload = payload

    class MockQdrantClient:
        def __init__(self, location: str = ":memory:"):
            self.collections = {}

        def recreate_collection(self, collection_name, vectors_config):
            self.collections[collection_name] = []

        def upsert(self, collection_name, points):
            existing = self.collections.setdefault(collection_name, [])
            point_ids = {p.id for p in existing}
            for p in points:
                if p.id in point_ids:
                    self.collections[collection_name] = [x if x.id != p.id else p for x in self.collections[collection_name]]
                else:
                    self.collections[collection_name].append(p)

        def search(self, collection_name, query_vector, limit=5, with_payload=True):
            points = self.collections.get(collection_name, [])
            scored_points = []
            for p in points:
                sim = self._cosine_similarity(query_vector, p.vector)
                scored_points.append((p, sim))
            scored_points.sort(key=lambda x: x[1], reverse=True)
            
            class Hit:
                def __init__(self, id, payload, score):
                    self.id = id
                    self.payload = payload
                    self.score = score
            return [Hit(p.id, p.payload, score) for p, score in scored_points[:limit]]

        def scroll(self, collection_name, limit=128, offset=None, with_payload=True, with_vectors=False):
            points = self.collections.get(collection_name, [])
            start_idx = int(offset) if offset else 0
            end_idx = start_idx + limit
            sliced = points[start_idx:end_idx]
            next_offset = str(end_idx) if end_idx < len(points) else None
            return sliced, next_offset

        def count(self, collection_name, exact=True):
            class CountResult:
                def __init__(self, count):
                    self.count = count
            return CountResult(len(self.collections.get(collection_name, [])))

        def set_payload(self, collection_name, payload, points):
            all_points = self.collections.get(collection_name, [])
            target_ids = set(points)
            for p in all_points:
                if p.id in target_ids:
                    p.payload.update(payload)

        def delete(self, collection_name, points_selector):
            filter_source = None
            try:
                filter_source = points_selector.filter.must[0].match.value
            except Exception:
                pass
            
            if filter_source:
                before = len(self.collections.get(collection_name, []))
                self.collections[collection_name] = [p for p in self.collections.get(collection_name, []) if p.payload.get("source") != filter_source]
                after = len(self.collections.get(collection_name, []))
                return before - after
            return 0

        def _cosine_similarity(self, v1, v2):
            a = np.array(v1)
            b = np.array(v2)
            dot = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return float(dot / (norm_a * norm_b))

    QdrantClient = MockQdrantClient
    class mock_models:
        PointStruct = MockPointStruct
        class Distance:
            COSINE = "cosine"
        class VectorParams:
            def __init__(self, size, distance):
                self.size = size
                self.distance = distance
        class FilterSelector:
            def __init__(self, filter):
                self.filter = filter
        class Filter:
            def __init__(self, must):
                self.must = must
        class FieldCondition:
            def __init__(self, key, match):
                self.key = key
                self.match = match
        class MatchValue:
            def __init__(self, value):
                self.value = value
    models = mock_models

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    class MockSentenceTransformer:
        def __init__(self, model_name):
            pass

        def encode(self, texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False):
            if isinstance(texts, str):
                return self._encode_text(texts)
            return [self._encode_text(t) for t in texts]

        def _encode_text(self, text):
            vector = np.zeros(768)
            words = re.findall(r'\w+', text.lower())
            for w in words:
                h = hash(w) % 768
                vector[h] += 1.0
            norm = np.linalg.norm(vector)
            if norm > 0:
                vector = vector / norm
            return vector.tolist()
            
    SentenceTransformer = MockSentenceTransformer


class L1SurfaceEngine:
    """Surface memory backed by in-memory Qdrant vector retrieval."""

    COLLECTION_NAME = "l1_surface"
    VECTOR_SIZE = 768

    def __init__(self, model: SentenceTransformer | None = None) -> None:
        self.model = model or SentenceTransformer("all-mpnet-base-v2")
        self.client = QdrantClient(":memory:")
        self._create_collection()

    def _create_collection(self) -> None:
        self.client.recreate_collection(
            collection_name=self.COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=self.VECTOR_SIZE,
                distance=models.Distance.COSINE,
            ),
        )

    def clear(self) -> None:
        self._create_collection()

    @staticmethod
    def _chunk_text(text: str, chunk_words: int = 400, overlap_words: int = 50) -> list[str]:
        words = text.split()
        if not words:
            return []

        chunks: list[str] = []
        step = max(1, chunk_words - overlap_words)
        for start in range(0, len(words), step):
            chunk = " ".join(words[start : start + chunk_words]).strip()
            if chunk:
                chunks.append(chunk)
            if start + chunk_words >= len(words):
                break
        return chunks

    def ingest(self, text: str, source: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        clean_text = text.strip()
        if not clean_text:
            return {"chunks_ingested": 0, "source": source}

        chunks = self._chunk_text(clean_text)
        if not chunks:
            return {"chunks_ingested": 0, "source": source}

        vectors = self.model.encode(
            chunks,
            batch_size=32,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        now = time.time()
        
        meta_base = {
            "source": source,
            "depth_score": 0.0,
            "access_count": 0,
            "timestamp": now,
            "layer": "L1",
            "incident_id": None,
            "severity": "info",
            "service": "unknown",
            "environment": "production"
        }
        if metadata:
            meta_base.update(metadata)

        points = []
        for chunk, vector in zip(chunks, vectors):
            payload = dict(meta_base)
            payload["text"] = chunk
            points.append(
                models.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=np.asarray(vector, dtype=float).tolist(),
                    payload=payload,
                )
            )
        self.client.upsert(collection_name=self.COLLECTION_NAME, points=points)
        return {"chunks_ingested": len(points), "source": source}

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        if not query.strip():
            return []

        query_vector = self.model.encode(
            query,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        hits = self._search(np.asarray(query_vector, dtype=float).tolist(), top_k)
        results: list[dict[str, Any]] = []

        for hit in hits:
            payload = dict(hit.payload or {})
            access_count = int(payload.get("access_count", 0)) + 1
            depth_score = float(payload.get("depth_score", 0.0))
            if access_count > 5:
                depth_score = min(1.0, depth_score + 0.1)

            self.client.set_payload(
                collection_name=self.COLLECTION_NAME,
                payload={"access_count": access_count, "depth_score": depth_score},
                points=[hit.id],
            )

            results.append(
                {
                    "text": str(payload.get("text", "")),
                    "score": round(float(hit.score), 4),
                    "source": str(payload.get("source", "unknown")),
                    "depth_score": round(depth_score, 3),
                    "access_count": access_count,
                    "incident_id": payload.get("incident_id"),
                    "timestamp": payload.get("timestamp"),
                    "severity": payload.get("severity"),
                    "service": payload.get("service"),
                    "environment": payload.get("environment"),
                }
            )
        return results

    def _search(self, query_vector: list[float], top_k: int) -> list[Any]:
        try:
            return self.client.search(
                collection_name=self.COLLECTION_NAME,
                query_vector=query_vector,
                limit=top_k,
                with_payload=True,
            )
        except AttributeError:
            response = self.client.query_points(
                collection_name=self.COLLECTION_NAME,
                query=query_vector,
                limit=top_k,
                with_payload=True,
            )
            return list(response.points)

    def stats(self) -> dict[str, Any]:
        count = self.client.count(collection_name=self.COLLECTION_NAME, exact=True).count
        if count == 0:
            return {"total_chunks": 0, "avg_depth_score": 0.0, "sources": []}

        depth_scores: list[float] = []
        source_counts: dict[str, int] = {}
        offset = None
        while True:
            points, offset = self.client.scroll(
                collection_name=self.COLLECTION_NAME,
                limit=128,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                payload = point.payload or {}
                depth_scores.append(float(payload.get("depth_score", 0.0)))
                source = str(payload.get("source", "unknown"))
                source_counts[source] = source_counts.get(source, 0) + 1
            if offset is None:
                break

        avg_depth = float(np.mean(depth_scores)) if depth_scores else 0.0
        sources = [
            {"source": source, "chunks": chunks}
            for source, chunks in sorted(source_counts.items(), key=lambda item: item[1], reverse=True)
        ]
        return {"total_chunks": int(count), "avg_depth_score": round(avg_depth, 3), "sources": sources}

    def export_points(self) -> list[dict[str, Any]]:
        exported: list[dict[str, Any]] = []
        offset = None
        while True:
            points, offset = self.client.scroll(
                collection_name=self.COLLECTION_NAME,
                limit=128,
                offset=offset,
                with_payload=True,
                with_vectors=True,
            )
            for point in points:
                vector = point.vector
                if isinstance(vector, dict):
                    vector = next(iter(vector.values()))
                exported.append(
                    {
                        "id": str(point.id),
                        "vector": list(vector or []),
                        "payload": dict(point.payload or {}),
                    }
                )
            if offset is None:
                break
        return exported

    def import_points(self, points: list[dict[str, Any]]) -> int:
        self.clear()
        if not points:
            return 0

        point_structs = [
            models.PointStruct(
                id=point["id"],
                vector=point["vector"],
                payload=point.get("payload", {}),
            )
            for point in points
            if point.get("id") and point.get("vector")
        ]
        if point_structs:
            self.client.upsert(collection_name=self.COLLECTION_NAME, points=point_structs)
        return len(point_structs)

    def delete_source(self, source: str) -> int:
        count_before = self.client.count(collection_name=self.COLLECTION_NAME, exact=True).count
        self.client.delete(
            collection_name=self.COLLECTION_NAME,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="source",
                            match=models.MatchValue(value=source),
                        )
                    ]
                )
            ),
        )
        count_after = self.client.count(collection_name=self.COLLECTION_NAME, exact=True).count
        return count_before - count_after
