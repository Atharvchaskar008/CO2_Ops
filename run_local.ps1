# CO2Ops - Local Development Runner
# Launches the AWS-native FastAPI Backend on port 8080 and Custom Frontend on port 8501.

$VenvDir = Join-Path $PSScriptRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating Virtual Environment at $VenvDir..." -ForegroundColor Cyan
    python -m venv $VenvDir
}

Write-Host "Activating Virtual Environment..." -ForegroundColor Green
& (Join-Path $VenvDir "Scripts\Activate.ps1")

Write-Host "Ensuring dependencies are installed..." -ForegroundColor Cyan
& $VenvPython -m pip install -q -r (Join-Path $PSScriptRoot "co2ops_agent\requirements.txt")

Write-Host "`nStarting CO2Ops FastAPI Backend Server on http://127.0.0.1:8080..." -ForegroundColor Yellow
$BackendJob = Start-Job -Name "CO2Ops_Backend" -ScriptBlock {
    param($PythonExe, $RootDir)
    Set-Location $RootDir
    & $PythonExe -m uvicorn co2ops_agent.api:app --port 8080 --host 127.0.0.1
} -ArgumentList $VenvPython, $PSScriptRoot

Start-Sleep -Seconds 3

Write-Host "Starting Frontend Server on http://127.0.0.1:8501..." -ForegroundColor Yellow
Write-Host "Open http://127.0.0.1:8501 in your browser to access the CO2Ops AWS Sustainability Console." -ForegroundColor Green
Write-Host "Press Ctrl+C to terminate both servers.`n" -ForegroundColor DarkGray

try {
    Set-Location (Join-Path $PSScriptRoot "Frontend")
    & $VenvPython -m http.server 8501
} finally {
    Write-Host "`nShutting down CO2Ops Backend..." -ForegroundColor Yellow
    Stop-Job -Name "CO2Ops_Backend" -ErrorAction SilentlyContinue
    Remove-Job -Name "CO2Ops_Backend" -ErrorAction SilentlyContinue
    Write-Host "CO2Ops servers terminated cleanly." -ForegroundColor Green
}
