#!/bin/bash
set -e

echo "=== AMD MI300X detected — 192GB HBM3 VRAM ==="
echo "=== Starting vLLM with Qwen2.5-7B-Instruct (fully open, no auth needed) ==="

# Kill any stale vllm processes
pkill -f "vllm.entrypoints" 2>/dev/null || true
sleep 2

# Check if already running
if curl -s --max-time 3 http://localhost:30000/v1/models > /dev/null 2>&1; then
  echo "vLLM already running!"
  curl -s http://localhost:30000/v1/models
  exit 0
fi

echo "Launching vLLM..."
nohup python -m vllm.entrypoints.openai.api_server \
  --model "Qwen/Qwen2.5-7B-Instruct" \
  --port 30000 \
  --host 0.0.0.0 \
  --dtype float16 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.6 \
  --trust-remote-code \
  > /tmp/vllm.log 2>&1 &

VLLM_PID=$!
echo "vLLM PID: $VLLM_PID"
echo ""
echo "Waiting for server (downloading model if needed, ~14GB, may take 3-5 min)..."

for i in $(seq 1 72); do
  sleep 5
  if curl -s --max-time 3 http://localhost:30000/v1/models > /dev/null 2>&1; then
    echo ""
    echo "=============================="
    echo "  vLLM IS LIVE!"
    echo "=============================="
    curl -s http://localhost:30000/v1/models | python3 -c "import sys,json; d=json.load(sys.stdin); print('Model:', d['data'][0]['id'])" 2>/dev/null || curl -s http://localhost:30000/v1/models
    echo ""
    echo "LLM online at http://localhost:30000"
    exit 0
  fi
  echo -n "."
  if [ $((i % 12)) -eq 0 ]; then
    echo " $(( i * 5 ))s"
    tail -3 /tmp/vllm.log 2>/dev/null || true
  fi
done

echo ""
echo "=== TIMEOUT - Last 40 lines of vllm.log ==="
tail -40 /tmp/vllm.log
