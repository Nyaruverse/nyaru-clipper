# Mirrors scripts/dev_api.sh for native Windows
. (Join-Path $PSScriptRoot '_dev_common.ps1')

Setup-BackendDevEnv
Require-BackendPython

if (-not $env:APP_HOST) { $env:APP_HOST = '0.0.0.0' }
if (-not $env:APP_PORT) { $env:APP_PORT = '8000' }

Set-Location $BackendDir
& $BackendPythonPath -m uvicorn app.main:app --host $env:APP_HOST --port $env:APP_PORT
