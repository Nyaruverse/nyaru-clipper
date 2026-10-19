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
if (-not $Python) { $Python = Join-Path $repoRoot 'backend\.venv\Scripts\python.exe' }
if (-not $Model) { $Model = Join-Path $repoRoot 'data\model-cache\whisper.cpp\ggml-small.bin' }
if (-not $OutputDir) { $OutputDir = Join-Path $repoRoot 'data\companion' }
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw 'Python environment missing. Run scripts\setup.ps1 first.'
}

# 单进程方案：启动前清理占用目标端口的旧进程，避免重复启动时新旧并存
$occupants = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($procId in $occupants) {
    $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
    if ($proc) {
        Write-Host "停止占用端口 $Port 的旧进程：$($proc.ProcessName) (PID $procId)"
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
}

$previousPath = $env:PATH
$previousUtf8 = $env:PYTHONUTF8
$previousNoBytecode = $env:PYTHONDONTWRITEBYTECODE
try {
    $env:PATH = "$(Split-Path -Parent $Python);$(Join-Path $repoRoot '.bin');$previousPath"
    # Job manifests and subtitles contain UTF-8 regardless of the Windows code page.
    $env:PYTHONUTF8 = '1'
    # 禁止字节码缓存，确保每次都从 .py 源文件加载最新代码
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $cliArgs = @((Join-Path $PSScriptRoot 'local_companion.py'), $Command, '--model', $Model, '--threads', $Threads)
    if ($Command -eq 'gui') { $cliArgs += @('--port', $Port, '--output-dir', $OutputDir) }
    & $Python @cliArgs
    $result = $LASTEXITCODE
}
finally {
    $env:PATH = $previousPath
    $env:PYTHONUTF8 = $previousUtf8
    $env:PYTHONDONTWRITEBYTECODE = $previousNoBytecode
}
exit $result
