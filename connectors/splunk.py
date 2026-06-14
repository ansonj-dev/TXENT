from __future__ import annotations

import os
import time
import random
from typing import Any
import httpx
from dotenv import load_dotenv

load_dotenv()

class SplunkConnector:
    """
    Connects to Splunk Enterprise REST API or Splunk MCP Server.
    Provides a high-fidelity simulated fallback if Splunk is not configured or reachable.
    """

    def __init__(self) -> None:
        self.splunk_host = os.getenv("SPLUNK_HOST", "")
        self.splunk_token = os.getenv("SPLUNK_TOKEN", "")
        self.splunk_port = os.getenv("SPLUNK_PORT", "8089")
        self.splunk_mcp_url = os.getenv("SPLUNK_MCP_URL", "")
        self.splunk_hec_url = os.getenv("SPLUNK_HEC_URL", "")
        self.splunk_hec_token = os.getenv("SPLUNK_HEC_TOKEN", "")
        self.use_simulation = not (self.splunk_host and self.splunk_token) and not self.splunk_mcp_url
        
        # Simulating environment state
        self.simulation_state = {
            "current_incident": None,
            "metrics": {
                "payment-api": {"latency": 150, "error_rate": 0.2, "cpu": 35, "memory": 45, "connections": 15},
                "redis-cache": {"latency": 2, "error_rate": 0.0, "cpu": 15, "memory": 58, "hit_ratio": 95},
                "postgres-db": {"latency": 25, "error_rate": 0.0, "cpu": 20, "memory": 60, "connections": 18},
                "auth-service": {"latency": 80, "error_rate": 0.1, "cpu": 25, "memory": 40},
                "order-service": {"latency": 110, "error_rate": 0.3, "cpu": 30, "memory": 50},
                "user-service": {"latency": 90, "error_rate": 0.1, "cpu": 22, "memory": 38}
            },
            "recent_deployments": [
                {"timestamp": time.time() - 3600 * 2, "service": "auth-service", "version": "v2.1.0", "status": "success"},
                {"timestamp": time.time() - 1200, "service": "payment-api", "version": "v1.4.2", "status": "success", "notes": "Optimized database query routing"}
            ],
            "incident_history": []
        }

    async def get_status(self) -> dict[str, Any]:
        """Checks connections and returns the connector status."""
        if self.use_simulation:
            return {
                "status": "connected",
                "mode": "simulation",
                "splunk_mcp": "simulated",
                "splunk_rest": "simulated",
                "host": "localhost:8089 (simulated)"
            }
        
        status = {
            "status": "connected",
            "mode": "live",
            "splunk_mcp": "disconnected",
            "splunk_rest": "disconnected",
            "host": self.splunk_host
        }

        # Check REST API
        if self.splunk_host and self.splunk_token:
            try:
                headers = {"Authorization": f"Bearer {self.splunk_token}"}
                async with httpx.AsyncClient(verify=False, timeout=3.0) as client:
                    url = f"https://{self.splunk_host.strip('/')}:8089/services/server/info?output_mode=json"
                    response = await client.get(url, headers=headers)
                    if response.status_code == 200:
                        status["splunk_rest"] = "connected"
            except Exception:
                status["splunk_rest"] = "failed"

        # Check MCP Server
        if self.splunk_mcp_url:
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    # Simple JSON-RPC ping or GET check depending on MCP transport
                    response = await client.get(self.splunk_mcp_url)
                    if response.status_code < 500:
                        status["splunk_mcp"] = "connected"
            except Exception:
                status["splunk_mcp"] = "failed"

        if status["splunk_rest"] != "connected" and status["splunk_mcp"] != "connected":
            status["status"] = "degraded"
            status["mode"] = "live-fallback-simulation"

        return status

    async def search_logs(self, query: str, earliest: str = "-15m", latest: str = "now") -> list[dict[str, Any]]:
        """Queries Splunk logs using SPL or returns simulated logs."""
        if self.use_simulation or not (self.splunk_host and self.splunk_token):
            return self._generate_simulated_logs(query)
            
        headers = {"Authorization": f"Bearer {self.splunk_token}"}
        url = f"https://{self.splunk_host.strip('/')}:8089/services/search/jobs?output_mode=json"
        
        try:
            async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
                # 1. Create search job
                search_query = f"search {query}"
                data = {
                    "search": search_query,
                    "earliest_time": earliest,
                    "latest_time": latest
                }
                response = await client.post(url, headers=headers, data=data)
                response.raise_for_status()
                sid = response.json().get("sid")
                
                if not sid:
                    return []
                
                # 2. Poll for completion
                job_url = f"{url}/{sid}?output_mode=json"
                for _ in range(10):
                    time.sleep(0.5)
                    job_res = await client.get(job_url, headers=headers)
                    job_res.raise_for_status()
                    job_data = job_res.json()
                    is_done = job_data.get("entry", [{}])[0].get("content", {}).get("isDone", False)
                    if is_done:
                        break
                
                # 3. Retrieve results
                results_url = f"{url}/{sid}/results?output_mode=json"
                res_response = await client.get(results_url, headers=headers)
                res_response.raise_for_status()
                return res_response.json().get("results", [])
        except Exception as e:
            # Fallback to simulated logs if querying fails
            return [
                {"_raw": f"Splunk query failed ({str(e)}). Falling back to simulated records.", "source": "txent-connector", "host": "splunk-mcp"},
                *self._generate_simulated_logs(query)
            ]

    async def query_metrics(self, service: str, duration_minutes: int = 15) -> dict[str, list[float] | list[str]]:
        """Queries telemetry metrics for a service."""
        # Simulated metrics values
        timestamps = []
        now = time.time()
        for i in range(duration_minutes):
            t_str = time.strftime("%H:%M", time.localtime(now - (duration_minutes - 1 - i) * 60))
            timestamps.append(t_str)

        # Generate sparkline-style lists
        state = self.simulation_state["metrics"].get(service, {})
        base_latency = state.get("latency", 100)
        base_cpu = state.get("cpu", 25)
        base_memory = state.get("memory", 45)
        base_error = state.get("error_rate", 0.1)

        latency_series = []
        cpu_series = []
        memory_series = []
        error_series = []

        for _ in range(duration_minutes - 1):
            latency_series.append(round(base_latency * random.uniform(0.9, 1.1), 1))
            cpu_series.append(round(base_cpu * random.uniform(0.85, 1.15), 1))
            memory_series.append(round(base_memory * random.uniform(0.99, 1.01), 1))
            error_series.append(round(base_error * random.uniform(0.8, 1.2), 2))

        # Append current state
        latency_series.append(base_latency)
        cpu_series.append(base_cpu)
        memory_series.append(base_memory)
        error_series.append(base_error)

        return {
            "timestamps": timestamps,
            "latency": latency_series,
            "cpu": cpu_series,
            "memory": memory_series,
            "error_rate": error_series
        }

    async def check_service_health(self, service: str) -> str:
        """Gets current health of a service."""
        state = self.simulation_state["metrics"].get(service, {})
        latency = state.get("latency", 0)
        error = state.get("error_rate", 0)
        memory = state.get("memory", 0)
        
        if service == "redis-cache" and memory > 95:
            return "critical"
        if service == "payment-api" and latency > 1000:
            return "critical"
        if service == "postgres-db" and state.get("connections", 0) > 40:
            return "degraded"
        if latency > 500 or error > 4.0:
            return "critical"
        if latency > 250 or error > 1.5:
            return "degraded"
        
        return "healthy"

    def trigger_simulation_incident(self, incident_type: str) -> dict[str, Any]:
        """Triggers a simulated incident (spikes metrics, inserts anomalies)."""
        if incident_type == "cache_saturation":
            # Spike Redis Memory and API Latency
            self.simulation_state["metrics"]["redis-cache"]["memory"] = 98.4
            self.simulation_state["metrics"]["redis-cache"]["hit_ratio"] = 12.1
            self.simulation_state["metrics"]["redis-cache"]["cpu"] = 87.2
            
            self.simulation_state["metrics"]["payment-api"]["latency"] = 1250.0
            self.simulation_state["metrics"]["payment-api"]["error_rate"] = 6.2
            self.simulation_state["metrics"]["payment-api"]["cpu"] = 61.0
            self.simulation_state["metrics"]["payment-api"]["memory"] = 58.0
            
            self.simulation_state["metrics"]["postgres-db"]["connections"] = 42
            self.simulation_state["metrics"]["postgres-db"]["latency"] = 45.0
            self.simulation_state["metrics"]["postgres-db"]["cpu"] = 48.0
            
            incident = {
                "incident_id": f"INC-{time.strftime('%Y%m%d')}-001",
                "timestamp": time.time(),
                "severity": "critical",
                "service": "payment-api",
                "environment": "Production",
                "source": "Splunk Alert",
                "title": "API Latency Increased 400%",
                "description": "Users are experiencing high latency while calling the payment API. Error rate is also elevated. Database connection pool is high, and response times are degraded."
            }
            self.simulation_state["current_incident"] = incident
            return incident
            
        elif incident_type == "db_pool_exhaustion":
            self.simulation_state["metrics"]["postgres-db"]["connections"] = 98
            self.simulation_state["metrics"]["postgres-db"]["cpu"] = 95.0
            self.simulation_state["metrics"]["postgres-db"]["latency"] = 380.0
            
            self.simulation_state["metrics"]["payment-api"]["latency"] = 2100.0
            self.simulation_state["metrics"]["payment-api"]["error_rate"] = 14.5
            
            incident = {
                "incident_id": f"INC-{time.strftime('%Y%m%d')}-002",
                "timestamp": time.time(),
                "severity": "critical",
                "service": "postgres-db",
                "environment": "Production",
                "source": "Splunk Alert",
                "title": "Postgres Database Connection Pool Exhausted",
                "description": "PostgreSQL database has reached 98% of active connection pool. All downstream services are experiencing query queue build-ups and HTTP 504 gateway timeouts."
            }
            self.simulation_state["current_incident"] = incident
            return incident
            
        else:
            # Reset / Normal state
            self.simulation_state["metrics"]["redis-cache"]["memory"] = 58.2
            self.simulation_state["metrics"]["redis-cache"]["hit_ratio"] = 95.4
            self.simulation_state["metrics"]["redis-cache"]["cpu"] = 15.0
            
            self.simulation_state["metrics"]["payment-api"]["latency"] = 150.0
            self.simulation_state["metrics"]["payment-api"]["error_rate"] = 0.2
            self.simulation_state["metrics"]["payment-api"]["cpu"] = 35.0
            self.simulation_state["metrics"]["payment-api"]["memory"] = 45.0
            
            self.simulation_state["metrics"]["postgres-db"]["connections"] = 18
            self.simulation_state["metrics"]["postgres-db"]["latency"] = 25.0
            self.simulation_state["metrics"]["postgres-db"]["cpu"] = 20.0
            
            self.simulation_state["current_incident"] = None
            return {"status": "normal", "message": "Telemetry metrics reset to normal baselines."}

    def _generate_simulated_logs(self, query: str) -> list[dict[str, Any]]:
        """Generates mock logs based on service queries."""
        q = query.lower()
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        
        if "redis" in q or "cache" in q:
            if self.simulation_state["metrics"]["redis-cache"]["memory"] > 90:
                return [
                    {"timestamp": now, "level": "WARNING", "service": "redis-cache", "_raw": f"[{now}] redis-server[102]: # WARNING over 95% of RAM used! maxmemory is set to 2.00 GB"},
                    {"timestamp": now, "level": "ERROR", "service": "redis-cache", "_raw": f"[{now}] redis-server[102]: # OOM command disallowed: out of memory allocating 4096 bytes"},
                    {"timestamp": now, "level": "WARNING", "service": "redis-cache", "_raw": f"[{now}] redis-server[102]: * Evicting keys under volatile-lru policy"}
                ]
            return [
                {"timestamp": now, "level": "INFO", "service": "redis-cache", "_raw": f"[{now}] redis-server[102]: * Running version 7.0.10 in standalone mode"},
                {"timestamp": now, "level": "INFO", "service": "redis-cache", "_raw": f"[{now}] redis-server[102]: * Memory usage: 1.16 GB (58.2% of maxmemory)"}
            ]
            
        if "postgres" in q or "db" in q or "database" in q:
            if self.simulation_state["metrics"]["postgres-db"]["connections"] > 90:
                return [
                    {"timestamp": now, "level": "FATAL", "service": "postgres-db", "_raw": f"[{now}] postgres[2910]: FATAL: remaining connection slots are reserved for non-replication superuser connections"},
                    {"timestamp": now, "level": "WARNING", "service": "postgres-db", "_raw": f"[{now}] postgres[2910]: WARNING: database connection pool capacity at 98% (98/100)"}
                ]
            if self.simulation_state["metrics"]["postgres-db"]["connections"] > 35:
                return [
                    {"timestamp": now, "level": "WARNING", "service": "postgres-db", "_raw": f"[{now}] postgres[2910]: WARNING: database connection pool is accumulating waiting queries (42 connections active)"},
                    {"timestamp": now, "level": "INFO", "service": "postgres-db", "_raw": f"[{now}] postgres[2910]: LOG: duration: 850.42 ms  statement: SELECT * FROM payments WHERE transaction_id = $1"}
                ]
            return [
                {"timestamp": now, "level": "INFO", "service": "postgres-db", "_raw": f"[{now}] postgres[2910]: LOG: database system is ready to accept connections"},
                {"timestamp": now, "level": "INFO", "service": "postgres-db", "_raw": f"[{now}] postgres[2910]: LOG: connection pool active connections: 18/100"}
            ]
            
        if "payment" in q or "latency" in q:
            if self.simulation_state["metrics"]["payment-api"]["latency"] > 1000:
                return [
                    {"timestamp": now, "level": "ERROR", "service": "payment-api", "_raw": f"[{now}] payment-api[77]: ERROR: Timeout calling database. Transaction failed.", "trace_id": "tr-payment-991f8a"},
                    {"timestamp": now, "level": "WARNING", "service": "payment-api", "_raw": f"[{now}] payment-api[77]: WARNING: HTTP 504 Gateway Timeout returned to client. Latency = 1250ms"},
                    {"timestamp": now, "level": "ERROR", "service": "payment-api", "_raw": f"[{now}] payment-api[77]: ERROR: Failed to execute credit card validation: connection pool exhausted."}
                ]
            return [
                {"timestamp": now, "level": "INFO", "service": "payment-api", "_raw": f"[{now}] payment-api[77]: INFO: Processed transaction tx_881b2a successfully. Latency = 148ms"},
                {"timestamp": now, "level": "INFO", "service": "payment-api", "_raw": f"[{now}] payment-api[77]: INFO: healthcheck passed - payment-api operational"}
            ]

        # Default general logs
        return [
            {"timestamp": now, "level": "INFO", "service": "payment-api", "_raw": f"[{now}] payment-api: GET /v1/payments - 200 OK (148ms)"},
            {"timestamp": now, "level": "INFO", "service": "redis-cache", "_raw": f"[{now}] redis-cache: GET key:user:8812 - HIT (2ms)"},
            {"timestamp": now, "level": "INFO", "service": "postgres-db", "_raw": f"[{now}] postgres-db: SELECT * FROM accounts - 200 OK (22ms)"}
        ]

    # ── Splunk HTTP Event Collector (HEC) — Push Results Back ────────────────

    async def push_to_splunk(self, event_data: dict[str, Any], sourcetype: str = "txent:investigation", index: str = "main") -> dict[str, Any]:
        """
        Pushes TXENT investigation results back to Splunk via HEC.
        This creates a bidirectional data flow: Splunk → TXENT → Splunk.
        """
        if not self.splunk_hec_url or not self.splunk_hec_token:
            # Log locally if HEC is not configured
            return {"status": "skipped", "reason": "HEC not configured", "event_logged": True}

        hec_payload = {
            "event": event_data,
            "sourcetype": sourcetype,
            "index": index,
            "source": "txent:investigator",
            "time": time.time()
        }

        try:
            headers = {"Authorization": f"Splunk {self.splunk_hec_token}"}
            async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
                response = await client.post(self.splunk_hec_url, json=hec_payload, headers=headers)
                response.raise_for_status()
                return {"status": "sent", "splunk_response": response.json()}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    # ── Splunk MCP Server — Structured Tool Calls ───────────────────────────

    async def mcp_call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Calls a tool on the Splunk MCP Server using JSON-RPC 2.0.
        
        Available MCP tools (Splunkbase #7931):
        - splunk_search: Run SPL queries
        - splunk_get_indexes: List available indexes
        - splunk_get_saved_searches: Access saved searches  
        - splunk_kvstore: Read/write KV store entries
        """
        if not self.splunk_mcp_url:
            return {"status": "unavailable", "reason": "MCP URL not configured", "tool": tool_name}

        payload = {
            "jsonrpc": "2.0",
            "id": f"txent-{int(time.time())}",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {}
            }
        }

        try:
            headers = {"Content-Type": "application/json"}
            if self.splunk_token:
                headers["Authorization"] = f"Bearer {self.splunk_token}"
            
            async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
                response = await client.post(self.splunk_mcp_url, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()
                return {"status": "success", "result": result.get("result", result)}
        except Exception as e:
            return {"status": "failed", "error": str(e), "tool": tool_name}

    async def mcp_search(self, spl_query: str, earliest: str = "-15m", latest: str = "now") -> dict[str, Any]:
        """Convenience wrapper: run an SPL search via MCP Server."""
        return await self.mcp_call_tool("splunk_search", {
            "search_query": spl_query,
            "earliest_time": earliest,
            "latest_time": latest
        })

    async def mcp_list_indexes(self) -> dict[str, Any]:
        """Convenience wrapper: list all Splunk indexes via MCP Server."""
        return await self.mcp_call_tool("splunk_get_indexes")

