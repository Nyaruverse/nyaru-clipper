# Mirrors scripts/dev_worker.sh for native Windows
. (Join-Path $PSScriptRoot '_dev_common.ps1')

Setup-BackendDevEnv
Require-BackendPython

Set-Location $BackendDir
& $BackendPythonPath -c "from app.worker import worker_loop; worker_loop()"
