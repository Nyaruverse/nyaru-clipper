# One-click installer for nyaru-clipper on Windows.
# Idempotent: safe to re-run. Existing dependencies are skipped.
# PowerShell 5.1 compatible.

#requires -Version 5.1
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$RootDir  = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$BinDir   = Join-Path $RootDir '.bin'
$DataDir  = Join-Path $RootDir 'data'
$CacheDir = Join-Path $DataDir 'model-cache'
$TempDir  = Join-Path $env:TEMP ("nyaru-setup-" + [Guid]::NewGuid().ToString('N'))

New-Item -ItemType Directory -Force -Path $BinDir, $DataDir, $CacheDir, $TempDir | Out-Null

$script:StepIndex = 0

function Write-Step {
    param([string]$Message)
    $script:StepIndex += 1
    Write-Host ""
    Write-Host ("[{0}] {1}" -f $script:StepIndex, $Message) -ForegroundColor Cyan
}

function Write-Skip {
    param([string]$Message)
    Write-Host "    skip: $Message" -ForegroundColor DarkGray
}

function Write-Ok {
    param([string]$Message)
    Write-Host "    ok:   $Message" -ForegroundColor Green
}

function Write-Fail {
    param([string]$Message)
    Write-Host ""
    Write-Host "FAILED: $Message" -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

function Invoke-DownloadWithFallback {
    param(
        [string[]]$Urls,
        [string]$Destination,
        [long]$MinSize = 1KB,
        [int]$TimeoutSec = 300
    )
    $lastErr = $null
    foreach ($url in $Urls) {
        Write-Host "      trying $url"
        try {
            Invoke-WebRequest -Uri $url -OutFile $Destination -UseBasicParsing `
                -TimeoutSec $TimeoutSec -Headers @{ 'User-Agent' = 'nyaru-clipper-setup/1.0' }
            $size = (Get-Item $Destination).Length
            if ($size -ge $MinSize) {
                Write-Host "      downloaded $size bytes"
                return
            }
            Remove-Item $Destination -Force -ErrorAction SilentlyContinue
            $lastErr = "file too small ($size bytes, expected >= $MinSize)"
        } catch {
            $lastErr = $_.Exception.Message
            Remove-Item $Destination -Force -ErrorAction SilentlyContinue
        }
    }
    throw "all mirrors failed, last error: $lastErr"
}

function Resolve-GitHubAsset {
    param(
        [string[]]$ApiUrls,
        [string]$Pattern
    )
    foreach ($apiUrl in $ApiUrls) {
        try {
            $rel = Invoke-RestMethod -Uri $apiUrl -UseBasicParsing `
                -Headers @{ 'User-Agent' = 'nyaru-clipper-setup/1.0' } -TimeoutSec 60
            # 兼容单 release 对象与 release 列表（latest 可能无资产，如 whisper.cpp v1.9.x）
            $releases = @($rel)
            if ($rel -is [System.Array]) { $releases = $rel }
            foreach ($r in $releases) {
                $asset = $r.assets | Where-Object { $_.name -match $Pattern } | Select-Object -First 1
                if ($asset) {
                    $direct = $asset.browser_download_url
                    return @(
                        $direct,
                        "https://mirror.ghproxy.com/$direct",
                        "https://ghproxy.net/$direct"
                    )
                }
            }
        } catch {
            # try next API mirror
        }
    }
    throw "could not resolve GitHub release asset matching $Pattern"
}

# ---------------------------------------------------------------------------
# Step 1: platform
# ---------------------------------------------------------------------------

function Assert-WindowsPlatform {
    Write-Step "checking platform"
    if ($env:OS -ne 'Windows_NT') {
        Write-Fail "This setup script targets Windows only. For Linux/macOS see docs/deployment-guide*.md"
    }
    if (-not [Environment]::Is64BitOperatingSystem) {
        Write-Fail "64-bit Windows is required"
    }
    $gpu = Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue |
           Where-Object { $_.Name -match 'NVIDIA' } |
           Select-Object -First 1
    if (-not $gpu) {
        Write-Warning "No NVIDIA GPU detected. whisperx / translation will fall back to CPU (slow)."
    } else {
        Write-Ok "NVIDIA GPU: $($gpu.Name)"
    }
}

# ---------------------------------------------------------------------------
# Step 2: prerequisites
# ---------------------------------------------------------------------------

function Assert-Prerequisites {
    Write-Step "checking prerequisites"

    # uv
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if (-not $uv) {
        Write-Fail @"
uv not found. Install it and re-run setup:
  winget install astral-sh.uv
  or
  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
"@
    }
    Write-Ok "uv $(uv --version)"

    # Node >= 20
    $node = Get-Command node -ErrorAction SilentlyContinue
    if (-not $node) {
        Write-Fail @"
Node.js >= 20 not found. Install it and re-run setup:
  winget install OpenJS.NodeJS.LTS
"@
    }
    $nodeVersion = node --version
    $nodeMajor = [int]($nodeVersion.TrimStart('v').Split('.')[0])
    if ($nodeMajor -lt 20) {
        Write-Fail "Node.js >= 20 required, current: $nodeVersion"
    }
    Write-Ok "node $nodeVersion"

    # pnpm via corepack
    $pnpm = Get-Command pnpm -ErrorAction SilentlyContinue
    if (-not $pnpm) {
        Write-Host "    enabling corepack for pnpm..."
        try {
            corepack enable 2>&1 | Out-Null
            corepack prepare pnpm@10.33.2 --activate 2>&1 | Out-Null
        } catch {
            # corepack may not be available
        }
        $pnpm = Get-Command pnpm -ErrorAction SilentlyContinue
        if (-not $pnpm) {
            Write-Fail "pnpm not found. Install it and re-run setup:`n  npm install -g pnpm@10.33.2"
        }
    }
    Write-Ok "pnpm $(pnpm --version)"
}

# ---------------------------------------------------------------------------
# Step 3: backend dependencies
# ---------------------------------------------------------------------------

function Install-BackendDependencies {
    Write-Step "installing backend dependencies (uv sync)"
    $venvPython = Join-Path $RootDir 'backend\.venv\Scripts\python.exe'

    # Idempotency: venv exists and core packages import
    if (Test-Path $venvPython) {
        & $venvPython -c "import fastapi,uvicorn,sqlmodel,transformers" 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Skip "backend .venv is ready"
            return
        }
    }

    Push-Location $RootDir
    try {
        & uv sync --project backend --group linux-cuda --frozen
        if ($LASTEXITCODE -ne 0) {
            Write-Fail @"
uv sync failed. Common cause: PyPI network unreachable.
Try setting a mirror and re-run:
  `$env:UV_INDEX_URL='https://pypi.tuna.tsinghua.edu.cn/simple'
"@
        }
    } finally {
        Pop-Location
    }
    Write-Ok "backend .venv ready"
}

# ---------------------------------------------------------------------------
# Step 4: torch CUDA
# ---------------------------------------------------------------------------

function Repair-TorchCuda {
    Write-Step "verifying torch CUDA build"
    $venvPython = Join-Path $RootDir 'backend\.venv\Scripts\python.exe'

    $torchInfo = & $venvPython -c "import torch;print(torch.__version__);print('yes' if torch.cuda.is_available() else 'no')" 2>$null
    $lines = $torchInfo -split "`r?`n"
    $ver = $lines[0].Trim()
    $cudaOk = $lines[1].Trim()

    if ($ver -match '\+cu' -and $cudaOk -eq 'yes') {
        Write-Skip "torch $ver with CUDA is already available"
        return
    }

    Write-Host "    current torch: $ver (cuda_available=$cudaOk), reinstalling cu128 wheels..."
    Push-Location $RootDir
    try {
        & uv pip install --python $venvPython --reinstall `
            torch==2.8.0 torchvision==0.23.0 torchaudio==2.8.0 `
            --index-url https://mirror.sjtu.edu.cn/pytorch-wheels/cu128
        if ($LASTEXITCODE -ne 0) {
            Write-Fail @"
torch cu128 installation failed.
Check network access to https://mirror.sjtu.edu.cn/pytorch-wheels/cu128
Fallback mirror: https://download.pytorch.org/whl/cu128 (may be slow in China)
"@
        }
    } finally {
        Pop-Location
    }

    # Re-verify
    $check = & $venvPython -c "import torch;print(torch.__version__);print('yes' if torch.cuda.is_available() else 'no')"
    $checkLines = $check -split "`r?`n"
    Write-Ok "torch reinstalled: $($checkLines[0]), cuda=$($checkLines[1])"
}

# ---------------------------------------------------------------------------
# Step 5: web dependencies
# ---------------------------------------------------------------------------

function Install-WebDependencies {
    Write-Step "installing web dependencies (pnpm)"
    $nodeModules = Join-Path $RootDir 'web\node_modules'
    if (Test-Path (Join-Path $nodeModules '.pnpm')) {
        Write-Skip "web/node_modules present"
        return
    }
    Push-Location (Join-Path $RootDir 'web')
    try {
        & pnpm install --frozen-lockfile
        if ($LASTEXITCODE -ne 0) {
            Write-Fail @"
pnpm install failed. If in China, try:
  pnpm config set registry https://registry.npmmirror.com
"@
        }
    } finally {
        Pop-Location
    }
    Write-Ok "web dependencies installed"
}

# ---------------------------------------------------------------------------
# Step 6: external binaries
# ---------------------------------------------------------------------------

$script:Tools = @(
    @{
        Name    = 'yt-dlp'
        Files   = @('yt-dlp.exe')
        Urls    = @(
            'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe',
            'https://mirror.ghproxy.com/https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe',
            'https://ghproxy.net/https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe'
        )
        Type    = 'raw'
        MinSize = 10MB
    },
    @{
        Name    = 'BBDown'
        Files   = @('BBDown.exe')
        ApiUrls = @(
            'https://api.github.com/repos/nilaoda/BBDown/releases/latest',
            'https://mirror.ghproxy.com/https://api.github.com/repos/nilaoda/BBDown/releases/latest'
        )
        AssetPattern = 'BBDown_\d+.*win-x64\.zip'
        Type    = 'zip-extract'
        Extract = @('BBDown.exe')
        MinSize = 5MB
    },
    @{
        Name    = 'ffmpeg'
        Files   = @('ffmpeg.exe', 'ffprobe.exe')
        ApiUrls = @(
            'https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest',
            'https://mirror.ghproxy.com/https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest'
        )
        AssetPattern = 'ffmpeg-master-latest-win64-gpl\.zip$'
        Type    = 'zip-extract'
        Extract = @('bin/ffmpeg.exe', 'bin/ffprobe.exe')
        MinSize = 50MB
    },
    @{
        Name    = 'whisper.cpp'
        Files   = @('whisper-cli.exe', 'whisper.dll', 'ggml.dll', 'ggml-base.dll', 'ggml-cuda.dll', 'cublas64_12.dll', 'cudart64_12.dll', 'SDL2.dll')
        ApiUrls = @(
            'https://api.github.com/repos/ggerganov/whisper.cpp/releases/latest',
            'https://api.github.com/repos/ggerganov/whisper.cpp/releases?per_page=15',
            'https://mirror.ghproxy.com/https://api.github.com/repos/ggerganov/whisper.cpp/releases/latest',
            'https://mirror.ghproxy.com/https://api.github.com/repos/ggerganov/whisper.cpp/releases?per_page=15'
        )
        AssetPattern = 'whisper-bin-win-cuda-12\.4\.0-x64\.zip$'
        Type    = 'zip-extract'
        Extract = @('whisper-cli.exe', 'whisper.dll', 'ggml.dll', 'ggml-base.dll', 'SDL2.dll',
                    'ggml-cpu-x64.dll', 'ggml-cpu-sse42.dll', 'ggml-cpu-sandybridge.dll',
                    'ggml-cpu-haswell.dll', 'ggml-cpu-skylakex.dll', 'ggml-cpu-cascadelake.dll',
                    'ggml-cpu-icelake.dll', 'ggml-cpu-cannonlake.dll', 'ggml-cpu-alderlake.dll',
                    'ggml-cuda.dll', 'cublas64_12.dll', 'cublasLt64_12.dll', 'cudart64_12.dll',
                    'nvblas64_12.dll', 'nvrtc64_120_0.dll', 'nvrtc-builtins64_124.dll')
        MinSize = 100MB
    }
)

function Install-RawTool {
    param($Tool)
    $dest = Join-Path $BinDir $Tool.Files[0]
    Invoke-DownloadWithFallback -Urls $Tool.Urls -Destination $dest -MinSize $Tool.MinSize
}

function Install-ZipTool {
    param($Tool)
    $zipPath = Join-Path $TempDir "$($Tool.Name).zip"
    $extractRoot = Join-Path $TempDir "$($Tool.Name)-x"

    $urls = Resolve-GitHubAsset -ApiUrls $Tool.ApiUrls -Pattern $Tool.AssetPattern
    Invoke-DownloadWithFallback -Urls $urls -Destination $zipPath -MinSize $Tool.MinSize

    if (Test-Path $extractRoot) { Remove-Item -Recurse -Force $extractRoot }
    Expand-Archive -Path $zipPath -DestinationPath $extractRoot -Force

    foreach ($sub in $Tool.Extract) {
        $leaf = Split-Path $sub -Leaf
        # ffmpeg zip has a top-level directory; find by filename anywhere inside
        $src = Get-ChildItem -Path $extractRoot -Recurse -Filter $leaf -ErrorAction SilentlyContinue |
               Select-Object -First 1
        if (-not $src) {
            throw "extracted file not found: $sub"
        }
        Copy-Item $src.FullName (Join-Path $BinDir $src.Name) -Force
    }
}

function Install-ZipExtractAll {
    param($Tool)
    $zipPath = Join-Path $TempDir "$($Tool.Name).zip"
    $urls = Resolve-GitHubAsset -ApiUrls $Tool.ApiUrls -Pattern $Tool.AssetPattern
    Invoke-DownloadWithFallback -Urls $urls -Destination $zipPath -MinSize $Tool.MinSize
    Expand-Archive -Path $zipPath -DestinationPath $BinDir -Force
}

function Install-BinaryTools {
    Write-Step "installing external binaries to .bin/"
    foreach ($tool in $script:Tools) {
        $missing = $tool.Files | Where-Object { -not (Test-Path (Join-Path $BinDir $_)) }
        if (-not $missing) {
            Write-Skip "$($tool.Name) present"
            continue
        }
        Write-Host "    fetching $($tool.Name) (missing: $($missing -join ', '))..."
        try {
            switch ($tool.Type) {
                'raw'             { Install-RawTool $tool }
                'zip-extract'     { Install-ZipTool $tool }
                'zip-extract-all' { Install-ZipExtractAll $tool }
            }
        } catch {
            Write-Fail @"
$($tool.Name) download failed: $_
Manual fix: download the files below and place them in $BinDir, then re-run setup:
  $($tool.Files -join "`n  ")
"@
        }
        $stillMissing = $tool.Files | Where-Object { -not (Test-Path (Join-Path $BinDir $_)) }
        if ($stillMissing) {
            Write-Fail "$($tool.Name) installed but still missing: $($stillMissing -join ', ')"
        }
        Write-Ok "$($tool.Name) installed"
    }
}

# ---------------------------------------------------------------------------
# Step 7: whisper model
# ---------------------------------------------------------------------------

$script:WhisperModelExpectedSize = 487601967  # bytes (466 MB)

function Install-WhisperModel {
    Write-Step "installing whisper.cpp ASR model"
    $destDir  = Join-Path $CacheDir 'whisper.cpp'
    $destPath = Join-Path $destDir 'ggml-small.bin'
    New-Item -ItemType Directory -Force -Path $destDir | Out-Null

    # Idempotency: already present with correct size
    if ((Test-Path $destPath) -and (Get-Item $destPath).Length -eq $script:WhisperModelExpectedSize) {
        Write-Skip "ggml-small.bin present ($($script:WhisperModelExpectedSize) bytes)"
        return
    }

    # User explicitly set a custom model path
    if ($env:NYARU_WHISPER_MODEL -and (Test-Path $env:NYARU_WHISPER_MODEL)) {
        Write-Skip "NYARU_WHISPER_MODEL is set, skipping download"
        return
    }

    # Migrate from legacy location (~/.cache/nyaru-clipper/models/)
    $legacy = Join-Path $env:USERPROFILE '.cache\nyaru-clipper\models\ggml-small.bin'
    if (Test-Path $legacy) {
        Write-Host "    migrating from $legacy"
        Copy-Item $legacy $destPath -Force
        if ((Get-Item $destPath).Length -eq $script:WhisperModelExpectedSize) {
            Write-Ok "migrated"
            return
        }
        Remove-Item $destPath -Force -ErrorAction SilentlyContinue
    }

    # Download (China mirror first)
    $urls = @(
        'https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-small.bin',
        'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin'
    )
    Write-Host "    downloading ggml-small.bin (~466 MB)..."
    Invoke-DownloadWithFallback -Urls $urls -Destination $destPath `
        -MinSize $script:WhisperModelExpectedSize -TimeoutSec 1800

    $actual = (Get-Item $destPath).Length
    if ($actual -ne $script:WhisperModelExpectedSize) {
        Remove-Item $destPath -Force -ErrorAction SilentlyContinue
        Write-Fail "ggml-small.bin size mismatch (expected $($script:WhisperModelExpectedSize), got $actual)"
    }
    Write-Ok "ggml-small.bin ($actual bytes)"
}

# ---------------------------------------------------------------------------
# Step 8: summary
# ---------------------------------------------------------------------------

function Write-Summary {
    Write-Step "setup complete"
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host "  setup complete" -ForegroundColor Green
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "next:  .\start-all.bat"
    Write-Host ""
    Write-Host "optional configuration:"
    Write-Host "  - DeepSeek API key (for translation/proofreading):"
    Write-Host "    open http://127.0.0.1:5173 after startup, go to Settings page"
    Write-Host "  - Bilibili cookie (for member-only videos):"
    Write-Host "    set APP_BILIBILI_COOKIE_PATH to your cookie file"
    Write-Host "  - Custom whisper model path:"
    Write-Host "    set NYARU_WHISPER_MODEL environment variable"
    Write-Host ""
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

try {
    Assert-WindowsPlatform
    Assert-Prerequisites
    Install-BackendDependencies
    Repair-TorchCuda
    Install-WebDependencies
    Install-BinaryTools
    Install-WhisperModel
    Write-Summary
} finally {
    Remove-Item -Recurse -Force $TempDir -ErrorAction SilentlyContinue
}
