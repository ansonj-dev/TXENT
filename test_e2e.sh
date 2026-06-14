#!/bin/bash
echo "=== Full E2E Test: Real LLM Query ==="
curl -s -X POST http://localhost:8000/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query":"What is network theory?","generate_answer":true,"max_tokens":200}' \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('Answer:', d.get('answer','')[:300])
print('Latency:', d.get('latency_ms','?'), 'ms')
print('L1 chunks:', len(d.get('l1_surface',[])))
"

echo ""
echo "=== LLM Health ==="
curl -s http://localhost:8000/health/llm

echo ""
echo "=== Full Health ==="
curl -s http://localhost:8000/health | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('Status:', d['status'])
print('LLM URL:', d['llm_url'])
print('LLM Model:', d['llm_model'])
print('L1 Chunks:', d['l1_stats']['total_chunks'])
print('Graph Nodes:', d['graph_stats']['nodes'])
"
