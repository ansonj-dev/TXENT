# TXENT: Agentic Observability Memory System for Splunk

TXENT is a production-ready AI-powered observability platform that integrates with Splunk. It transforms raw logs, alerts, metrics, and service topologies into structural memory. Unlike standard assistants, TXENT continuously learns from historical incidents, checks for contradictions using a proprietary Kick Mechanism, and launches autonomous investigations via Splunk MCP to find true root causes.

## Four-Layer Memory Architecture

1. **L1: Surface Memory** (`layers/l1_surface.py`): Stores raw logs, alerts, metrics snapshots, and trace summaries indexed with structured metadata (`incident_id`, `timestamp`, `severity`, `service`, `environment`, `source`).
2. **L2: Associative Graph** (`layers/l2_associative.py`): Maps relationships between services, databases, caches, and cloud infrastructure (e.g., `payment-api` -> `redis-cache` -> `postgres-db`).
3. **L3: Structural Pattern Layer** (`layers/l3_structural.py`): Matches active incidents against 7 operational pattern signatures (Resource Exhaustion, Cache Saturation, Cascading Failure, Network Partition, Dependency Failure, Traffic Spike, and Configuration Drift).
4. **L4: Operational Archetypes** (`layers/l4_archetypes.py`): Encapsulates deep operational priors and wisdom rules (e.g. cache saturation appearing as database connection exhaustions) to guide investigations.

## Upgraded Kick Mechanism & Agentic Investigation

When a surface alert comes in (e.g., "Database Timeout"), the **Kick Detector** (`core/kick.py`) compares it semantically and topologically against historical pattern expectations (e.g., Cache Saturation). If a contradiction is detected (divergence > threshold):
1. **KICK FIRES**: Flagging that the surface alert is likely a downstream symptom.
2. **Autonomous Investigation Agent** (`agents/investigator.py`): Automatically launches, queries the **Splunk Connector** (`connectors/splunk.py`) via Splunk MCP/REST to gather metrics and logs, builds a step-by-step timeline, and compiles a comprehensive root-cause analysis.
3. **Remediation**: Recommends automatable actions (e.g., scaling the Redis cache cluster) that can be executed directly from the dashboard.

## Lightweight Zero-Dependency Fallback

To support immediate, lightweight local execution on machines without GPU environments or Docker, TXENT includes pure-Python in-memory fallbacks for Qdrant, spaCy, and SentenceTransformers.
- Vector search runs on a fast hashed word-overlap vectorizer.
- Service graph entity extraction uses rule-based matching.
- Graph traversal calculates BFS shortest paths in pure Python.
This guarantees the entire stack runs out of the box in under 1 second!

## Quick Start on Windows

### 1. Configure Settings
Configure your environment variables in `.env`:
```ini
LLM_URL=http://localhost:30000/v1/chat/completions
LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
KICK_THRESHOLD=0.42
API_PORT=8000
DREAMWEAVE_MEMORY_DIR=memory_store
DREAMWEAVE_AUTO_LOAD=true
DREAMWEAVE_AUTO_SAVE=true
CI=false

# Optional Splunk Enterprise REST API & MCP Server config
SPLUNK_HOST=
SPLUNK_TOKEN=
SPLUNK_MCP_URL=

# Optional AI credentials (Gemini / OpenAI)
GEMINI_API_KEY=
OPENAI_API_KEY=
```

### 2. Start the FastAPI API Server
Start the server using PowerShell:
```powershell
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Open the Command Center Dashboard
Open your browser and navigate to:
`http://localhost:8000/`

## Testing and Verification

Run the integration tests verifying the entire L1-L4 flow, Splunk simulator, Kick mechanism, and investigator agent:
```powershell
$env:PYTHONPATH="."; python test/test_txent_flow.py
```
