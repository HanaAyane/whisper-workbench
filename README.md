# JP Voice Workbench

本地优先的日语音频工作台，规划支持日语转录、日中翻译、专名纠错、译名统一与字幕复核。需求和阶段验收以 [AGENT.md](AGENT.md) 为准，开发约定见 [CONTRIBUTING.md](CONTRIBUTING.md)，实际验收见 [STATUS.md](STATUS.md)。

## 当前范围

当前已完成 Phase 0、Phase 1、Phase 2 和 Phase 3（3.1–3.5）的代码实现：具备本地 Sidecar 健康/模型检查、音视频解码、VAD/能量回退、30 秒切块、任务临时目录清理，以及本地 faster-whisper ASR 与任务状态机。真实日语样本的转写验收仍待完成。模型资产检查只判断文件是否存在，不代表 ASR 模型可推理。桌面 UI、词表和字幕编辑尚未实现；waveform peaks、批量任务与流式转写是后续 V1 项。中文法律文本脱敏与 mask 是可选迁移方向。

## 环境与依赖

已验证 Windows、Python 3.10.21、Node v24.16.0、pnpm 11.21.0。尚无前端依赖，Node/pnpm 兼容性留待前端阶段验证。后端安装 FastAPI、Pydantic、Uvicorn、PyAV、NumPy、ONNX Runtime、faster-whisper 1.2.1、CTranslate2 4.8.5 和检查工具。真实 ASR 加载与推理已在 RTX 4070（CUDA，bfloat16）上验证；翻译模型尚未提供。

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

默认每次启动生成随机 token，通过本地 stdout 的 `SIDECAR_TOKEN {"token":"..."}` 行交付。请求时使用 `X-Sidecar-Token` header。不要把该行重定向到共享日志。服务提供 `/api/health`、`/api/models`、`POST /api/jobs` 与 `GET /api/jobs/{id}`；健康/模型接口不会加载模型或联网，任务接口只在执行时加载本地权重。内置入口 `python -m app.main` 固定监听 `127.0.0.1:8765`。手工启动 Uvicorn 时同样保留上述环回 host。

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
| `JP_WORKBENCH_TEMP_DIR` | `<项目根>/data/tmp`；Phase 2 任务临时目录的根目录 |
| `JP_WORKBENCH_DEVICE` | `auto`；`auto` 优先 CUDA，无 GPU 时用 CPU |
| `JP_WORKBENCH_COMPUTE_TYPE` | `int8`；模型清单中的 `compute_type` 优先，README 记录的 ASR 验证值为 `bfloat16` |
| `SIDECAR_TOKEN` | 未设置时随机生成；显式非空 ASCII 值供开发/未来主进程传入 |

## 音频处理（Phase 2）

`app.audio.decode.decode_audio(path)` 接受 `.wav/.mp3/.m4a/.flac/.mp4/.mkv`，通过 PyAV 返回一维 `float32` 采样，固定为 16000 Hz 单声道。`DecodedAudio.duration_ms` 由实际采样数计算；解码失败、无音轨和空采样会给出中文错误。

`app.audio.vad.detect_speech(samples)` 默认优先读取 `models/whisper_vad.onnx` 与 `models/whisper_vad_metadata.json`。该 ONNX 需要 30 秒 Whisper log-Mel 特征，本地特征配置默认从 `models/whisper-base/preprocessor_config.json` 读取，也可用 `feature_config_path` 显式指定。实现只读取本地文件，不会从 Hugging Face 下载配置。ONNX、metadata、特征配置缺失或运行失败时记录中文警告并降级到 RMS 能量阈值；也可传 `use_onnx=False` 强制使用回退。合成正弦波适合验证回退与边界，不代表真实人声上的 ONNX VAD 准确率。

VAD 与切块统一使用毫秒、左闭右开的 `SpeechSegment(start_ms, end_ms)`。`merge_speech_segments()` 默认合并不超过 500 ms 的静音间隔，并生成每块不超过 30000 ms 的连续时间范围；超长语音会硬切，不丢弃原语音区间。`speech_pad_ms` 默认 200，测量未填充的检测边界时应显式设为 0。

任务临时文件使用 `job_temp_directory(job_id)` 上下文管理器，写入 `data/tmp/<job-id>/`，正常返回或抛出异常都会清理；任务 ID 禁止路径分隔符和路径穿越。不要绕过该上下文把私人音频写入仓库。

生成完全合成的演示资源：

```powershell
python scripts/make_demo_assets.py --out data/demo
```

该命令生成 6 秒 `sample.wav` 与 `sample.txt`。音频只有正弦波和静音，文本如实描述信号，**不是日语语音或 ASR 参照转录**；生成资源均被 Git 忽略。

## ASR 接入（Phase 3）

`app.asr.model_manager.ModelManager` 读取本地 `models/manifest.json`，校验必需文件后按 `device`（`auto/cpu/cuda`）与模型 `compute_type` 加载 `faster_whisper.WhisperModel`，并设置 `local_files_only=True`，不会下载权重。模型按 `(id, device, compute_type)` 缓存，`unload()` 释放。设备自动选择优先 CUDA；不支持的计算类型会返回中文错误并列出可用值。

`app.asr.whisper_backend.recognize_chunks()` 对 Phase 2 产生的 ≤30 秒块逐块推理，把块内时间戳换算为全局毫秒并裁剪到块边界；`translate_spans()` 为翻译模型保留逐段音频翻译接口。ASR 模型已在 RTX 4070（cuda/bfloat16）完成加载与合成音频推理；真实日语样本转写验收待完成。翻译模型缺失时翻译模式会明确报错。

任务接口（内存态，重启后不保留；持久化/取消/WebSocket 留待 Phase 6）：

```text
POST /api/jobs           创建任务，返回 202 与 JobStatus
GET  /api/jobs/{job_id}  查询状态、进度、阶段与 segments
```

`JobRequest` / `JobStatus` / `Segment` 遵循 AGENT.md 6.2/6.6/6.3：时间均为毫秒整数，`raw_text/raw_translation` 保存首次模型输出，`text/translation` 是可编辑副本。任务为单 worker 顺序执行，状态 `queued → running → succeeded/failed`；`export_formats` 暂被接受但不生成文件，正式导出在 Phase 7。

冒烟命令（会真实加载本地模型；`--no-vad-onnx` 可强制能量 VAD）：

```powershell
python scripts/smoke_transcribe.py --audio data/demo/sample.wav --model whisper-ja-1.5B
```

模型与设备会打印到终端；输出默认写在音频同目录的 `.srt`。合成正弦波在真实模型上返回 0 段属正常结果，**不能**作为日语转写验收。

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
