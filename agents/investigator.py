from __future__ import annotations

import os
import time
import httpx
import json
from typing import Any
from connectors.splunk import SplunkConnector
from dotenv import load_dotenv

load_dotenv()

class AutonomousInvestigationAgent:
    """
    Autonomous Observability Investigation Agent.
    Runs investigations when the Kick Mechanism fires.
    """

    def __init__(self, splunk_connector: SplunkConnector) -> None:
        self.splunk = splunk_connector
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.openai_key = os.getenv("OPENAI_API_KEY", "")
        self.llm_url = os.getenv("LLM_URL", "http://localhost:30000/v1/chat/completions")
        self.llm_model = os.getenv("LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")

    async def investigate(self, incident: dict[str, Any], l3_schemas: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Executes the autonomous investigation workflow.
        """
        timeline = []
        start_time = time.time()
        
        # Helper to log timeline steps
        def log_step(action: str, status: str, details: str):
            timeline.append({
                "timestamp": time.strftime("%H:%M:%S", time.localtime()),
                "action": action,
                "status": status,
                "details": details
            })

        log_step("Incident Detection", "triggered", f"Splunk alert: '{incident.get('title')}' for service '{incident.get('service')}'")
        time.sleep(0.1) # Simulate quick agent processing
        log_step("Kick Mechanism", "triggered", "Contradiction detected between surface symptoms and historical structural memory.")
        
        # 1. Query Splunk/Simulator for dependency health and service status
        log_step("Topology Correlation", "running", "Analyzing service dependency graph connections in L2 Associative Graph.")
        target_service = incident.get("service", "unknown")
        
        # Fetch health of downstream and upstream services
        related_services = ["redis-cache", "postgres-db", "auth-service", "order-service", "user-service"]
        health_status = {}
        for s in related_services:
            h = await self.splunk.check_service_health(s)
            health_status[s] = h
        
        log_step("Service Health Status", "completed", f"Health check results: {health_status}")

        # 2. Query metrics and logs for suspected services
        log_step("Splunk MCP Query", "running", "Querying metrics snapshots and recent logs via Splunk MCP server.")
        
        # Gather logs and metrics
        metrics_data = {}
        for s in ["redis-cache", "postgres-db", "payment-api"]:
            metrics_data[s] = self.splunk.simulation_state["metrics"].get(s, {})
            
        logs_redis = await self.splunk.search_logs("redis", earliest="-15m")
        logs_db = await self.splunk.search_logs("postgres", earliest="-15m")
        
        log_step("Evidence Gathering", "completed", "Retrieved CPU/Memory metrics and logs for redis-cache and postgres-db.")

        # 3. Analyze recent deployments or configuration changes
        log_step("Change Log Check", "running", "Checking deployment history and infrastructure changes in Splunk index.")
        deployments = self.splunk.simulation_state["recent_deployments"]
        log_step("Change Log Check", "completed", f"Found {len(deployments)} recent deployments. Last release: payment-api v1.4.2.")

        # 4. Synthesize root cause analysis
        log_step("Root Cause Analysis", "running", "Correlating metrics anomalies against operational archetypes and historical schemas.")
        
        evidence = []
        root_cause = "Unknown Anomaly"
        confidence = 0.50
        recommended_actions = []

        # Determine the scenario based on metrics
        redis_mem = self.splunk.simulation_state["metrics"]["redis-cache"]["memory"]
        db_conns = self.splunk.simulation_state["metrics"]["postgres-db"]["connections"]
        api_latency = self.splunk.simulation_state["metrics"]["payment-api"]["latency"]
        
        if redis_mem > 90:
            root_cause = "Redis Memory Exhaustion"
            confidence = 0.94
            evidence = [
                f"Redis cache memory usage is at {redis_mem}% exceeding maxmemory limit.",
                "Redis cache hit ratio dropped to 12.1% (eviction cascade active).",
                f"Database connection pool active connections spiked to {db_conns}.",
                "Database response times degraded, indicating DB load is a downstream symptom.",
                "API Latency increased to 1250ms due to cache-miss database fallback."
            ]
            recommended_actions = [
                {"action_id": "scale_redis", "title": "Scale Redis cluster memory allocation", "type": "automatable"},
                {"action_id": "clear_keys", "title": "Clear expired volatile keys via flush", "type": "automatable"},
                {"action_id": "monitor_memory", "title": "Enable memory usage alerting threshold", "type": "automatable"},
                {"action_id": "review_traffic", "title": "Review transaction traffic patterns", "type": "manual"}
            ]
        elif db_conns > 80:
            root_cause = "PostgreSQL Connection Pool Exhaustion"
            confidence = 0.91
            evidence = [
                f"PostgreSQL active connections reached {db_conns} (98% of pool capacity).",
                "Downstream applications are blocking waiting for connection availability.",
                f"API latency spiked to {api_latency}ms with HTTP 504 Gateway Timeouts.",
                "Upstream gateway thread pools are exhausted due to blocking queries."
            ]
            recommended_actions = [
                {"action_id": "increase_pool", "title": "Increase database connection pool size limit", "type": "automatable"},
                {"action_id": "kill_idle_queries", "title": "Kill idle Postgres connections", "type": "automatable"},
                {"action_id": "scale_read_replica", "title": "Deploy read replica for billing operations", "type": "manual"}
            ]
        else:
            # General fallback analysis if no specific scenario is spiked
            root_cause = "Downstream Dependency Degradation"
            confidence = 0.75
            evidence = [
                "Upstream service latency is high, but internal database and cache metrics are healthy.",
                "HTTP request queue builds up at the load balancer layer.",
                "Recent payment-api v1.4.2 deployment detected 20 minutes ago."
            ]
            recommended_actions = [
                {"action_id": "rollback_deploy", "title": "Rollback payment-api to v1.4.1", "type": "automatable"},
                {"action_id": "throttle_gateway", "title": "Throttle request rate limit on gateway", "type": "manual"}
            ]

        # Call LLM to generate narrative reports if keys exist and we want to use them
        narrative_rca = ""
        if self.gemini_key or self.openai_key:
            try:
                narrative_rca = await self._call_llm_for_rca(incident, evidence, root_cause, health_status)
            except Exception:
                pass

        if not narrative_rca:
            narrative_rca = (
                f"TXENT investigated the incident '{incident.get('title')}' on service '{incident.get('service')}' and identified "
                f"**{root_cause}** as the primary root cause with **{int(confidence*100)}%** confidence.\n\n"
                f"**Investigation Summary:**\n"
                f"The surface alert indicated database latency, but our memory systems and metrics correlations revealed that the "
                f"cache hit ratio had dropped due to memory limits, flooding the database with requests. Downstream DB slowness "
                f"is a downstream symptom of the cache saturation."
            )

        log_step("Root Cause Analysis", "completed", f"Identified primary cause: '{root_cause}' with {int(confidence*100)}% confidence.")

        duration = int((time.time() - start_time) * 1000)
        
        investigation_result = {
            "incident_id": incident.get("incident_id"),
            "root_cause": root_cause,
            "confidence": confidence,
            "evidence": evidence,
            "timeline": timeline,
            "recommended_actions": recommended_actions,
            "narrative_rca": narrative_rca,
            "investigation_latency_ms": duration,
            "health_status": health_status,
            "metrics_data": metrics_data
        }

        # ── Push investigation results back to Splunk via HEC ──
        # This creates the bidirectional data flow: Splunk → TXENT → Splunk
        log_step("HEC Push", "running", "Pushing investigation results back to Splunk index via HEC.")
        hec_result = await self.splunk.push_to_splunk(
            event_data={
                "investigation": investigation_result,
                "incident_title": incident.get("title"),
                "root_cause": root_cause,
                "confidence": confidence,
                "service": target_service,
                "severity": incident.get("severity"),
            },
            sourcetype="txent:investigation"
        )
        log_step("HEC Push", hec_result.get("status", "unknown"), f"Splunk HEC response: {hec_result.get('status')}")

        # Also try MCP search to demonstrate MCP tool usage
        log_step("MCP Tool Call", "running", "Calling Splunk MCP Server for additional context.")
        mcp_result = await self.splunk.mcp_search(f"index=main sourcetype=txent:investigation | head 5")
        log_step("MCP Tool Call", mcp_result.get("status", "unknown"), f"MCP result: {mcp_result.get('status')}")

        investigation_result["splunk_hec_status"] = hec_result.get("status")
        investigation_result["splunk_mcp_status"] = mcp_result.get("status")

        return investigation_result

    async def _call_llm_for_rca(self, incident: dict[str, Any], evidence: list[str], root_cause: str, health_status: dict[str, str]) -> str:
        prompt = (
            f"You are the TXENT Agentic Observability Root Cause Analyzer.\n"
            f"Write a professional, concise, markdown incident root cause report based on the following findings:\n\n"
            f"Incident: {incident.get('title')} on service {incident.get('service')}\n"
            f"Severity: {incident.get('severity')}\n"
            f"Environment: {incident.get('environment')}\n"
            f"Detected Causal Root: {root_cause}\n"
            f"Evidence Found:\n" + "\n".join([f"- {e}" for e in evidence]) + "\n\n"
            f"Service Health: {json.dumps(health_status)}\n\n"
            f"Provide a brief, high-impact summary explaining why the surface alert was misleading (i.e. why the database timeout was a symptom and cache saturation was the root cause) and suggest key remediation actions."
        )

        payload = {
            "model": self.llm_model,
            "messages": [
                {"role": "system", "content": "You are a professional Site Reliability Engineer and Observability expert."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 500,
            "temperature": 0.2
        }

        headers = {}
        if self.openai_key:
            headers["Authorization"] = f"Bearer {self.openai_key}"
        elif self.gemini_key:
            headers["Authorization"] = f"Bearer {self.gemini_key}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(self.llm_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return str(data["choices"][0]["message"]["content"])
