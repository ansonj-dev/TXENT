#!/bin/bash
# Update .env and restart Dreamweave API

cat > /app/dreamweave/.env << 'ENVEOF'
LLM_URL=http://localhost:30000/v1/chat/completions
LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
KICK_THRESHOLD=0.42
API_PORT=8000
EMBEDDING_MODEL=all-mpnet-base-v2
DREAMWEAVE_MEMORY_DIR=/app/dreamweave/memory_store
DREAMWEAVE_AUTO_LOAD=true
DREAMWEAVE_AUTO_SAVE=true
CI=false
ENVEOF

echo "=== .env updated ==="
cat /app/dreamweave/.env

echo ""
echo "=== Restarting Dreamweave API ==="
pkill -f "uvicorn api.main" 2>/dev/null || true
sleep 2
cd /app/dreamweave
uvicorn api.main:app --host 0.0.0.0 --port 8000 > /tmp/dreamweave.log 2>&1 &
sleep 5
curl -s http://localhost:8000/health | python3 -c "import sys,json; d=json.load(sys.stdin); print('Status:', d['status'], '| LLM URL:', d['llm_url'], '| LLM Model:', d['llm_model'])"

echo ""
echo "=== Test LLM via Dreamweave /health/llm ==="
curl -s http://localhost:8000/health/llm
