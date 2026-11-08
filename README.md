# JP Voice Workbench

本地优先的日语音频工作台，规划支持日语转录、日中翻译、专名纠错、译名统一与字幕复核。需求和阶段验收以 [AGENT.md](AGENT.md) 为准，开发约定见 [CONTRIBUTING.md](CONTRIBUTING.md)，实际验收见 [STATUS.md](STATUS.md)。

## 当前范围

当前已完成 Phase 0、Phase 1、Phase 2、Phase 3（3.1–3.5）和 Phase 4（4.1–4.7 首版 exact 范围）：具备本地 Sidecar、音视频解码、VAD/能量回退、30 秒切块、本地 faster-whisper ASR、**DeepSeek 文本翻译**，以及**术语表精确匹配、替换与预览 API**。ASR 使用本地模型，音频始终不上传；启用翻译时仅字幕文本发送到 DeepSeek，词表处理完全本地。真实日语样本的 30 秒片段与完整长音频转写验收已通过。桌面 UI 和字幕编辑尚未实现；waveform peaks、批量任务与流式转写是后续 V1 项。中文法律文本脱敏与 mask 是可选迁移方向。

## 环境与依赖

已验证 Windows、Python 3.10.21、Node v24.16.0、pnpm 11.21.0。尚无前端依赖，Node/pnpm 兼容性留待前端阶段验证。后端安装 FastAPI、Pydantic、Uvicorn、PyAV、NumPy、ONNX Runtime、faster-whisper 1.2.1、CTranslate2 4.8.5、pyahocorasick 2.3.1 和检查工具。真实 ASR 加载与推理已在 RTX 4070（CUDA，bfloat16）上验证；翻译使用 DeepSeek API，不需要本地翻译权重。

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

`app.asr.whisper_backend.recognize_chunks()` 对 Phase 2 产生的 ≤30 秒块逐块推理，把块内时间戳换算为全局毫秒并裁剪到块边界。ASR 模型已在 RTX 4070（cuda/bfloat16）完成加载与真实日语样本验收（30 秒片段及完整 144.9 秒长音频）。

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

## DeepSeek 翻译（Phase 3）

翻译通过 DeepSeek Chat Completions API 完成，默认 `model=deepseek-flash`、`base_url=https://api.deepseek.com`。**只发送待翻译的字幕文本，不发送音频或文件**；这是项目中唯一允许的外网请求，且仅在任务 `mode=translate` 时发生。

### 配置 Key

不要把 Key 写进代码或提交 Git。复制模板并填写本地 `.env`（已被 `.gitignore` 忽略）：

```powershell
Copy-Item .env.example .env
# 编辑 .env，填写 DEEPSEEK_API_KEY=...
```

也支持系统环境变量 `DEEPSEEK_API_KEY`（优先级高于 `.env`），以及 `DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL` 覆盖。`GET /api/health` 不会检查 Key，也不会发起网络请求。

### 接口与行为

`JobRequest` 的翻译选项为：

```json
{
  "mode": "translate",
  "translation": {"provider": "deepseek", "model": "deepseek-flash"}
}
```

`app.translation.deepseek.DeepSeekTranslator` 会按 20 段 / 6000 字符分批，用 JSON 模式要求返回与输入 id 一一对应的译文；401/402/429、超时和格式错误都有中文错误。任务 `segments[i].raw_translation` 与 `translation` 保存译文，`raw_text/text` 保留日语原文；不会覆盖原文。`mode=transcribe` 不联网、不需要 Key。

### 双语字幕冒烟

```powershell
python scripts/smoke_translate.py --audio "你的日语样本.mp3" --model whisper-ja-1.5B --out data/review/样本_日中双语.srt
```

输出每条字幕包含「日语原文 + 中文译文」两行，UTF-8 SRT，便于人工核对。未配置 Key 时脚本以中文错误退出，不会加载模型或外发任何内容。真实 144.9 秒样本已验证：ASR 17 段 → DeepSeek 17 段译文，双语 SRT 17 块全部非空（验收记录见 STATUS）。

## 术语表与替换（Phase 4）

支持 `exact` 精确匹配、`source` 与 `variants`、最长匹配优先、同长度按 `priority` 高者优先，以及 `correct`（日语原文纠正）、`translate`（中文译名统一）、`keep`（只高亮）三种策略。规则按 `field` 隔离：`correct` 只能作用于 `text`，`translate` 只能作用于 `translation`。`regex`、`fuzzy`、`mask` 属于 V1/STRETCH，导入时会明确返回“不支持”，不会静默跳过。

CSV 列：

```text
source,variants,target,category,match_mode,regex,priority,field,policy,enabled
```

`variants` 用 `|` 分隔；重复 `source` 会合并，若 target/field/policy 冲突则拒绝。JSON 支持数组或 `{ "entries": [...] }`。

API：

```text
GET  /api/glossary                          词表列表
POST /api/glossary/import                   导入（JSON body: glossary_id, format, content）
GET  /api/glossary/{glossary_id}/export     导出 csv/json
POST /api/glossary/preview                  文本命中与替换预览
```

词表保存在本地 `data/glossary/<id>.json`（被 Git 忽略）。仓库提供合成示例 `examples/glossary.demo.json`；本机验收前复制：

```powershell
New-Item -ItemType Directory -Force data/glossary | Out-Null
Copy-Item examples/glossary.demo.json data/glossary/demo.json
python scripts/glossary_demo.py --text "田中さんと渋谷で会いました" --glossary data/glossary/demo.json
```

`app.glossary.replacer.apply_to_segment()` 返回 Segment 副本，只改 `text/translation`，`raw_text/raw_translation` 永远保持首次模型输出；命中记录写入 `hits`。任务处理中若 `glossary_id` 指向存在的词表，会自动应用并返回 `hits`。

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

模型、用户词表、音视频、字幕结果、数据库、日志、密钥和本地配置均不提交 Git。`.env` 与 `models/manifest.json` 都是本地配置，仓库只保留无密钥的 `.env.example` 和示例 manifest。测试占位模型仅用临时空文件验证文件检查逻辑，不作为推理或准确率验收。共享合成数据和配置只放 `tests/fixtures/` 或 `examples/`。

隐私边界：音频解码、VAD 与 ASR 全部本地；启用 DeepSeek 翻译时，仅字幕文本会发送到 `https://api.deepseek.com`，音频不上传。默认的 `mode=transcribe` 不联网。
