# Mirrors scripts/dev_web.sh for native Windows
. (Join-Path $PSScriptRoot '_dev_common.ps1')

if (-not $env:VITE_HOST) { $env:VITE_HOST = '0.0.0.0' }
if (-not $env:VITE_PORT) { $env:VITE_PORT = '5173' }
if (-not $env:VITE_API_BASE_URL) { $env:VITE_API_BASE_URL = 'http://127.0.0.1:8000/api' }

pnpm --dir (Join-Path $RootDir 'web') dev --host $env:VITE_HOST --port $env:VITE_PORT
