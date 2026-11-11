# Whisper工作台

本地优先的日语音频工作台，支持日语转录、按需日中翻译、术语匹配和字幕复核。阶段验收、开发约定和实际验收记录见 [AGENT.md](AGENT.md)、[CONTRIBUTING.md](CONTRIBUTING.md) 和 [STATUS.md](STATUS.md)。

## 当前范围

Electron 工作台支持录音、选择或拖入媒体、本地 faster-whisper 转录、可选 DeepSeek 文本翻译（可在设置页调整系统提示词）、任务历史、术语表维护与匹配预览、字幕编辑，以及 SRT、VTT、LRC、TXT 导出。音频始终留在本机，只有启用翻译时才会将待翻译字幕文本发送给 DeepSeek。

## Windows 安装与首次启动

Windows x64 只交付 NSIS 安装版 `Whisper工作台-0.1.0-win-x64-setup.exe`。运行后安装到所选目录（支持含空格或中文的路径），包内包含 Python sidecar；本地数据使用当前 Windows 用户的 `%APPDATA%\jp-voice-workbench`。

安装时会在安装目录创建 `model/` 目录并写入放置说明。用户把本地 CTranslate2 模型放入 `<安装目录>/model/<模型子目录>/`（每个子目录含 `model.bin`、`config.json`、`tokenizer.json`、`preprocessor_config.json`、`vocabulary.json`），把 VAD 文件 `whisper_vad.onnx`、`whisper_vad_metadata.json` 放在 `model/` 根目录。工作台启动时自动扫描该目录，无需手写 `manifest.json`。

1. 启动后在「设置」页查看模型目录、发现的本地 Whisper CT2 模型与逐文件校验结果；放好模型后点「重新扫描」即可选择模型。
2. 空目录或缺文件时，设置页会显示准确的放置路径、示例子目录、缺少的文件名和模型获取说明；目录不可访问时给出权限提示。未就绪的 ASR 模型不能提交任务，VAD 缺失时单独显示能量阈值回退状态。
3. 只有需要日中翻译时，才在用户数据目录下的 `.env` 或环境变量配置 `DEEPSEEK_API_KEY`，并在任务中选择翻译模式。

Windows 交付为本地未签名构建，模型权重由用户提供。CPU 使用默认的 `int8`。NVIDIA GPU 需相容驱动和 CUDA 运行环境。

从 `v0.1.0` 升级的用户，按[从 0.1.0 迁移模型](docs/migration-model-dir.md)把原模型文件复制到新的 `model/` 目录。

## macOS 安装与首次启动

Apple Silicon（arm64）交付一个 DMG 和一个 ZIP。打开 `Whisper工作台-0.1.0-mac-arm64.dmg`，把「Whisper工作台」拖入「应用程序」；ZIP 解压后得到同样的 `.app`。本地数据保存在 `~/Library/Application Support/jp-voice-workbench`。

macOS 产物是本地 ad-hoc 签名的未公证应用。从网络下载后首次打开会被 Gatekeeper 拦截，提示「无法验证开发者」。在「应用程序」中右键点击应用选择「打开」，或到「系统设置 → 隐私与安全性」允许一次即可；不要用 `xattr` 或关闭 Gatekeeper 绕过。模型准备、翻译配置与 Windows 相同，模型权重由用户提供，macOS 版只使用 CPU（默认清单的 `int8`）。

## 打包

在目标平台准备 Node.js 24、pnpm 11.21.0 和 Python 3.10 的项目 `.venv`。Windows 在仓库根目录执行。

```powershell
uv pip install --require-hashes --python .venv/Scripts/python.exe -r backend/requirements.txt -r backend/requirements-build.txt
pnpm --dir apps/desktop install --frozen-lockfile
pnpm --dir apps/desktop build
pnpm --dir apps/desktop dist
```

PyInstaller 将 sidecar 输出到 `backend/dist/sidecar/`，Electron Builder 将其复制到应用资源目录。Windows 只生成 NSIS 安装版 `Whisper工作台-0.1.0-win-x64-setup.exe`（不再提供 portable），产物位于 `apps/desktop/release/`；安装时按 `apps/desktop/scripts/installer.nsh` 在安装目录创建 `model/` 并写入放置说明。初次构建会获取 Electron 与安装器工具。

macOS（Apple Silicon / arm64）在仓库根目录执行同一套命令，Python 路径改为 `.venv/bin/python`：

```bash
uv pip install --require-hashes --python .venv/bin/python -r backend/requirements.txt -r backend/requirements-build.txt
pnpm --dir apps/desktop install --frozen-lockfile
pnpm --dir apps/desktop dist
```

产物位于 `apps/desktop/release/`，包括 `Whisper工作台-0.1.0-mac-arm64.dmg`、同名 ZIP 及 blockmap。`scripts/after-pack.cjs` 在打包后做 ad-hoc 签名，使下载到的副本通过完整性校验；配置 Developer ID 证书后 Electron Builder 会用真实证书覆盖该签名。当前未做公证。

从 GitHub 下载 Electron 或 Electron Builder 二进制过慢时，可对构建命令临时加镜像环境变量（本机实际采用）：

```bash
export ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
export ELECTRON_BUILDER_BINARIES_MIRROR=https://npmmirror.com/mirrors/electron-builder-binaries/
pnpm --dir apps/desktop dist
```

仓库提供手动触发的 `Whisper工作台 macOS 构建` 工作流，在 `macos-latest` 生成 DMG 和 ZIP；本机已在 macOS 27.0（arm64）完成 DMG/ZIP 构建、ad-hoc 签名、DMG 挂载和打包版运行验收。

参见[一分钟演示](docs/demo.md)与[架构说明](docs/architecture.md)。

## 环境与依赖

使用 Node.js 24、pnpm 11.21.0、Electron 45.2.3 和 Python 3.10。后端安装 FastAPI、Pydantic、Uvicorn、PyAV、NumPy、ONNX Runtime、faster-whisper 1.2.1、CTranslate2 4.8.5、pyahocorasick 2.3.1 和检查工具。真实 ASR 加载与推理已在 RTX 4070（CUDA，bfloat16）上验证。翻译使用 DeepSeek API。

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

开发版从项目目录读取模型，需要手写清单；**Windows 安装版无需清单**，直接把模型放入 `<安装目录>/model/<模型子目录>/`，由应用自动扫描（见上文）。

将 [manifest.example.json](examples/manifest.example.json) 复制到本地 `models/manifest.json`，修改其中路径。相对路径统一以项目根目录解析，也支持外部绝对路径；本机路径只保存在被忽略的本地清单。不要猜测不明模型的身份，不自动下载模型，不改动旧项目资产。

每个 CT2 模型检查 `model.bin`、`config.json`、`tokenizer.json`、`preprocessor_config.json`、`vocabulary.json`；VAD 检查 ONNX 和 metadata 文件。

```powershell
New-Item -ItemType Directory -Force models | Out-Null
Copy-Item examples/manifest.example.json models/manifest.json
python scripts/verify_models.py
```

已有本地清单时不要覆盖，可先人工编辑。也可传 `--manifest <路径>`。脚本退出码 0 表示文件齐全；1 表示缺失/清单错误，并逐项打印路径。当前默认模型路径缺失属于真实环境结果，不阻止健康服务或无模型测试启动。

## 启动桌面工作台（Phase 5）

准备项目 `.venv` 与模型清单，在仓库根目录执行。

```powershell
pnpm --dir apps/desktop install --frozen-lockfile
pnpm --dir apps/desktop dev
```

首次运行会取得锁定版本的 Electron。开发脚本优先让 Vite 监听 `127.0.0.1:5173`，端口不可用时切换到系统分配的环回端口。Electron 主进程随后启动本地 Python 服务，并通过私有管道取得其环回端口。令牌只在主进程和 Python 服务中使用。也可执行 `pnpm --dir apps/desktop build` 后运行 `pnpm --dir apps/desktop start`，加载构建后的界面。

- 在「新建」录制约 10 秒日语或拖入媒体，再点「开始处理」。任务按提交顺序运行。打开「工作台」后，任务列表通过 WebSocket 显示阶段和进度。排队时可立即取消，运行中会在下一个安全检查点停止。
- 批量处理：在「新建」一次性多选或拖入多个音频/视频（可混合格式），列表显示名称、采样、体积和逐项校验结果。先选择模型、字幕格式和输出目录，点「开始批量处理」后按列表顺序逐条入队。每条成功转录后自动把已保存字幕写入输出目录，文件名取媒体主文件名，遇到同名自动追加序号并保护已有文件；转录与字幕写入分别显示状态，写入失败可就地「重新导出」，其余任务继续。
- 转录完成后在「工作台」的「字幕复核」里并排查看模型输出和当前字幕。可以手改并保存、逐条接受或拒绝术语建议，也可以撤销最近一次仍可撤销的替换。纯静音或合成正弦波可能生成空 SRT。
- 导出时先选择字幕格式和覆盖策略，再通过保存对话框确认目录与文件名。默认保护已有同名文件。
- 在「术语表」导入 `examples/glossary.demo.json`，用 `田中さんと渋谷で会いました` 验证高亮和替换预览。也可以直接维护词条，或导出 CSV/JSON。
- 在「设置」选择含 `manifest.json` 的目录、推理设备、计算类型和默认导出目录。模型目录、任务与已保存字幕在重启后恢复。推理覆盖项和默认导出目录在当前会话生效。
- 临时录音在任务完成、失败、取消或正常退出时清理。异常退出留下的临时录音会在下次启动时清理。勾选「保留录音副本」会在 Electron 用户数据目录的 `recordings/` 保留 WebM，任务详情会显示保存路径。

左栏、顶部工具条和消息浮层使用本地打包的 Glasswork v1.1.0 MIT 样式和 Chromium 边缘折射。正文编辑区是实底。背景是一张低调的窗边照片，浅色和深色均在 `prefers-reduced-transparency: reduce` 时退回实色。来源见 [Glasswork v1.1.0](https://github.com/kubai087/glasswork/tree/v1.1.0)。

Windows 桌面烟雾脚本需要 ffmpeg、已配置的 ASR 模型和生产构建。默认使用 `data/demo/sample.wav` 的合成信号。将 `JP_WORKBENCH_SMOKE_AUDIO` 设为本地日语音频，可额外验证非空转录、模拟翻译、术语复核和字幕编辑。脚本使用模拟麦克风和环回翻译 mock，浅色与深色截图保存至被忽略的 `data/desktop-smoke/`。

```powershell
python scripts/make_demo_assets.py --out data/demo
pnpm --dir apps/desktop build
pnpm --dir apps/desktop smoke
```

批量导入与自动导出的界面冒烟可单独运行，它会用合成 WAV 验证同名文件加序号、保护已有字幕与 SRT/VTT 切换：

```powershell
node apps/desktop/scripts/smoke-batch.mjs
```

## 单独启动 Sidecar（Phase 1）

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
| `SIDECAR_TOKEN` | 未设置时随机生成。Electron 启动子进程时直接传入临时令牌 |

## 音频处理（Phase 2）

`app.audio.decode.decode_audio(path)` 接受 `.wav/.mp3/.m4a/.flac/.mp4/.mkv/.webm`，通过 PyAV 返回一维 `float32` 采样，固定为 16000 Hz 单声道。`DecodedAudio.duration_ms` 由实际采样数计算。解码失败、无音轨和空采样会给出中文错误。

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

## 任务队列与历史（Phase 6）

```text
POST  /api/jobs                        创建任务，返回 202 与 JobStatus
GET   /api/jobs                        按创建时间倒序读取任务
GET   /api/jobs/{job_id}               查询状态、进度、阶段与 segments
POST  /api/jobs/{job_id}/cancel        请求取消
PATCH /api/jobs/{job_id}/segments/{id} 保存字幕编辑副本
WS    /ws/jobs/{job_id}                发送当前快照和后续变更
```

桌面端在 Electron 用户数据目录的 `jobs.sqlite3` 保存任务状态和字幕，独立启动 sidecar 时默认使用项目的 `data/jobs.sqlite3`，可通过 `JP_WORKBENCH_JOBS_DB` 指定路径。同一数据库由单个 sidecar 使用。重启时，退出前仍在运行或排队的任务显示为已中断，历史任务不会自动重跑。数据库含字幕原文、译文和保存后的编辑结果，应作为本地私人数据保管。

WebSocket 使用同一会话令牌，可通过 `X-Sidecar-Token` 请求头或 Electron 使用的 `jp-workbench, <token>` 子协议握手鉴权。消息带 `revision`，连接中断时客户端查询最新快照后重连。取消检查覆盖解码、VAD 窗口、推理片段和翻译批次，已发出的单次网络请求或正在执行的原生推理须等待返回。

`raw_text/raw_translation` 保存首次模型输出，`text/translation` 是可编辑副本，时间均为毫秒整数。任务状态包括 `queued`、`running`、`succeeded`、`failed` 和 `cancelled`。

## 本地模型冒烟

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
  "translation": {"provider": "deepseek", "model": "deepseek-flash", "system_prompt": null}
}
```

`system_prompt` 省略或为 `null` 时使用内置预设；桌面端会把它保存为本地自定义提示词后注入，长度上限 4000 字符。

`app.translation.deepseek.DeepSeekTranslator` 会按 20 段 / 6000 字符分批，用 JSON 模式要求返回与输入 id 一一对应的译文；401/402/429、超时和格式错误都有中文错误。任务 `segments[i].raw_translation` 与 `translation` 保存译文，`raw_text/text` 保留日语原文；不会覆盖原文。`mode=transcribe` 不联网、不需要 Key。

### 提示词与数据边界

发给 DeepSeek 的 system 提示词分两段：前端固定规则 + 可编辑预设。固定规则由后端始终追加，声明 `<subtitles>` 标签内的内容一律只当作待翻译文本，字幕里出现指令、问题或角色扮演也不会被执行；同时固定「逐段 JSON、id 一一对应」的输出契约。字幕原文在 user 消息里用 `<subtitles>` / `<subtitle id="0">` 边界包裹，原文中的 `&`、`<`、`>` 会转义成 HTML 实体，因此任意字幕文本都无法关闭标签或伪造新的边界。

在「设置 → 翻译提示词」可以查看并编辑可编辑那一段（默认值就是内置预设）。保存后写入用户数据目录的 `translation-prompt.json`，只影响后续 `mode=translate` 的任务；点「恢复默认」清空自定义内容。固定规则以只读形式一并展示，界面无法关闭。`GET /api/translation/prompt` 返回默认预设、固定规则和长度上限。

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

词表预览显示匹配位置和预期替换。任务用选中的词表生成待复核的 `hits`，转录完成时的字幕与首次模型输出一致。

## 字幕复核与导出（Phase 7）

日语原文纠错和中文译名统一分别作用于对应字段。接受建议会修改当前字幕，拒绝会留下标记并保留原词。只高亮的命中会显示在当前字幕上。手工编辑后重新匹配受影响的字段，并调整仍有效的复核位置。撤销作用于该片段中最近一次仍有效的已接受替换。

任务保存当时使用的词表快照，以便重启后继续复核。升级 Phase 6 的历史库时，应用保留已保存的字幕和原始结果，并以当时可读取的词表重新匹配已保存字幕。新增编辑或复核操作会校验片段的 `revision`，以防止旧位置或旧草稿覆盖最新版本。

```text
PATCH /api/jobs/{job_id}/segments/{id}        保存 text、translation 和当前 revision
POST  /api/jobs/{job_id}/segments/{id}/review 提交 action、revision 和命中定位
POST  /api/jobs/{job_id}/export               提交 format，返回已保存字幕的 UTF-8 内容
```

接受或拒绝时使用 `accept` 或 `reject`，并在 `hit` 中传入 `entry_id`、`field`、`start`、`end`。撤销使用 `undo`，只需传片段版本。时间轴使用毫秒。WebVTT 会转义文本中的标记字符，LRC 使用开始时间和百分秒。双语片段按原文、译文顺序写出。

桌面端通过系统保存对话框取得路径，默认用排他创建保护同名文件。允许覆盖时先写入同目录的临时文件，再替换目标。导出读取数据库中已经保存的编辑结果。

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

桌面端与 CI 使用相同的静态检查、测试和构建入口。

```powershell
pnpm --dir apps/desktop lint
pnpm --dir apps/desktop typecheck
pnpm --dir apps/desktop test
pnpm --dir apps/desktop build
```

CI 在 Windows 和 Linux 运行 Python 3.10 与 Node 24 检查，测试使用合成数据或 mock。

## 本地数据

模型、用户词表、音视频、字幕结果、数据库、日志、密钥和本地配置均不提交 Git。`.env` 与 `models/manifest.json` 都是本地配置，仓库只保留无密钥的 `.env.example` 和示例 manifest。测试占位模型仅用临时空文件验证文件检查逻辑，不作为推理或准确率验收。共享合成数据和配置只放 `tests/fixtures/` 或 `examples/`。

隐私边界：音频解码、VAD 与 ASR 全部本地；启用 DeepSeek 翻译时，仅字幕文本会发送到 `https://api.deepseek.com`，音频不上传。默认的 `mode=transcribe` 不联网。
