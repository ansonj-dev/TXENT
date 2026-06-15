from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    from layers.l1_surface import SentenceTransformer

from core.kick import KickDetector
from layers.l1_surface import L1SurfaceEngine
from layers.l2_associative import L2AssociativeEngine
from layers.l3_structural import L3StructuralEngine
from layers.l4_archetypes import L4OperationalArchetypes
from connectors.splunk import SplunkConnector
from agents.investigator import AutonomousInvestigationAgent

load_dotenv()

class TXENTOrchestrator:
    """
    Coordinates TXENT's layered memory engines, Splunk connectors,
    Kick Mechanism, and autonomous investigation agents.
    """

    def __init__(self) -> None:
        self.embedding_model_name = os.getenv("EMBEDDING_MODEL", "all-mpnet-base-v2")
        self.memory_dir = Path(os.getenv("TXENT_MEMORY_DIR", "memory_store"))
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.sources: dict[str, dict[str, Any]] = {}
        self.started_at = time.time()
        self.model = SentenceTransformer(self.embedding_model_name)
        
        # Core layers
        self.l1 = L1SurfaceEngine(model=self.model)
        self.l2 = L2AssociativeEngine()
        self.l3 = L3StructuralEngine(model=self.model)
        self.l4 = L4OperationalArchetypes()
        
        # Connectors & Agents
        self.splunk = SplunkConnector()
        self.agent = AutonomousInvestigationAgent(self.splunk)
        
        self.kick = KickDetector(
            model=self.model,
            threshold=float(os.getenv("KICK_THRESHOLD", "0.42")),
        )
        
        if os.getenv("TXENT_AUTO_LOAD", "true").lower() == "true":
            self.load_memory()

    def ingest(self, text: str, source: str = "manual", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        """Ingests raw text and telemetry into L1 and L2 layers."""
        l1_stats = self.l1.ingest(text=text, source=source, metadata=metadata)
        l2_stats = self.l2.ingest(text=text)
        chunks = int(l1_stats.get("chunks_ingested", 0))
        self._record_source(source=source, chunks=chunks, characters=len(text), kind="text")
        self._auto_save()
        return {
            "chunks_ingested": chunks,
            "source": l1_stats.get("source", source),
            "graph_nodes": int(l2_stats.get("nodes", 0)),
            "graph_edges": int(l2_stats.get("edges", 0)),
        }

    def ingest_batch(self, documents: list[dict[str, str]]) -> dict[str, Any]:
        """Ingests a batch of documents."""
        results = []
        for document in documents:
            text = str(document.get("text", ""))
            source = str(document.get("source", "batch"))
            # Extra metadata mapping if present
            metadata = {
                "incident_id": document.get("incident_id"),
                "severity": document.get("severity", "info"),
                "service": document.get("service", "unknown"),
                "environment": document.get("environment", "production")
            }
            if text.strip():
                results.append(self.ingest(text=text, source=source, metadata=metadata))
        return {
            "documents_ingested": len(results),
            "chunks_ingested": sum(int(item.get("chunks_ingested", 0)) for item in results),
            "results": results,
            "graph_nodes": self.l2.graph.number_of_nodes(),
            "graph_edges": self.l2.graph.number_of_edges(),
        }

    async def retrieve(self, query: str, kick_enabled: bool = True) -> dict[str, Any]:
        """Retrieves layered context and runs autonomous investigations if the Kick fires."""
        l1_results = self.l1.search(query, top_k=5)
        l2_results = self.l2.traverse(query, depth=2)
        l3_results = self.l3.match_pattern(query, top_k=3)
        
        # Upgraded Kick Check
        kick_result = self.kick.check(query, l1_results, l3_results) if kick_enabled else {
            "fired": False,
            "divergence": 0.0,
            "contradiction_score": 0.0,
            "severity": "none",
            "message": "Kick check disabled",
            "reason": "Kick validation was skipped by request.",
            "threshold": self.kick.threshold,
        }
        
        # Match L4 Operational Archetypes using active metrics
        metrics = self.splunk.simulation_state["metrics"]
        l4_results = self.l4.match_archetype(l3_results, metrics)
        
        # Launch Autonomous Investigation Agent if Kick fires
        agent_result = None
        if kick_result.get("fired"):
            # Increment the simulation's kick count for the dashboard
            if "kick_count" in self.splunk.simulation_state:
                self.splunk.simulation_state["kick_count"] += 1
            else:
                self.splunk.simulation_state["kick_count"] = 1
                
            # Construct standard incident payload based on query details
            incident = self.splunk.simulation_state.get("current_incident")
            if not incident:
                # Deduce metadata details from query text dynamically
                inferred_service = "payment-api"
                for s in ["redis-cache", "postgres-db", "payment-api", "auth-service", "order-service", "user-service"]:
                    if s in query.lower() or s.replace("-", " ") in query.lower():
                        inferred_service = s
                incident = {
                    "incident_id": "INC-2025-05-18-001",
                    "title": query,
                    "service": inferred_service,
                    "severity": kick_result.get("severity", "critical"),
                    "environment": "Production",
                    "source": "Splunk Alert",
                    "timestamp": time.time()
                }
            agent_result = await self.agent.investigate(incident, l3_results)

        # Apply Kick re-ranking using L2 entities and L3 patterns if Kick fires
        reranked_surface = self._kick_rerank(query, l1_results, l2_results, l3_results) if kick_result.get("fired") else []
        
        return {
            "query": query,
            "l1_surface": l1_results,
            "l2_associative": l2_results[:15],
            "l3_structural": l3_results,
            "l4_archetypes": l4_results,
            "kick": kick_result,
            "kick_reranked_surface": reranked_surface,
            "agent_investigation": agent_result,
            "graph_stats": self.l2.stats(),
        }

    def _kick_rerank(
        self,
        query: str,
        l1_results: list[dict[str, Any]],
        l2_results: list[dict[str, Any]],
        l3_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        entity_terms = [item.get("entity", "") for item in l2_results[:6]]
        schema_terms = []
        for schema in l3_results[:2]:
            schema_terms.extend(str(schema.get("keywords", "")).split(",")[:4])
        expanded_query = " ".join([query, *entity_terms, *schema_terms])
        expanded_results = self.l1.search(expanded_query, top_k=8)

        seen: set[str] = set()
        merged: list[dict[str, Any]] = []
        for item in expanded_results + l1_results:
            key = f"{item.get('source')}::{item.get('text')}"
            if key in seen:
                continue
            seen.add(key)
            copy = dict(item)
            copy["rerank_reason"] = "Kick expansion used L2 service topology and L3 operational patterns"
            merged.append(copy)
        return merged[:5]

    def build_llm_context(self, context: dict[str, Any]) -> str:
        """Assembles a prompt context for the LLM using all memory layers."""
        l1_lines = []
        for idx, item in enumerate(context.get("l1_surface", [])[:3], start=1):
            l1_lines.append(
                f"{idx}. score={item.get('score', 0)} source={item.get('source', 'unknown')} :: {item.get('text', '')}"
            )
        if not l1_lines:
            l1_lines.append("No surface facts retrieved.")

        l2_lines = []
        for idx, item in enumerate(context.get("l2_associative", [])[:5], start=1):
            l2_lines.append(f"{idx}. {item.get('entity', '')} -> {item.get('path', '')}")
        if not l2_lines:
            l2_lines.append("No related graph concepts found.")

        l3_lines = []
        for idx, item in enumerate(context.get("l3_structural", []), start=1):
            l3_lines.append(
                f"{idx}. {item.get('name', '')} confidence={item.get('confidence', 0)} :: {item.get('description', '')}"
            )
        if not l3_lines:
            l3_lines.append("No structural pattern matched above threshold.")

        l4_lines = []
        for idx, item in enumerate(context.get("l4_archetypes", []), start=1):
            l4_lines.append(
                f"{idx}. {item.get('name', '')} (Match: {int(item.get('match_score', 0)*100)}%) :: {item.get('wisdom', '')}"
            )
        if not l4_lines:
            l4_lines.append("No matching operational archetypes matched.")

        kick = context.get("kick", {})
        agent = context.get("agent_investigation", {})
        
        agent_lines = []
        if agent:
            agent_lines.append(f"Root Cause: {agent.get('root_cause')} (Confidence: {int(agent.get('confidence',0)*100)}%)")
            agent_lines.append("Gathered Evidence:")
            for e in agent.get("evidence", []):
                agent_lines.append(f"  - {e}")
            agent_lines.append("Investigation Timeline:")
            for t in agent.get("timeline", []):
                agent_lines.append(f"  [{t.get('timestamp')}] {t.get('action')}: {t.get('details')}")

        return "\n".join(
            [
                "=== TXENT LAYERED OBSERVABILITY CONTEXT ===",
                "",
                "L1 SURFACE MEMORY (Vector Logs & Alerts):",
                *l1_lines,
                "",
                "L2 ASSOCIATIVE GRAPH (Service Dependency Topology):",
                *l2_lines,
                "",
                "L3 STRUCTURAL PATTERNS (Incident Signature Layer):",
                *l3_lines,
                "",
                "L4 OPERATIONAL ARCHETYPES (Historical Wisdom Priors):",
                *l4_lines,
                "",
                "KICK DETECTOR STATUS:",
                f"Contradiction Fired: {kick.get('fired')} | Severity: {kick.get('severity')}",
                f"Divergence Score: {kick.get('divergence')} | Contradiction: {kick.get('contradiction_score')}",
                f"Causal Assessment: {kick.get('reason')}",
                "",
                *(["=== AUTONOMOUS AGENT INVESTIGATION LOGS ===", *agent_lines, ""] if agent else []),
                "Use this operational context to provide a clear explanation of the true root cause and recommended remediation.",
            ]
        )

    def get_graph_data(self, entity: str | None = None) -> dict[str, Any]:
        if entity:
            return self.l2.get_subgraph(entity, depth=2)
        return self.l2.summary_graph(limit=30)

    def list_sources(self) -> list[dict[str, Any]]:
        l1_sources = {item["source"]: item for item in self.l1.stats().get("sources", [])}
        combined = []
        for source, meta in self.sources.items():
            entry = dict(meta)
            entry["chunks"] = int(l1_sources.get(source, {}).get("chunks", entry.get("chunks", 0)))
            combined.append(entry)
        for source, item in l1_sources.items():
            if source not in self.sources:
                combined.append(
                    {
                        "source": source,
                        "chunks": item.get("chunks", 0),
                        "characters": 0,
                        "kind": "unknown",
                        "created_at": None,
                        "updated_at": None,
                    }
                )
        return sorted(combined, key=lambda item: str(item.get("updated_at") or ""), reverse=True)

    def clear_memory(self) -> dict[str, Any]:
        self.l1.clear()
        self.l2.clear()
        self.sources.clear()
        self._auto_save()
        return {"status": "cleared", "l1_stats": self.l1.stats(), "graph_stats": self.l2.stats()}

    def delete_source(self, source: str) -> dict[str, Any]:
        l1_chunks = self.l1.delete_source(source)
        if source in self.sources:
            del self.sources[source]

        self.l2.clear()
        if self.sources:
            for point in self.l1.export_points():
                text = point.get("payload", {}).get("text", "")
                if text:
                    self.l2.ingest(text)

        self._auto_save()
        return {"status": "deleted", "source": source, "chunks_deleted": l1_chunks}

    def save_memory(self, path: str | None = None) -> dict[str, Any]:
        target = Path(path) if path else self.memory_dir / "txent_memory.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "saved_at": time.time(),
            "embedding_model": self.embedding_model_name,
            "kick_threshold": self.kick.threshold,
            "sources": self.sources,
            "l1_points": self.l1.export_points(),
            "l2_graph": self.l2.export_graph(),
        }
        target.write_text(json.dumps(data), encoding="utf-8")
        return {
            "status": "saved",
            "path": str(target),
            "chunks": len(data["l1_points"]),
            "nodes": self.l2.graph.number_of_nodes(),
            "edges": self.l2.graph.number_of_edges(),
        }

    def load_memory(self, path: str | None = None) -> dict[str, Any]:
        target = Path(path) if path else self.memory_dir / "txent_memory.json"
        if not target.exists():
            return {"status": "missing", "path": str(target), "loaded": False}
        data = json.loads(target.read_text(encoding="utf-8"))
        chunks = self.l1.import_points(data.get("l1_points", []))
        graph_stats = self.l2.import_graph(data.get("l2_graph", {"nodes": [], "edges": []}))
        self.sources = {
            str(source): dict(meta)
            for source, meta in dict(data.get("sources", {})).items()
        }
        return {
            "status": "loaded",
            "path": str(target),
            "loaded": True,
            "chunks": chunks,
            "graph_stats": graph_stats,
        }

    def runtime_status(self) -> dict[str, Any]:
        return {
            "status": "ready",
            "uptime_seconds": round(time.time() - self.started_at, 2),
            "embedding_model": self.embedding_model_name,
            "spacy_model": self.l2.nlp.meta.get("name", "unknown"),
            "memory_dir": str(self.memory_dir),
            "kick_threshold": self.kick.threshold,
            "l1_stats": self.l1.stats(),
            "graph_stats": self.l2.stats(),
            "sources": self.list_sources(),
        }

    def _record_source(self, source: str, chunks: int, characters: int, kind: str) -> None:
        now = time.time()
        existing = self.sources.get(source, {})
        self.sources[source] = {
            "source": source,
            "kind": kind,
            "chunks": int(existing.get("chunks", 0)) + chunks,
            "characters": int(existing.get("characters", 0)) + characters,
            "created_at": existing.get("created_at", now),
            "updated_at": now,
        }

    def _auto_save(self) -> None:
        if os.getenv("TXENT_AUTO_SAVE", "true").lower() == "true":
            self.save_memory()

