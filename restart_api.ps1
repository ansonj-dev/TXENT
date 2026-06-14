# Windows PowerShell Script to restart the TXENT API Server
# Sets up PYTHONPATH and runs uvicorn on port 8000

$env:PYTHONPATH="."

echo "=== Stopping any active TXENT API processes ==="
$processes = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { 
    $_.CommandLine -like "*uvicorn*" -or $_.CommandLine -like "*api.main*" 
}
if ($processes) {
    echo "Found active uvicorn processes. Terminating..."
    $processes | Stop-Process -Force
    Start-Sleep -Seconds 2
} else {
    echo "No active uvicorn processes found."
}

echo "=== Starting TXENT API Server on port 8000 ==="
Start-Process -NoNewWindow -FilePath "python" -ArgumentList "-m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload"

Start-Sleep -Seconds 3
echo ""
echo "=== Server Started successfully! ==="
echo "Navigate to http://localhost:8000 in your browser."
echo "Running unit tests check..."
$env:PYTHONPATH="."; python test/test_txent_flow.py
