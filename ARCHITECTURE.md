# TXENT Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          TXENT COMMAND CENTER                               │
│                  (frontend/txent_final.html — Browser UI)                    │
│  ┌──────────┐  ┌──────────────┐  ┌────────────┐  ┌──────────────────────┐  │
│  │ Incident  │  │  Memory      │  │ Knowledge  │  │ Investigation       │  │
│  │ Trigger   │  │  Retrieval   │  │ Graph      │  │ Results Panel       │  │
│  └─────┬─────┘  └──────┬───────┘  └─────┬──────┘  └──────────┬──────────┘  │
└────────┼───────────────┼────────────────┼──────────────────────┼─────────────┘
         │               │                │                      │
         ▼               ▼                ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FastAPI Backend (api/main.py)                         │
│                                                                              │
│   POST /api/ingest/incident    POST /retrieve    GET /graph                  │
│   POST /api/actions/execute    GET /api/dashboard GET /api/splunk/readings    │
└──────────────────────────────────┬───────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Orchestrator (core/orchestrator.py)                        │
│                                                                              │
│  Coordinates all memory layers, kick detection, and agent investigations     │
└───┬──────────┬──────────┬──────────┬──────────┬──────────┬──────────────────┘
    │          │          │          │          │          │
    ▼          ▼          ▼          ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌─────────────────┐
│   L1   │ │   L2   │ │   L3   │ │   L4   │ │  KICK  │ │  INVESTIGATOR   │
│Surface │ │Assoc.  │ │Struct. │ │Archety │ │Detector│ │  AGENT          │
│Memory  │ │Graph   │ │Patterns│ │pes     │ │        │ │                 │
│        │ │        │ │        │ │        │ │Contra- │ │ Autonomous      │
│Raw logs│ │Service │ │7 obser │ │Deep    │ │diction │ │ investigation   │
│metrics │ │depend- │ │vability│ │ops     │ │& diver │ │ with evidence   │
│alerts  │ │encies  │ │pattern │ │priors  │ │gence   │ │ collection      │
│traces  │ │& paths │ │match   │ │        │ │scoring │ │                 │
└────────┘ └────────┘ └────────┘ └────────┘ └───┬────┘ └────────┬────────┘
                                                 │               │
                                   ┌─────────────┘               │
                                   │  If contradiction detected  │
                                   │  → trigger investigation ───┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   Splunk Connector (connectors/splunk.py)                     │
│                                                                              │
│   ┌────────────────────┐  ┌──────────────────┐  ┌─────────────────────┐     │
│   │ Splunk REST API    │  │ Splunk MCP Server │  │ Simulation Engine  │     │
│   │ (port 8089)        │  │ (Model Context    │  │ (High-fidelity     │     │
│   │                    │  │  Protocol)        │  │  telemetry for     │     │
│   │ • SPL searches     │  │                   │  │  demo/dev mode)    │     │
│   │ • Index queries    │  │ • splunk_search   │  │                    │     │
│   │ • Server info      │  │ • splunk_indexes  │  │ • CPU/Memory spikes│     │
│   │ • Saved searches   │  │ • splunk_kvstore  │  │ • Error rate surges│     │
│   └────────┬───────────┘  └────────┬──────────┘  │ • DB pool exhaust  │     │
│            │                       │              └─────────┬──────────┘     │
└────────────┼───────────────────────┼────────────────────────┼────────────────┘
             │                       │                        │
             ▼                       ▼                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SPLUNK ENTERPRISE                                     │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ MCP Server   │  │ AI Toolkit   │  │ AI Assistant │  │ Indexes      │    │
│  │ App (#7931)  │  │ App (#2890)  │  │ App (#7245)  │  │ (main, etc.) │    │
│  │              │  │              │  │              │  │              │    │
│  │ Model Context│  │ Hosted Models│  │ Natural Lang │  │ Log/Metric   │    │
│  │ Protocol     │  │ • Foundation │  │ SPL queries  │  │ storage      │    │
│  │ integration  │  │   Sec 8B     │  │              │  │              │    │
│  │              │  │ • Cisco Deep │  │              │  │              │    │
│  │              │  │   Time Series│  │              │  │              │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                                              │
│  HTTP Event Collector (HEC) ← TXENT pushes investigation results back       │
└─────────────────────────────────────────────────────────────────────────────┘


DATA FLOW:
═══════════

1. INGEST:   Splunk Index → REST/MCP → TXENT L1 Surface Memory
2. ANALYZE:  L1 → L2 Graph → L3 Pattern Match → L4 Archetype Check
3. DETECT:   Kick Mechanism compares current vs. historical patterns
4. INVESTIGATE: If Kick fires → Agent queries Splunk for deeper evidence
5. RESPOND:  Agent compiles root cause + remediation → Dashboard
6. FEEDBACK: Investigation results → pushed back to Splunk via HEC
```

## Key Innovation: The Kick Mechanism

Unlike traditional observability tools that only surface alerts, TXENT's **Kick Mechanism** detects when a surface-level alert contradicts the historical pattern memory. For example:

- **Surface Alert**: "Database connection timeout on postgres-db"
- **Historical Pattern (L3)**: This signature matches "Cache Saturation" not "Database Failure"
- **Kick Fires**: Contradiction detected! The database timeout is a *symptom*, not the *cause*
- **Agent Investigates**: Queries Splunk for redis-cache metrics → confirms cache hit ratio dropped → root cause: Redis memory exhaustion

This transforms TXENT from a passive dashboard into an **agentic system that challenges its own assumptions**.
