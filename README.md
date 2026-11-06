# JP Voice Workbench

本地优先的日语音频工作台，规划支持日语转录、日中翻译、专名纠错、译名统一与字幕复核。需求和阶段验收以 [AGENT.md](AGENT.md) 为准，开发约定见 [CONTRIBUTING.md](CONTRIBUTING.md)，实际验收见 [STATUS.md](STATUS.md)。

## 当前范围

本轮仅实现 Phase 0 和 Phase 1。模型资产检查只判断文件是否存在，不代表模型可推理。桌面、音频处理、ASR、词表和字幕功能尚未实现。中文法律文本脱敏与 mask 是可选迁移方向。

## 环境与依赖

已验证 Windows、Python 3.10.21、Node v24.16.0、pnpm 11.21.0。尚无前端依赖，Node/pnpm 兼容性留待前端阶段验证。后端当前只安装 FastAPI、Pydantic、Uvicorn 和检查工具；faster-whisper/CTranslate2 等在 Phase 3 引入，不提前安装模型推理依赖。

项目使用 `.venv`。有 Python 3.10 和 pip 时，在项目根目录执行（PowerShell）：

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r backend/requirements.txt
.\.venv\Scripts\Activate.ps1
```

也可使用 uv（本机实际采用此方式；uv 创建的环境默认不带 pip）：

```powershell
uv python install 3.10
uv venv --python 3.10 .venv
uv pip sync --python .venv/Scripts/python.exe backend/requirements.txt
uv pip check --python .venv/Scripts/python.exe
```

[requirements.in](backend/requirements.in) 声明直接依赖与用途，[requirements.txt](backend/requirements.txt) 锁定全部传递依赖及哈希。修改依赖后重新生成并验收：

```powershell
uv pip compile backend/requirements.in --python .venv/Scripts/python.exe --generate-hashes --output-file backend/requirements.txt
```

## 模型准备

将 [manifest.example.json](examples/manifest.example.json) 复制到本地 `models/manifest.json`，修改其中路径。相对路径统一以项目根目录解析，也支持外部绝对路径；本机路径只保存在被忽略的本地清单。不要猜测不明模型的身份，不自动下载模型，不改动旧项目资产。

每个 CT2 模型检查 `model.bin`、`config.json`、`tokenizer.json`、`preprocessor_config.json`、`vocabulary.json`；VAD 检查 ONNX 和 metadata 文件。

```powershell
New-Item -ItemType Directory -Force models | Out-Null
Copy-Item examples/manifest.example.json models/manifest.json
python scripts/verify_models.py
```

已有本地清单时不要覆盖，可先人工编辑。也可传 `--manifest <路径>`。脚本退出码 0 表示文件齐全；1 表示缺失/清单错误，并逐项打印路径。当前默认模型路径缺失属于真实环境结果，不阻止健康服务或无模型测试启动。

## 启动 Sidecar（Phase 1）

激活项目 `.venv` 后，在 `backend` 目录执行：

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8765
```

默认每次启动生成随机 token，通过本地 stdout 的 `SIDECAR_TOKEN {"token":"..."}` 行交付。请求时使用 `X-Sidecar-Token` header。不要把该行重定向到共享日志。服务只提供 `/api/health` 与 `/api/models`，不会加载模型或联网；内置入口 `python -m app.main` 也固定监听 `127.0.0.1:8765`。手工启动 Uvicorn 时同样保留上述环回 host。

为运行 AGENT 中固定 `dev` 的验收示例，必须显式设置开发 token，不存在默认开发后门：

```powershell
$env:SIDECAR_TOKEN = 'dev'
uvicorn app.main:app --host 127.0.0.1 --port 8765
# 在另一终端中执行：
curl.exe -H "X-Sidecar-Token: dev" http://127.0.0.1:8765/api/health
```

验收后清除开发 token：`Remove-Item Env:SIDECAR_TOKEN`。健康接口返回 `{status, version, models_ok}`；缺模型时保持 `status=ok`、`models_ok=false`。模型接口返回 `models`、`vad`、`errors` 和逐文件状态；这只说明文件存在情况。缺失/错误 token 返回 401，非法 Origin 返回 403。CORS 只允许 `http://127.0.0.1` 及其端口，允许的浏览器预检不需要 token，实际 GET 必须鉴权。

本地配置使用环境变量（相对路径以项目根解析）：

| 变量 | 默认值/说明 |
| --- | --- |
| `JP_WORKBENCH_ROOT` | 根据源码位置确定项目根，不依赖工作目录 |
| `JP_WORKBENCH_MODELS_DIR` | `<项目根>/models`；改变默认清单所在目录 |
| `JP_WORKBENCH_MANIFEST` | `<模型目录>/manifest.json`；清单内相对模型路径仍以项目根解析 |
| `JP_WORKBENCH_TEMP_DIR` | `<项目根>/data/tmp`；本阶段只配置，不进行音频读写 |
| `JP_WORKBENCH_DEVICE` | `auto`；允许 `auto/cpu/cuda`，尚未加载设备 |
| `JP_WORKBENCH_COMPUTE_TYPE` | `int8`；允许 `int8/int8_float16/float16/bfloat16`，尚未验证推理 |
| `SIDECAR_TOKEN` | 未设置时随机生成；显式非空 ASCII 值供开发/未来主进程传入 |

## 开发检查

激活 `.venv` 后在项目根目录执行：

```powershell
python scripts/check_repository.py
python -m ruff check backend scripts
python -m ruff format --check backend scripts
python -m pytest -q
```

若本机旧的系统 pytest 临时目录权限异常，可指定项目内临时目录，不修改系统权限：

```powershell
New-Item -ItemType Directory -Force data/tmp | Out-Null
$env:TMPDIR = (Resolve-Path data/tmp).Path
python -m pytest -q
```

CI 在 Windows/Linux 的 Python 3.10 上执行仓库、静态、格式和无模型测试，不下载模型或使用私人音频。模型文件存在检查不替代加载模型、GPU 或业务验收。

## 本地数据

模型、用户词表、音视频、字幕结果、数据库、日志、密钥和本地配置均不提交 Git。测试占位模型仅用临时空文件验证文件检查逻辑，不作为推理或准确率验收。共享合成数据和配置只放 `tests/fixtures/` 或 `examples/`。
