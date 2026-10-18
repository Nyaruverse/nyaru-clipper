# Windows 部署

适用于独立 Companion（NVIDIA GPU／CUDA，无需 Docker）。假设已有 PowerShell 7 和 NVIDIA 显卡驱动，项目已下载；项目命令均在仓库根目录执行。

## 安装

以管理员身份打开 PowerShell 7，安装系统工具：

```powershell
winget install --exact --id Python.Python.3.11 --source winget
winget install --exact --id astral-sh.uv --source winget
winget install --exact --id CoreyButler.NVMforWindows --source winget
winget install --exact --id Gyan.FFmpeg --source winget
```

关闭终端，重新以管理员身份打开 PowerShell 7，再用 nvm 安装 Node.js：

```powershell
nvm install 24.15.0
nvm use 24.15.0
node --version
```

回到仓库根目录，安装 Python 依赖到 `.venv`：

```powershell
$env:UV_CACHE_DIR = Join-Path $PWD '.cache/uv'
uv venv --python 3.11 --no-python-downloads .venv
uv pip install --python .venv/Scripts/python.exe `
  'pydantic-settings>=2.6,<3' 'sqlmodel>=0.0.22,<1' `
  'anyio>=4,<5' 'httpx>=0.28,<1' 'PyJWT[crypto]>=2.10,<3' `
  'fastapi>=0.115,<1' 'uvicorn>=0.32,<1' yt-dlp
```

安装 pnpm 到 `.tools/pnpm`，安装前端依赖到 `web/node_modules` 并构建：

```powershell
npm install --prefix .tools/pnpm --no-package-lock --cache .cache/npm pnpm@10.33.2
node .tools/pnpm/node_modules/pnpm/bin/pnpm.cjs --dir web install --frozen-lockfile --store-dir "$PWD/.cache/pnpm"
node .tools/pnpm/node_modules/pnpm/bin/pnpm.cjs --dir web build
```

安装 CUDA 版 whisper.cpp 到 `.bin`，下载多语种模型到 `data/model-cache/whispercpp`：

```powershell
New-Item -ItemType Directory -Force .tools, .bin, data/model-cache/whispercpp | Out-Null
Invoke-WebRequest 'https://github.com/ggml-org/whisper.cpp/releases/download/v1.9.2/whisper-cublas-12.4.0-bin-x64.zip' -OutFile .tools/whisper-cuda.zip
if ((Get-FileHash .tools/whisper-cuda.zip -Algorithm SHA256).Hash -ne '443110ddaad70d4290ab2e77179e31cf712035bbc4fad56bb4519a90c917b39c') { throw 'whisper.cpp 下载校验失败' }
Expand-Archive .tools/whisper-cuda.zip -DestinationPath .tools/whisper-cuda -Force
Copy-Item .tools/whisper-cuda/Release/whisper-cli.exe .bin/ -Force
Copy-Item .tools/whisper-cuda/Release/*.dll .bin/ -Force
Invoke-WebRequest 'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin' -OutFile data/model-cache/whispercpp/ggml-small.bin
```

## 运行

检查依赖：

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\dev_companion.ps1 -Command doctor
nvidia-smi
```

启动，保留终端：

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\dev_companion.ps1
```

浏览器打开 <http://127.0.0.1:8787>。

识别期间在另一个终端观察 GPU；任务 ASR 日志应加载 CUDA 后端。`doctor` 只检查依赖，不验证 GPU 推理。

```powershell
nvidia-smi -l 1
```

关闭：在启动终端按 `Ctrl+C`；也可在仓库根目录的另一个 PowerShell 7 终端执行：

```powershell
$entry = (Resolve-Path .\scripts\local_companion.py).Path
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
  Where-Object { $_.CommandLine -and $_.CommandLine.Contains($entry) } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
```
