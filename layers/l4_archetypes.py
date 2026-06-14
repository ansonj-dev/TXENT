from __future__ import annotations

from typing import Any

ARCHETYPES = [
    {
        "id": "arch_cache_masking_db",
        "name": "Cache Saturation Masked as DB Failure",
        "wisdom": "Cache failures (like Redis maxmemory limit or evictions) frequently appear as database failures because all client read requests are forced to fall back to the slower SQL store, exhausting its connection pool.",
        "trigger_conditions": ["Cache Saturation", "Cascading Failure"],
        "remediation_actions": [
            {"id": "scale_redis", "title": "Scale Redis cluster memory", "type": "automatable"},
            {"id": "clear_keys", "title": "Clear expired volatile keys", "type": "automatable"},
            {"id": "db_pool_increase", "title": "Increase database connection pool size", "type": "manual"}
        ]
    },
    {
        "id": "arch_traffic_overflow",
        "name": "Traffic Surge Overwhelming Frontend Cache First",
        "wisdom": "A massive traffic spike typically overwhelms cache layers and buffers before causing slow queries in databases. Resolving this requires throttling at the API gateway rather than database optimization.",
        "trigger_conditions": ["Traffic Spike", "Resource Exhaustion"],
        "remediation_actions": [
            {"id": "enable_rate_limiting", "title": "Enable API Gateway Rate Limiting", "type": "automatable"},
            {"id": "scale_api", "title": "Autoscale API Gateway nodes", "type": "automatable"}
        ]
    },
    {
        "id": "arch_deployment_drift",
        "name": "Configuration Drift Latency Premonition",
        "wisdom": "Misconfigured environment variables or deployment updates often create latency spikes (due to connection retries or timeout defaults) before they manifest as outright service crash errors.",
        "trigger_conditions": ["Configuration Drift", "Resource Exhaustion"],
        "remediation_actions": [
            {"id": "rollback_deploy", "title": "Rollback recent deployment", "type": "automatable"},
            {"id": "audit_env", "title": "Audit environment variable drifts", "type": "manual"}
        ]
    },
    {
        "id": "arch_network_cascade",
        "name": "Network Partition Inducing Thread Pools Exhaustion",
        "wisdom": "Intermittent network partitions or packet loss cause socket read timeouts, locking up worker threads on caller services and cascading into thread exhaustion across the API gateway.",
        "trigger_conditions": ["Network Partition", "Cascading Failure"],
        "remediation_actions": [
            {"id": "drain_partitioned_node", "title": "Drain traffic from affected zone", "type": "automatable"},
            {"id": "configure_circuit_breaker", "title": "Enable circuit breakers on dependency", "type": "manual"}
        ]
    }
]

class L4OperationalArchetypes:
    """
    L4 Operational Archetypes layer.
    Stores operational priors (deep system wisdom) and matches them against L3 and incident metrics.
    """

    def __init__(self) -> None:
        self.archetypes = ARCHETYPES

    def match_archetype(self, l3_patterns: list[dict[str, Any]], metrics: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """
        Matches active structural patterns (L3) and metrics against operational archetypes.
        """
        matched = []
        matched_names = {p.get("name") for p in l3_patterns if p.get("confidence", 0) > 0.3}

        for arch in self.archetypes:
            # Match based on L3 conditions
            match_score = 0.0
            triggers = arch["trigger_conditions"]
            
            # Simple overlap scoring
            matches_trigger = [t for t in triggers if t in matched_names]
            if len(matches_trigger) > 0:
                match_score = len(matches_trigger) / len(triggers)

            # Extra weight if specific metrics indicate this pattern
            if metrics:
                # E.g. Redis memory > 90% and DB connections > 35 -> Cache Saturation Masked as DB Failure
                if arch["id"] == "arch_cache_masking_db":
                    redis_mem = metrics.get("redis-cache", {}).get("memory", 0)
                    db_conns = metrics.get("postgres-db", {}).get("connections", 0)
                    if redis_mem > 90 and db_conns > 30:
                        match_score = max(match_score, 0.95)
                elif arch["id"] == "arch_deployment_drift":
                    # If drift is active and latency is high
                    pay_latency = metrics.get("payment-api", {}).get("latency", 0)
                    if "Configuration Drift" in matched_names and pay_latency > 500:
                        match_score = max(match_score, 0.9)

            if match_score > 0.4:
                copy = dict(arch)
                copy["match_score"] = round(match_score, 2)
                matched.append(copy)

        # Sort by match score
        matched.sort(key=lambda x: x["match_score"], reverse=True)
        return matched

    def list_archetypes(self) -> list[dict[str, Any]]:
        return self.archetypes
