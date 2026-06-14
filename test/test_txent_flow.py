from __future__ import annotations

import unittest
import asyncio
from core.orchestrator import DreamWeaveOrchestrator
from connectors.splunk import SplunkConnector
from agents.investigator import AutonomousInvestigationAgent

class TestTXENTFlow(unittest.TestCase):
    """
    Integration tests for TXENT layered memory layers and agent workflows.
    """

    def setUp(self) -> None:
        # Initialize orchestrator (rebranded internally to TXENT)
        self.orchestrator = DreamWeaveOrchestrator()
        
    def test_rebranding_reloaded(self):
        """Verifies that the orchestrator initializes with rebranding variables."""
        self.assertEqual(self.orchestrator.l1.COLLECTION_NAME, "l1_surface")
        self.assertIsNotNone(self.orchestrator.splunk)
        self.assertIsNotNone(self.orchestrator.l4)
        self.assertIsNotNone(self.orchestrator.agent)

    def test_l2_baseline_topology(self):
        """Verifies that the service topology is correctly seeded on start."""
        graph = self.orchestrator.l2.graph
        self.assertTrue(graph.has_node("payment-api"))
        self.assertTrue(graph.has_node("redis-cache"))
        self.assertTrue(graph.has_node("postgres-db"))
        self.assertTrue(graph.has_edge("payment-api", "redis-cache"))

    def test_l3_observability_schemas(self):
        """Verifies L3 contains observability-focused patterns."""
        schemas = self.orchestrator.l3.list_schemas()
        schema_names = [s["name"] for s in schemas]
        self.assertIn("Cache Saturation", schema_names)
        self.assertIn("Resource Exhaustion", schema_names)
        self.assertIn("Cascading Failure", schema_names)

    def test_l4_archetypes(self):
        """Verifies L4 contains operational archetypes."""
        archetypes = self.orchestrator.l4.list_archetypes()
        self.assertGreater(len(archetypes), 0)
        arch_names = [a["name"] for a in archetypes]
        self.assertIn("Cache Saturation Masked as DB Failure", arch_names)

    def test_ingest_metadata(self):
        """Verifies metadata ingestion works in L1 Surface Memory."""
        result = self.orchestrator.ingest(
            text="Simulated Redis CPU alert spike",
            source="Splunk Alert System",
            metadata={
                "incident_id": "INC-TEST-99",
                "severity": "critical",
                "service": "redis-cache",
                "environment": "Production"
            }
        )
        self.assertEqual(result["chunks_ingested"], 1)
        
        # Verify retrieved metadata
        search_res = self.orchestrator.l1.search("Redis CPU spike", top_k=1)
        self.assertEqual(len(search_res), 1)
        self.assertEqual(search_res[0]["incident_id"], "INC-TEST-99")
        self.assertEqual(search_res[0]["severity"], "critical")
        self.assertEqual(search_res[0]["service"], "redis-cache")

    def test_splunk_simulation_incident(self):
        """Verifies Splunk simulation state spikes on anomaly trigger."""
        self.orchestrator.splunk.trigger_simulation_incident("cache_saturation")
        redis_mem = self.orchestrator.splunk.simulation_state["metrics"]["redis-cache"]["memory"]
        self.assertGreater(redis_mem, 90.0)
        
        # Reset incident
        self.orchestrator.splunk.trigger_simulation_incident("reset")
        redis_mem_reset = self.orchestrator.splunk.simulation_state["metrics"]["redis-cache"]["memory"]
        self.assertLess(redis_mem_reset, 65.0)

    def test_kick_mechanism_firing(self):
        """Verifies that the Kick detector detects contradiction and logs details."""
        # Setup L1 facts representing standard database timeout
        l1_results = [
            {"text": "PostgreSQL database connection timeout error", "source": "postgres-db", "score": 0.9}
        ]
        # Setup L3 schemas representing Cache Saturation
        l3_schemas = [
            {"name": "Cache Saturation", "description": "Redis memory reaches maxmemory limit, eviction policy active.", "confidence": 0.85}
        ]
        
        kick_res = self.orchestrator.kick.check("Database connection timeout", l1_results, l3_schemas)
        self.assertTrue(kick_res["fired"])
        self.assertEqual(kick_res["severity"], "critical")
        self.assertIn("Cache Saturation", kick_res["reason"])

    def test_agent_investigation_loop(self):
        """Verifies the async agent investigation loop runs and outputs structured details."""
        self.orchestrator.splunk.trigger_simulation_incident("cache_saturation")
        
        async def run_investigate():
            incident = self.orchestrator.splunk.simulation_state["current_incident"]
            l3_patterns = [{"name": "Cache Saturation", "confidence": 0.88}]
            return await self.orchestrator.agent.investigate(incident, l3_patterns)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            report = loop.run_until_complete(run_investigate())
            self.assertEqual(report["root_cause"], "Redis Memory Exhaustion")
            self.assertEqual(report["confidence"], 0.94)
            self.assertGreater(len(report["timeline"]), 0)
            self.assertGreater(len(report["evidence"]), 0)
            self.assertGreater(len(report["recommended_actions"]), 0)
        finally:
            loop.close()

if __name__ == "__main__":
    unittest.main()
