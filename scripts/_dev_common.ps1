# Shared setup for Windows dev launchers, mirrors scripts/_dev_common.sh
$ErrorActionPreference = 'Stop'

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$BackendDir = Join-Path $RootDir 'backend'
$BackendVenvDir = Join-Path $BackendDir '.venv'
$BackendPythonPath = Join-Path $BackendVenvDir 'Scripts\python.exe'

$env:PATH = "$RootDir\.bin;$env:PATH"

function Require-BackendPython {
    if (-not (Test-Path $BackendPythonPath)) {
        Write-Error "backend environment is missing: $BackendPythonPath`nrun: uv sync --project backend --group linux-cuda --frozen"
        exit 1
    }
}

function Setup-BackendDevEnv {
    $dataDir = if ($env:APP_DATA_DIR) { $env:APP_DATA_DIR } else { Join-Path $RootDir 'data' }
    $modelCacheRoot = if ($env:APP_MODEL_CACHE_ROOT) { $env:APP_MODEL_CACHE_ROOT } else { Join-Path $dataDir 'model-cache' }
    $whisperxCacheDir = if ($env:APP_WHISPERX_MODEL_CACHE_DIR) { $env:APP_WHISPERX_MODEL_CACHE_DIR } else { Join-Path $modelCacheRoot 'whisperx' }
    $hfHome = if ($env:HF_HOME) { $env:HF_HOME } else { Join-Path $modelCacheRoot 'hf' }

    New-Item -ItemType Directory -Force -Path $dataDir, $modelCacheRoot, $whisperxCacheDir, $hfHome | Out-Null

    $env:APP_DATA_DIR = $dataDir
    $env:APP_WHISPERX_MODEL_CACHE_DIR = $whisperxCacheDir
    $env:HF_HOME = $hfHome
    if (-not $env:TRANSFORMERS_CACHE) { $env:TRANSFORMERS_CACHE = $hfHome }
}
