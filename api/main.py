from __future__ import annotations

import asyncio
import io
import json
import os
import re
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.responses import FileResponse, StreamingResponse

from core.orchestrator import DreamWeaveOrchestrator

load_dotenv()

LLM_URL = os.getenv("LLM_URL", "http://localhost:30000/v1/chat/completions")
LLM_MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")

orchestrator: DreamWeaveOrchestrator | None = None

class IngestRequest(BaseModel):
    text: str = Field(..., min_length=1)
    source: str = "manual"

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    generate_answer: bool = True
    max_tokens: int = Field(default=600, ge=1, le=4096)
    kick_enabled: bool = True

class NodeExpandRequest(BaseModel):
    label: str = Field(..., min_length=1)

class UrlIngestRequest(BaseModel):
    url: str = Field(..., min_length=8)
    source: str = "url"

class YoutubeIngestRequest(BaseModel):
    video_url: str = Field(..., min_length=8)
    source: str | None = None

class BatchIngestRequest(BaseModel):
    documents: list[IngestRequest] = Field(..., min_length=1)

class MemoryPathRequest(BaseModel):
    path: str | None = None

class IngestResponse(BaseModel):
    status: str
    chunks_ingested: int
    source: str
    graph_nodes: int
    graph_edges: int

class RetrieveResponse(BaseModel):
    query: str
    l1_surface: list[dict[str, Any]]
    l2_associative: list[dict[str, Any]]
    l3_structural: list[dict[str, Any]]
    l4_archetypes: list[dict[str, Any]] = []
    kick: dict[str, Any]
    kick_reranked_surface: list[dict[str, Any]] = []
    agent_investigation: dict[str, Any] | None = None
    graph_stats: dict[str, Any]
    answer: str
    latency_ms: int

class TriggerIncidentRequest(BaseModel):
    incident_type: str

class ExecuteActionRequest(BaseModel):
    action_id: str
    service: str | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestrator
    orchestrator = DreamWeaveOrchestrator()
    yield

app = FastAPI(title="TXENT API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_HTML = Path(__file__).resolve().parents[1] / "frontend" / "txent.html"

def get_orchestrator() -> DreamWeaveOrchestrator:
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="TXENT orchestrator is still starting")
    return orchestrator

@app.post("/ingest", response_model=IngestResponse)
async def ingest(req: IngestRequest) -> IngestResponse:
    try:
        result = get_orchestrator().ingest(text=req.text, source=req.source)
        return IngestResponse(status="ok", **result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingest failed: {exc}") from exc

@app.post("/ingest/batch")
async def ingest_batch(req: BatchIngestRequest) -> dict[str, Any]:
    try:
        documents = [
            document.model_dump() if hasattr(document, "model_dump") else document.dict()
            for document in req.documents
        ]
        return {"status": "ok", **get_orchestrator().ingest_batch(documents)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Batch ingest failed: {exc}") from exc

@app.post("/ingest/file", response_model=IngestResponse)
async def ingest_file(file: UploadFile = File(...), source: str | None = None) -> IngestResponse:
    try:
        raw = await file.read()
        source_name = source or file.filename or "uploaded_file"
        text = extract_uploaded_text(filename=source_name, content=raw)
        if not text.strip():
            raise HTTPException(status_code=400, detail="Uploaded file did not contain extractable text")
        result = get_orchestrator().ingest(text=text, source=source_name)
        return IngestResponse(status="ok", **result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"File ingest failed: {exc}") from exc

@app.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(req: QueryRequest) -> RetrieveResponse:
    started = time.perf_counter()
    answer = "Answer generation disabled"
    try:
        dw = get_orchestrator()
        context = await dw.retrieve(req.query, kick_enabled=req.kick_enabled)
        if req.generate_answer:
            prompt = dw.build_llm_context(context)
            answer = await call_llm(prompt, req.query, req.max_tokens, context)
        latency_ms = int((time.perf_counter() - started) * 1000)
        return RetrieveResponse(answer=answer, latency_ms=latency_ms, **context)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Retrieve failed: {exc}") from exc

@app.post("/retrieve/stream")
async def retrieve_stream(req: QueryRequest) -> StreamingResponse:
    async def events():
        started = time.perf_counter()
        yield sse("status", {"message": "Starting layered retrieval"})
        await asyncio.sleep(0)
        try:
            dw = get_orchestrator()
            context = await dw.retrieve(req.query, kick_enabled=req.kick_enabled)
            yield sse("layers", context)
            answer = "Answer generation disabled"
            confidence = 1.0
            if req.generate_answer:
                yield sse("status", {"message": "Calling local LLM"})
                prompt = dw.build_llm_context(context)
                streamed = ""
                try:
                    async for token in stream_llm_tokens(prompt, req.query, req.max_tokens):
                        streamed += token
                        yield sse("token", {"token": token})
                    answer = streamed if streamed else build_retrieval_answer(req.query, context)
                except Exception:
                    answer = await call_llm(prompt, req.query, req.max_tokens, context)
                
                kick = context.get("kick", {})
                contradiction = float(kick.get("contradiction_score", 0.0))
                confidence = max(0.0, round(1.0 - contradiction, 2))
            latency_ms = int((time.perf_counter() - started) * 1000)
            yield sse("answer", {"answer": answer, "latency_ms": latency_ms, "confidence": confidence})
            yield sse("done", {"status": "complete"})
        except Exception as exc:
            yield sse("error", {"message": str(exc)})

    return StreamingResponse(events(), media_type="text/event-stream")

@app.post("/node/expand")
async def node_expand(req: NodeExpandRequest) -> StreamingResponse:
    async def events():
        try:
            dw = get_orchestrator()
            results = dw.l1.search(req.label, top_k=1)
            chunk = results[0] if results else None
            
            if chunk:
                yield sse("origin", {"source": chunk.get("source", "Unknown"), "score": chunk.get("score", 0)})
            else:
                yield sse("origin", {"source": "Graph Inference", "score": 1.0})

            prompt_context = f"Context: {chunk.get('text', '')}" if chunk else "No additional context available."
            system_prompt = (
                f"You are the TXENT memory core. Briefly define or explain the concept '{req.label}' "
                f"in exactly 1 or 2 short sentences based on this context. DO NOT use markdown, asterisks, or formatting. "
                f"\n\n{prompt_context}"
            )
            
            async for token in stream_llm_tokens(system_prompt, req.label, 150):
                token = token.replace("*", "").replace("#", "").replace("_", "").replace("`", "")
                if token:
                    yield sse("token", {"token": token})
            
            yield sse("done", {"status": "complete"})
        except Exception as exc:
            yield sse("error", {"message": str(exc)})

    return StreamingResponse(events(), media_type="text/event-stream")

# ── TXENT Observability Custom Endpoints ────────────────────────────────────

@app.get("/api/splunk/status")
async def get_splunk_status() -> dict[str, Any]:
    """Retrieves connection state of Splunk Enterprise and Splunk MCP."""
    try:
        return await get_orchestrator().splunk.get_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/api/ingest/incident")
async def ingest_incident(req: TriggerIncidentRequest) -> dict[str, Any]:
    """Triggers an incident in the simulator and ingests it into memory layers."""
    try:
        dw = get_orchestrator()
        incident = dw.splunk.trigger_simulation_incident(req.incident_type)
        
        # If a real incident was triggered (not a reset), ingest it into memory
        if "incident_id" in incident:
            text = f"{incident['title']}: {incident['description']}. Impacted service: {incident['service']}. Detected by: {incident['source']}."
            dw.ingest(
                text=text,
                source=incident["source"],
                metadata={
                    "incident_id": incident["incident_id"],
                    "severity": incident["severity"],
                    "service": incident["service"],
                    "environment": incident["environment"]
                }
            )
            return {"status": "incident_triggered", "incident": incident}
        
        return {"status": "reset", "message": "System telemetry reset to healthy baselines."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/api/actions/execute")
async def execute_action(req: ExecuteActionRequest) -> dict[str, Any]:
    """Executes a recommended remediation action and resolves the incident metrics."""
    try:
        dw = get_orchestrator()
        action_id = req.action_id
        
        # In simulator mode, executing remediation resolves the spiked metrics
        if action_id in ["scale_redis", "clear_keys", "increase_pool", "kill_idle_queries", "rollback_deploy"]:
            dw.splunk.trigger_simulation_incident("reset")
            return {
                "status": "success",
                "message": f"Successfully executed action: {action_id}. Target services have been scaled/cleared. Telemetry returned to normal."
            }
        
        return {"status": "ignored", "message": f"Action {action_id} logged but no changes were executed."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/api/incidents")
async def get_incidents() -> dict[str, Any]:
    """Lists recent incidents under investigation."""
    dw = get_orchestrator()
    incident = dw.splunk.simulation_state.get("current_incident")
    return {
        "active_incident": incident,
        "history": dw.splunk.simulation_state.get("incident_history", [])
    }

# ── Standard Dreamweave/TXENT Endpoints ─────────────────────────────────────

async def call_llm(context: str, query: str, max_tokens: int, retrieval_context: dict[str, Any]) -> str:
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": context},
            {"role": "user", "content": query},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(LLM_URL, json=payload)
            response.raise_for_status()
            data = response.json()
            return str(data["choices"][0]["message"]["content"])
    except Exception as llm_err:
        import logging
        logging.getLogger("txent").warning(f"LLM call failed: {llm_err}")
        return build_retrieval_answer(query, retrieval_context)

async def stream_llm_tokens(context: str, query: str, max_tokens: int):
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": context},
            {"role": "user", "content": query},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.3,
        "stream": True,
    }
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", LLM_URL, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        chunk = line[6:].strip()
                        if chunk == "[DONE]":
                            break
                        try:
                            obj = json.loads(chunk)
                            delta = obj["choices"][0].get("delta", {})
                            token = delta.get("content", "")
                            if token:
                                yield token
                        except Exception:
                            continue
    except Exception:
        # Fallback stream
        yield "Streaming failed, fallback answer loading..."

@app.get("/health")
async def health() -> dict[str, Any]:
    dw = get_orchestrator()
    splunk_status = await dw.splunk.get_status()
    return {
        "status": "alive",
        "runtime": dw.runtime_status(),
        "layers": ["L1", "L2", "L3", "L4", "Kick"],
        "l1_stats": dw.l1.stats(),
        "graph_stats": dw.l2.stats(),
        "splunk_status": splunk_status,
        "llm_url": LLM_URL,
        "llm_model": LLM_MODEL,
    }

@app.get("/health/llm")
async def health_llm() -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                LLM_URL,
                json={
                    "model": LLM_MODEL,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1,
                    "temperature": 0,
                },
            )
        return {"status": "reachable" if response.status_code < 500 else "error", "status_code": response.status_code}
    except Exception as exc:
        return {"status": "unreachable", "error": str(exc)}

@app.get("/graph")
async def graph(entity: str | None = Query(default=None)) -> dict[str, Any]:
    try:
        return get_orchestrator().get_graph_data(entity)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Graph fetch failed: {exc}") from exc

@app.get("/schemas")
async def schemas() -> list[dict[str, str]]:
    return get_orchestrator().l3.list_schemas()

@app.get("/stats")
async def stats() -> dict:
    dw = get_orchestrator()
    l1 = dw.l1.stats()
    g = dw.l2.stats()
    return {
        "l1_total_chunks": l1.get("total_chunks", 0),
        "l1_avg_depth": l1.get("avg_depth_score", 0.0),
        "l1_sources": l1.get("sources", []),
        "graph_nodes": g.get("nodes", 0),
        "graph_edges": g.get("edges", 0),
        "graph_top_entities": g.get("top_entities", []),
        "kick_threshold": dw.kick.threshold,
        "schemas_count": len(dw.l3.list_schemas()),
    }

@app.get("/metrics")
async def metrics() -> dict:
    dw = get_orchestrator()
    l1 = dw.l1.stats()
    g = dw.l2.stats()
    return {
        "l1_chunks": l1.get("total_chunks", 0),
        "l2_nodes": g.get("nodes", 0),
        "l2_edges": g.get("edges", 0),
        "l3_schemas": len(dw.l3.list_schemas()),
        "kick_threshold": dw.kick.threshold,
        "sources_count": len(dw.list_sources()),
    }

@app.get("/gpu-stats")
async def gpu_stats() -> dict:
    """Returns GPU stats for dashboard badge."""
    import subprocess
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(",")
            used_gb = round(int(parts[0].strip()) / 1024, 1)
            total_gb = round(int(parts[1].strip()) / 1024, 1)
            return {"vendor": "NVIDIA", "vram_used_gb": used_gb, "vram_total_gb": total_gb, "backend": "CUDA"}
    except Exception:
        pass
    return {"vendor": "GPU", "vram_used_gb": 0, "vram_total_gb": 0, "backend": "unknown"}

@app.get("/sources")
async def sources() -> list[dict[str, Any]]:
    return get_orchestrator().list_sources()

@app.delete("/sources/{source_id:path}")
async def delete_source(source_id: str) -> dict[str, Any]:
    try:
        return get_orchestrator().delete_source(source_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Source deletion failed: {exc}") from exc

@app.post("/memory/save")
async def save_memory(req: MemoryPathRequest | None = None) -> dict[str, Any]:
    try:
        return get_orchestrator().save_memory(req.path if req else None)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Memory save failed: {exc}") from exc

@app.post("/memory/load")
async def load_memory(req: MemoryPathRequest | None = None) -> dict[str, Any]:
    try:
        return get_orchestrator().load_memory(req.path if req else None)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Memory load failed: {exc}") from exc

@app.delete("/memory")
async def clear_memory() -> dict[str, Any]:
    try:
        return get_orchestrator().clear_memory()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Memory clear failed: {exc}") from exc

@app.post("/ingest/url", response_model=IngestResponse)
async def ingest_url(req: UrlIngestRequest) -> IngestResponse:
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(req.url)
            response.raise_for_status()
        text = html_to_text(response.text)
        source = req.source if req.source != "url" else req.url
        result = get_orchestrator().ingest(text=text, source=source)
        return IngestResponse(status="ok", **result)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=400, detail=f"URL fetch failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"URL ingest failed: {exc}") from exc

@app.post("/ingest/youtube", response_model=IngestResponse)
async def ingest_youtube(req: YoutubeIngestRequest) -> IngestResponse:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        vid_match = re.search(r"(?:v=|youtu\.be/)([\w-]{11})", req.video_url)
        if not vid_match:
            raise HTTPException(status_code=400, detail="Could not extract YouTube video ID from URL")
        video_id = vid_match.group(1)
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        text = " ".join(entry["text"] for entry in transcript_list)
        source = req.source or f"youtube:{video_id}"
        result = get_orchestrator().ingest(text=text, source=source)
        return IngestResponse(status="ok", **result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"YouTube transcript failed: {exc}") from exc

def html_to_text(html: str) -> str:
    without_scripts = re.sub(r"<(script|style).*?>.*?</\1>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    without_tags = re.sub(r"<[^>]+>", " ", without_scripts)
    return re.sub(r"\s+", " ", without_tags).strip()

def extract_uploaded_text(filename: str, content: bytes) -> str:
    lower_name = filename.lower()
    if lower_name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(content))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"PDF text extraction failed: {exc}") from exc

    # Plain text fallback
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise HTTPException(status_code=400, detail="Unsupported file type or encoding")

def sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=True)}\n\n"

def build_retrieval_answer(query: str, context: dict[str, Any]) -> str:
    l1 = context.get("l1_surface", [])
    l2 = context.get("l2_associative", [])
    l3 = context.get("l3_structural", [])
    l4 = context.get("l4_archetypes", [])
    kick = context.get("kick", {})
    agent = context.get("agent_investigation", {})

    top_fact = l1[0].get("text", "") if l1 else "No surface memory matched this query yet."
    top_schema = l3[0] if l3 else {}
    schema_name = top_schema.get("name", "no structural schema")
    schema_description = top_schema.get("description", "No L3 structural pattern cleared the confidence threshold.")
    paths = "; ".join(item.get("path", item.get("entity", "")) for item in l2[:3]) or "No L2 graph paths were found."

    summary = (
        "TXENT Observability Memory Engine has completed layered retrieval and autonomous investigation.\n\n"
        f"Query/Alert: {query}\n\n"
        f"L3 Structural Pattern: {schema_name} - {schema_description}\n\n"
        f"L2 Associative Paths: {paths}\n\n"
        f"Kick Status: {kick.get('message', 'Kick was not evaluated')} "
        f"(Contradiction: {kick.get('contradiction_score', 0.0)}).\n\n"
    )

    if agent:
        summary += (
            f"=== Autonomous Agent Findings ===\n"
            f"Likely Root Cause: {agent.get('root_cause')} (Confidence: {int(agent.get('confidence',0)*100)}%)\n\n"
            f"Supporting Evidence:\n" + "\n".join([f"- {e}" for e in agent.get("evidence", [])]) + "\n"
        )
    return summary

@app.get("/", response_model=None)
async def serve_frontend_root():
    if FRONTEND_HTML.exists():
        return FileResponse(FRONTEND_HTML, media_type="text/html")
    return {
        "status": "TXENT API running",
        "docs": "/docs",
    }
