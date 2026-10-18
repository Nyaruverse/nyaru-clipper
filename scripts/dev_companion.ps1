param(
    [ValidateSet('gui', 'doctor')]
    [string]$Command = 'gui',
    [string]$Python = '',
    [string]$Model = '',
    [string]$OutputDir = '',
    [ValidateRange(1, 65535)]
    [int]$Port = 8787,
    [ValidateRange(1, 64)]
    [int]$Threads = 4
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $Python) { $Python = Join-Path $repoRoot '.venv\Scripts\python.exe' }
if (-not $Model) { $Model = Join-Path $repoRoot 'data\model-cache\whispercpp\ggml-small.bin' }
if (-not $OutputDir) { $OutputDir = Join-Path $repoRoot 'data\local-runs' }
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw 'Python environment missing. Follow the Windows setup in docs/local-companion.md.'
}

$previousPath = $env:PATH
$previousUtf8 = $env:PYTHONUTF8
try {
    $env:PATH = "$(Split-Path -Parent $Python);$(Join-Path $repoRoot '.bin');$previousPath"
    # Job manifests and subtitles contain UTF-8 regardless of the Windows code page.
    $env:PYTHONUTF8 = '1'
    $cliArgs = @((Join-Path $PSScriptRoot 'local_companion.py'), $Command, '--model', $Model, '--threads', $Threads)
    if ($Command -eq 'gui') { $cliArgs += @('--port', $Port, '--output-dir', $OutputDir) }
    & $Python @cliArgs
    $result = $LASTEXITCODE
}
finally {
    $env:PATH = $previousPath
    $env:PYTHONUTF8 = $previousUtf8
}
exit $result
