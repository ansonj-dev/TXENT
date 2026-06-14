#!/bin/bash
set -e

DREAMWEAVE_DIR="/app/dreamweave"
cd "$DREAMWEAVE_DIR"

echo "=== [1/5] Checking GPU ==="
rocm-smi 2>/dev/null || echo "rocm-smi not found, skipping"

echo ""
echo "=== [2/5] Writing .env ==="
cat > "$DREAMWEAVE_DIR/.env" << 'ENVEOF'
LLM_URL=http://localhost:30000/v1/chat/completions
LLM_MODEL=meta-llama/Meta-Llama-3-8B-Instruct
KICK_THRESHOLD=0.42
API_PORT=8000
EMBEDDING_MODEL=all-mpnet-base-v2
DREAMWEAVE_MEMORY_DIR=/app/dreamweave/memory_store
DREAMWEAVE_AUTO_LOAD=true
DREAMWEAVE_AUTO_SAVE=true
CI=false
ENVEOF
echo ".env written"
cat "$DREAMWEAVE_DIR/.env"

echo ""
echo "=== [3/5] Checking spacy model ==="
python -c "import spacy; nlp = spacy.load('en_core_web_lg'); print('spacy model OK:', nlp.meta['name'])"

echo ""
echo "=== [4/5] Installing any missing deps ==="
pip install -q fastapi uvicorn qdrant-client sentence-transformers spacy networkx httpx numpy scikit-learn python-dotenv pydantic python-multipart pypdf

echo ""
echo "=== [5/5] Quick import sanity check ==="
python -c "
import sys
sys.path.insert(0, '/app/dreamweave')
from dotenv import load_dotenv
load_dotenv('/app/dreamweave/.env')
print('dotenv OK')
import fastapi, uvicorn, qdrant_client, sentence_transformers, spacy, networkx, httpx, numpy, sklearn, pydantic, pypdf
print('all imports OK')
from api.main import app
print('FastAPI app import OK')
print('READY TO RUN')
"
