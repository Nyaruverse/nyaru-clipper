# 第二阶段：发布验证入口实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` or `executing-plans` task by task. 下列复选框仅在实际执行并保存证据后勾选。

**Goal:** 完成原改进计划 #12、#32、#43、#44，使依赖检查、数据库 readiness、浏览器选择和发布 smoke 的结果可信。

**Architecture:** 延续宿主机 `uv + pnpm` 主路径、Docker 备用路径及独立 macOS Companion。复用现有脚本和路由；先固定依赖与健康／浏览器契约，再收尾 smoke，四项分别验收。

**Tech Stack:** Python `>=3.11,<3.12`、Bash、uv、FastAPI、SQLite、React/TypeScript、pnpm `10.33.2`、Playwright、pytest。

对应英文：[Implementation plan](/Users/drm/project/nyaru-clipper/docs/superpowers/plans/2026-10-21-phase2-release-validation.md)。来源：[44 项改进计划](/Users/drm/project/nyaru-clipper/docs/code-improvement-plan-2026-10-20.zh-CN.md)、[第一阶段结果](/Users/drm/project/nyaru-clipper/docs/phase1-improvement-results-2026-10-21.zh-CN.md)。

## Global Constraints

- 执行结果：**四项均已实现，与第一阶段共同完成本轮记录范围内的合并验收，最终 gate APPROVE、无阻塞项；总账 13 已验收／31 待处理**。实际命令、数量和平台限制见[第二阶段结果](/Users/drm/project/nyaru-clipper/docs/phase2-improvement-results-2026-10-21.zh-CN.md)。下文基线和 proposed 代码保留准备时设计；勾选只对应已有证据，平台全栈推广项保持未勾选。
- 继续使用 `/Users/drm/project/nyaru-clipper` 的 `codex/code-improvement-2026-10-21`，保护第一阶段全部未提交修改及既有文档，不重新导入或重置 Companion 原工作树。
- 准备阶段仅新增计划和预检记录。随后用户授权本阶段实现及隔离临时验证；仍不安装 App、不启动业务服务／录制／监控，不提交、推送或合并。
- 实施使用临时数据库、媒体、端口与数据目录；不读取真实授权或使用真实供应商。Docker Compose 现有 `../data` 挂载不能直接用于隔离验收，须覆盖为临时目录。
- 保持可信本机／LAN、单用户、单 GPU worker；不改公网认证、多用户或 GPU 架构。
- 不手改 `requirements*.txt`、OpenAPI 或生成类型。修复不得借机升级运行依赖或放宽失败断言。
- 每项保留修复前失败、修复后期望行为、实际入口和局限；不能把测试清单非空当成浏览器／发布验收。
- 文档变更成对维护。未得到独立授权不自动提交或发布；下文“交付”指本地可审阅候选。

## 已核对的起点

2026-10-21 现场：分支如上，HEAD `e8ea71085cf5c6ff6f671499872f5c166d31f89b`，181 个 dirty entries。`backend/.venv` 不存在，第一阶段独立证据环境仍可执行。旧项目交接的安装版／运行状态不作为本轮现场事实。

第一阶段结果是历史验收基线：290 项专项通过，完整后端 970 通过／1 失败；本次未重跑。失败项为 `test_export_script_prefers_the_backend_virtualenv_python_over_system_python`，它依赖真实 checkout 中不存在的 `.venv`；随 #32 改成自包含环境夹具，不能删除或跳过。

| 原编号 | 准备时源码观察 | 本阶段交付物 | 准备时状态 |
| --- | --- | --- | --- |
| #32（中） | 检查与生成都在临时空输出上 `uv pip compile`，且所有安装入口先解析三种配置 | 固定版本校验与显式升级分开，按目标配置检查 | planned |
| #43（中） | health 只取得 engine，没有执行查询；Compose 还探测根路径 | 有界真实 DB readiness，消费者采用同一契约 | planned |
| #44（低） | 路径位于 `use.executablePath` | runner 及真实浏览器使用 `use.launchOptions.executablePath` | planned |
| #12（中） | 共用 smoke 仍选择不存在的 `e2e/task-flow.spec.ts` | 当前工作站和独立 Companion 的有效发布检查 | planned |

只执行了浏览器测试**清单**预检：现有 5 个工作站文件共 17 项，未启动浏览器。记录：[正确工作目录下的清单](/Users/drm/project/nyaru-clipper/.omo/evidence/phase2-preparation-2026-10-21/workstation-test-list-corrected.log)。先前在仓库根目录调用 Corepack 误选系统 pnpm 的失败日志亦保留；后续在 `web/` 中运行固定版本，不修改全局配置或关闭版本检查。

## 顺序与接口

执行顺序：**Task 1 #32 → Task 2 #43 → Task 3 #44 → Task 4 #12 → 合并验收**。#43／#44 没有逻辑依赖，可以在明确文件所有权后并行；#12 最后串联，不与 #44 同时编辑 Playwright 配置。

| 边界 | 选定的实施契约 |
| --- | --- |
| 依赖声明／锁定版本 | `backend/pyproject.toml` 继续定义需求与平台配置；三份已提交 `requirements*.txt` 是对应安装路径的固定运行版本产物。`backend/uv.lock` 保留其开发环境用途，不悄悄切换为这些产物的版本来源或强行对齐两套版本。 |
| 校验／升级 | `--check --profile base\|linux-cuda\|wsl-rocm\|all` 受现有固定版本约束；只有显式 `--upgrade` 允许重新选版。默认仍处理 all，保留 `--output PATH` 仅基础产物语义。 |
| 健康 | 继续 `/api/health`，作为 readiness：DB 可读 200／`status=ok,database=ok`，失败 503／`status=error,database=error`；保留 `runtime_capabilities` 和正常响应字段。GPU 警告不因此阻止启动。 |
| 工作站浏览器 | 主配置仍由 Vite 提供页面；选用现有 5 个工作站 spec。 |
| Companion 浏览器 | 另用无 Vite webServer 的配置，访问 CLI／冻结后端实际提供的同源页面及 API；不套用工作站 `/api/v2` 契约。 |

### Task 1：#32 固定版本校验与平台隔离

**Files:**

- 修改 `/Users/drm/project/nyaru-clipper/scripts/export_backend_requirements.sh`、`/Users/drm/project/nyaru-clipper/scripts/_backend_profile_common.sh`。
- 测试 `/Users/drm/project/nyaru-clipper/backend/tests/test_requirements_export.py`。
- 更新 `/Users/drm/project/nyaru-clipper/docs/deployment-guide.md`、`/Users/drm/project/nyaru-clipper/docs/deployment-guide.zh-CN.md`、`/Users/drm/project/nyaru-clipper/scripts/AGENTS.md` 中对应契约。
- 仅必要时通过生成脚本更新三份 requirements；默认锁定路径应保持现有版本。无需新增依赖管理服务或第二套清单数据库。

**Interfaces:** 输入为现有 pyproject、三份固定产物和 Python 3.11；输出为进程退出码及生成文件。安装 helper 传当前 `profile_name` 给导出检查。`--check` 不写权威产物，任何未选中平台均不调用其编译函数。

- [x] **1. 写自包含失败用例。** 在 `tmp_path` 创建最小 checkout，复制真实脚本、pyproject、固定产物；在这个临时 checkout 创建 `.venv/bin/python` 包装器，使用 `shlex.quote(sys.executable)`，并把 PATH 上 `python3` 换成 exit 77。断言脚本优先临时 `.venv`；另测显式 `BACKEND_PYTHON` 优先级及缺失解释器的明确失败。不得创建／替换主 checkout 的 `.venv` 来蒙混通过。
- [x] **2. 重现版本漂移。** 用受控 uv 可执行文件记录 argv：未提供约束时返回模拟新版，受约束时返回原版。两次只改变模拟“可见最新版本”，`--check --profile base` 都应为 0；提高临时声明的最低版本使原 pin 不再满足时应非零。再令 ROCm 求解必失败，确认 base／CUDA 检查不调用它。保留缺文件、比较漂移和共享依赖 pin 一致性断言。
- [x] **3. 最小实现。** 增加 `--profile` 与 `--upgrade` 解析；锁定模式先从**权威产物**生成约束，再编译到临时输出并比较；禁止用刚重新求解的版本作为自己的约束。选中 profile 同时校验基础与该 profile；过滤约束中的注释、`./backend` 和 index 参数，ROCm index 仍从已有配置传入。核心规则如下，嵌入现有函数而非新增框架：

  ```bash
  # proposed: compile arguments are arrays, never command strings
  compile_args=()
  if ((UPGRADE)); then
    compile_args+=(--upgrade)
  else
    write_constraints_file "${DEFAULT_OUTPUT_PATH}" "${GENERIC_CONSTRAINTS_PATH}"
    compile_args+=(--constraints "${GENERIC_CONSTRAINTS_PATH}")
  fi
  uv pip compile "${GENERIC_INPUT_PATH}" --project "${BACKEND_DIR}" \
    --python-version 3.11 --python-platform x86_64-unknown-linux-gnu \
    --no-header --no-annotate "${compile_args[@]}" >"${GENERIC_RAW_PATH}"
  ```

  profile 编译还加入对应固定 profile 的约束；基础／profile 共享 pin 不一致直接失败，不静默改版本。`--check` 与 `--upgrade` 同时出现应拒绝；`--output` 隐含 base，与显式非 base profile 同用则拒绝。缺少锁定产物只允许显式升级／首次生成路径。升级模式先编译基础，再从候选基础产物生成 profile 约束。锁定校验仍可能需要固定包元数据或缓存，**不承诺全新空缓存离线可运行**。
- [x] **4. 修正安装调用与记录。** helper 改为 `bash "${ROOT_DIR}/scripts/export_backend_requirements.sh" --check --profile "${profile_name}"`；保留先建立 Python 3.11 venv、再验证、再 sync，以及 WSL HIP 构建顺序。若显式更新基础 pin，三个产物须一起生成并检查共享版本，不能只更新一份后宣布可安装。
- [x] **5. 验证与交付。** 运行下列命令，预期全部通过且 `--check` 前后三份产物哈希不变；未选平台不可触发求解。保存 red/green、argv、版本与哈希清单。

  ```bash
  cd /Users/drm/project/nyaru-clipper
  PYTHONPATH=backend .omo/evidence/phase1-improvement-2026-10-21/venv/bin/python -m pytest backend/tests/test_requirements_export.py -q
  BACKEND_PYTHON="$PWD/.omo/evidence/phase1-improvement-2026-10-21/venv/bin/python" ./scripts/export_backend_requirements.sh --check --profile base
  ./scripts/install_backend_linux_cuda.sh --dry-run
  ./scripts/install_backend_wsl_rocm.sh --dry-run
  ```

### Task 2：#43 有界数据库 readiness

**Files:** 修改 `/Users/drm/project/nyaru-clipper/backend/app/api/routes/health.py`；扩展 `backend/tests/test_runtime_api.py`；更新 `scripts/dev_up.sh`、`scripts/_release_smoke_common.sh`、`infra/docker-compose.yml` 及双语 deployment/operator 文档。如声明新增 503 OpenAPI 响应，使用现有生成器更新 `web/openapi.json` 与 `web/src/generated/api-schema.ts`。

**Interfaces:** `healthcheck(response: Response) -> dict[str, object]` 保留现有正常载荷；新增健康模块内 `_database_is_readable() -> bool`。当前持久 SQLite 路径使用独立只读连接，避免缓存 engine／已打开文件掩盖新连接失败，不改变业务会话超时。

- [x] **1. 写失败用例。** 正常临时 DB 返回 200；启动后把临时 DB 所在目录移开并 dispose 业务连接，再请求 tasks 和 health，后者必须 503；恢复目录／连接后 health 回到 200。另用真实 SQLite 排他锁覆盖 1 秒 busy timeout，断言探测在 2 秒内失败；缺表／不存在的 DB 也失败且不创建新文件。响应不得泄漏 DB URL、绝对路径或原始异常。
- [x] **2. 最小实现。** 健康模块用 `make_url(get_database_url())` 获取持久 SQLite 路径；以 `Path(...).resolve().as_uri() + '?mode=ro'`、`uri=True, timeout=1.0` 打开并在 `contextlib.closing` 中关闭。执行的不是空 engine 访问，而是：

  ```python
  connection.execute("SELECT 1 FROM task LIMIT 1").fetchone()
  ```

  空表仍算可读；捕获 `sqlite3.Error`、`OSError` 和 URL 解析 `ValueError`，返回 false。当前产品是持久 SQLite；内存库／其他方言不能靠新建另一个数据库伪造成功，应明确返回未就绪并在测试中锁定语义。health 用 `response.status_code = 503` 标记失败，保留 runtime 摘要；不把 DB 读取探测扩写为写能力或磁盘容量承诺。
- [x] **3. 消费方一致。** Compose 的 API healthcheck 从 `/` 改为 `/api/health`；启动与 smoke 同时检查 HTTP 成功、`status == 'ok'`、`database == 'ok'`，503 不允许继续后续阶段。保留既有等待总时限和退出清理；不新增第二套含义不清的 liveness/readiness URL。
- [x] **4. 实际工作流。** 运行 `PYTHONPATH=backend .omo/evidence/phase1-improvement-2026-10-21/venv/bin/python -m pytest backend/tests/test_runtime_api.py -q`。另在临时数据路径启动真实 uvicorn，记录正常→DB 故障→恢复三段 HTTP／延迟及调用方退出码；容器在隔离挂载下复验。未在目标容器执行时，不勾选其平台验收。

### Task 3：#44 浏览器可执行路径

**Files:** `/Users/drm/project/nyaru-clipper/web/playwright.config.ts`；记录在双语 deployment 文档；不修改应用 UI 或用户 Chrome 配置。

**Interfaces:** 环境变量仍为 `PLAYWRIGHT_CHROME_EXECUTABLE`；只改变正确的 runner 配置层级，未设置时保留 bundled Chromium 默认行为。

- [x] **1. 保留修复前证据。** 使用临时 reporter 的 `onBegin(config)` 记录 `config.projects[].use.launchOptions`，只输出配置路径，不输出完整环境；先证明路径没有进入有效选项。
- [x] **2. 最小修改。** 替换现有 spread，保留其余配置：

  ```typescript
  ...(chromeExecutablePath === undefined
    ? {}
    : { launchOptions: { executablePath: chromeExecutablePath } }),
  ```

- [x] **3. 实际启动。** 在 `web/` 执行以下命令，保留 `DEBUG=pw:browser` 的启动可执行路径、退出结果和 trace；不能只看清单或 `browserType.executablePath()`，后者不证明覆盖路径。

  ```bash
  cd /Users/drm/project/nyaru-clipper/web
  PLAYWRIGHT_CHROME_EXECUTABLE='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' DEBUG=pw:browser corepack pnpm exec playwright test e2e/workstation-shell.spec.ts -g 'declares Chinese' --reporter=line
  env -u PLAYWRIGHT_CHROME_EXECUTABLE corepack pnpm exec playwright test e2e/workstation-shell.spec.ts -g 'declares Chinese' --reporter=line
  ```

  准备时仅确认系统 Chrome 文件存在；默认 Chromium 是否可启动尚未验证。若缺少浏览器，先按锁定 Playwright 版本准备依赖再运行；不禁用沙箱、不使用个人浏览器 profile。再设一个不存在的路径，要求明确非零退出，禁止静默回退。

### Task 4：#12 工作站与 Companion 的发布 smoke

**Files:** 修改 `/Users/drm/project/nyaru-clipper/scripts/_release_smoke_common.sh`，并检查 `/Users/drm/project/nyaru-clipper/scripts/release_smoke_non_docker.sh`、`/Users/drm/project/nyaru-clipper/scripts/release_smoke_wsl_rocm.sh`、`/Users/drm/project/nyaru-clipper/scripts/release_smoke_docker.sh`。新增 `/Users/drm/project/nyaru-clipper/backend/tests/test_release_smoke_scripts.py`、`/Users/drm/project/nyaru-clipper/scripts/release_smoke_companion.sh`、`/Users/drm/project/nyaru-clipper/web/playwright.companion.config.ts`、`/Users/drm/project/nyaru-clipper/web/e2e/companion-release.spec.ts`；更新双语部署文档与脚本 AGENTS。新增路径均为计划产物，当前尚不存在。

**Interfaces:** 工作站共享 `run_downstream_smoke_suite()` 保留原函数名及退出码传播；新增 Companion 脚本只接受临时 root 与可选冻结后端路径，使用独立回环端口／同源静态页面。两种交付入口互不冒充对方。

- [x] **1. 失败与零测试守卫。** 用临时可执行 wrapper 跑真实 shell helper，分别让 backend/unit/build/browser 返回非零，断言原退出码向上传播且后续步骤不执行。用 runner 的空选择确认非零；不添加 `--pass-with-no-tests`。所有异常退出仍清理自己创建的进程和 fixture，不终止已有服务。
- [x] **2. 修正实际工作站选择。** 选用已确认存在的五个文件，保留全量单元测试与 build；17 是本次清单快照，不写死为测试数量断言。新增 Companion spec 后，主配置必须 `testIgnore: '**/companion-release.spec.ts'`，避免普通工作站配置误跑它。共享 smoke 不再 `uv run` 隐式同步环境，调用已经验证的后端解释器执行 pytest。

  ```bash
  pnpm --dir "${ROOT_DIR}/web" exec playwright test \
    e2e/workstation-shell.spec.ts e2e/workstation-task-create.spec.ts \
    e2e/workstation-queue.spec.ts e2e/workstation-task-overview.spec.ts \
    e2e/task-library-controls.spec.ts --reporter=line
  ```

- [x] **3. 加入 Companion 同源 smoke。** CLI 现有入口为 `python -m app.arctime.cli gui`，指定 `--output-dir`、`--port`，读取构建后的静态页面。新脚本建立临时 root，在 Python 中以回环 socket 分配空闲端口，监听失败明确退出；使用 Task 1 已验证解释器与 `PYTHONPATH=/Users/drm/project/nyaru-clipper/backend` 启动 CLI 并等待 `/companion-api/jobs`，不沿用默认数据路径。退出 trap 终止并 wait 自己的子进程。macOS 冻结模式按现有 `--data`、`--ready`、`--parent-pid` 启动指定候选，不打开已安装 App。配置复用主配置的 `use`（含 #44），另设 `baseURL` 与 `testMatch`，不继承 Vite webServer。浏览器用例如下：

  ```typescript
  import { expect, test } from "@playwright/test";

  test("Companion serves its jobs and settings from the actual backend", async ({ page, request }) => {
    const jobs = await request.get("/companion-api/jobs");
    expect(jobs.ok()).toBe(true);
    expect(await jobs.json()).toEqual([]);
    const settings = await request.get("/companion-api/studio-settings");
    expect(settings.ok()).toBe(true);
    await page.goto("/");
    await page.getByRole("button", { name: "设置", exact: true }).click();
    await expect(page.getByRole("heading", { name: "设置中心" })).toBeVisible();
    await page.getByRole("button", { name: "返回工作区" }).click();
    await expect(page.getByRole("button", { name: "设置", exact: true })).toBeVisible();
  });
  ```

  此用例不得 mock 同源 jobs／settings 请求；只验证空工作区、设置往返和实际页面/API。不创建任务、请求模型或使用真实认证；现有 Companion 后端与前端测试仍作为单独回归执行。
- [ ] **4. 匹配平台执行。** Linux host、WSL ROCm、Docker fallback 分别运行自己的现有 smoke 入口，Companion 运行新增入口；先保留 `--list`，再记录真实 browser runner 与整体退出码。浏览器工作站测试的 API 多为受控 mock，不能把它写成真实下载／ASR 验收。macOS 无 `setsid` 时只跑可支持的组件与 Companion，不把 Docker/Linux 结果代替 WSL GPU 验收。

## 合并验收与交付

- [x] 四个 ID 各有独立 red/green 与实际入口证据，所有状态从 planned 据实推进；不以一个 smoke 结果代替四项关闭。
- [x] #32 验证原解释器优先级测试已自包含且通过；不再接受第一阶段的该项环境失败作为本阶段结项理由。
- [x] 除第一阶段环境中的快速回归外，用独立 `.omo/evidence/phase2-release-validation-2026-10-21/venv` 安装实际固定基础 requirements，增加精确测试依赖 `pytest==8.4.2`、`pytest-asyncio==0.26.0` 以及 Companion 已声明的 `yt-dlp==2026.8.19`，执行 `uv pip check` 及验收测试；对比安装前后运行 pin，不能以开发环境的不同版本代替运行产物验证。
- [x] 复跑第一阶段 290 项对应文件范围，以及完整后端、前端类型／构建、受影响浏览器场景；实际数量按新报告统计。禁止删除／跳过旧失败用例。macOS 原有临时目录断言用本地 `/tmp` 运行环境满足，不顺带重构无关测试。
- [x] 保存 `.omo/evidence/phase2-release-validation-2026-10-21/` 下命令、版本、退出码、JUnit、trace、截图、耗时、产物哈希；敏感配置不进入证据。按 Linux/CUDA、WSL/ROCm、Docker、macOS 分列 observed／not run。
- [x] 双语总计划与第二阶段结果已更新：**13 项在记录范围内已验收／31 项待处理**，证据和最终 APPROVE 已保存；准备时的 9 已验收加 4 planned 为历史状态，不代表当前结果。
- [x] 复核第一阶段源文件、原 Companion 工作树和未提交内容仍被保护；交付可审阅差异，不自动提交／推送／安装。

历史准备验收：四个原编号均有入口、实施边界、可执行步骤和单独验收条件；新增计划链接有效；产品源码没有被准备阶段改动。后续实际实现／验证见执行更新。平台全栈推广项仍未勾选：本机已运行共用组件、Docker CPU 数据库检查及 Companion CLI／冻结入口，未运行 Linux CUDA／WSL ROCm／业务 Compose GPU 全栈。
