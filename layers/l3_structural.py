from __future__ import annotations

from typing import Any

import numpy as np
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    from layers.l1_surface import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


SCHEMAS: list[dict[str, str]] = [
    {
        "name": "Resource Exhaustion",
        "description": "CPU or memory saturation on a host or service, leading to queue delays or out-of-memory errors.",
        "keywords": "cpu, memory, ram, oom, limit, exhaustion, utilization, disk, storage, host, server, maxmemory, swap",
        "exemplar": "Host memory usage exceeds limit, causing out of memory errors and server slowdowns.",
        "color": "#EF4444",
    },
    {
        "name": "Cache Saturation",
        "description": "Redis or Memcached memory usage spikes, leading to eviction cascades, hit ratio drops, and downstream database lag.",
        "keywords": "cache, redis, memcached, eviction, hit ratio, keys, memory usage, cache miss, saturation, eviction policy",
        "exemplar": "Redis memory reaches maxmemory limit, eviction policy active, hit ratio drops, database connections spike.",
        "color": "#3B82F6",
    },
    {
        "name": "Cascading Failure",
        "description": "Upstream service timeout triggering thread exhaustion and connection pool failures in downstream components.",
        "keywords": "cascade, downstream, pool, exhaustion, connections, queue, thread, timeout, database pool, dependency cascade",
        "exemplar": "Database slow query blocks connection pool, causing upstream APIs to exhaust worker threads.",
        "color": "#F59E0B",
    },
    {
        "name": "Network Partition",
        "description": "Intermittent network dropouts or packet loss between services, appearing as high latency or connect timeouts.",
        "keywords": "network, partition, packet loss, connect timeout, connection reset, connection dropped, interface, latency",
        "exemplar": "Packet loss between payment gateway and DB host causes database timeouts and retries.",
        "color": "#EC4899",
    },
    {
        "name": "Dependency Failure",
        "description": "Third-party APIs or external integrations failing, raising alerts in the primary API layer.",
        "keywords": "external api, dependency, third party, integration, provider, oauth, stripe, payment gateway, external timeout",
        "exemplar": "Stripe payment service is unreachable, causing checkout operations to fail and raise alert errors.",
        "color": "#8B5CF6",
    },
    {
        "name": "Traffic Spike",
        "description": "Unusual volume spikes leading to request buffering and high queue wait times across all system layers.",
        "keywords": "traffic, spike, surge, requests, rps, volume, buffer, queue lag, bottleneck, throughput, load test",
        "exemplar": "A sudden 10x surge in user traffic overwhelms the API server, creating high request queue wait times.",
        "color": "#10B981",
    },
    {
        "name": "Configuration Drift",
        "description": "Settings or deployment versions changing, causing performance degradation after updates.",
        "keywords": "config, settings, deployment, update, release, version change, environment variables, yaml, flag, drift",
        "exemplar": "A misconfigured environment variable setting after a deployment causes cache connection failures.",
        "color": "#06B6D4",
    },
]


class L3StructuralEngine:
    """Structural pattern matcher over a fixed schema geometry."""

    def __init__(self, model: SentenceTransformer | None = None) -> None:
        self.model = model or SentenceTransformer("all-mpnet-base-v2")
        exemplars = [schema["exemplar"] for schema in SCHEMAS]
        self.schema_vectors = np.asarray(
            self.model.encode(exemplars, normalize_embeddings=True, show_progress_bar=False),
            dtype=float,
        )

    def match_pattern(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        if not query.strip():
            return []
        query_vector = np.asarray(
            self.model.encode(query, normalize_embeddings=True, show_progress_bar=False),
            dtype=float,
        ).reshape(1, -1)
        scores = cosine_similarity(query_vector, self.schema_vectors)[0]
        matches: list[dict[str, Any]] = []
        for idx, score in enumerate(scores):
            if float(score) > 0.30:
                schema = SCHEMAS[idx]
                matches.append(
                    {
                        "name": schema["name"],
                        "description": schema["description"],
                        "confidence": round(float(score), 3),
                        "color": schema["color"],
                        "keywords": schema["keywords"],
                    }
                )
        matches.sort(key=lambda item: item["confidence"], reverse=True)
        return matches[:top_k]

    def list_schemas(self) -> list[dict[str, str]]:
        return [dict(schema) for schema in SCHEMAS]
