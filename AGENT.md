# Whisper 工作台维护基线

Whisper 工作台（JP Voice Workbench）已完成 0 到 1 的基础框架搭建。它面向日常日语音频处理，支持录音或导入媒体、本地转录、按需日中翻译、专名纠错和译名统一、字幕人工复核，以及 SRT、VTT、LRC、TXT 导出。

本文件记录后续开发应遵守的工程约定和现有契约。[README.md](README.md) 负责安装、模型准备和使用说明，[STATUS.md](STATUS.md) 记录已执行的验收和已知限制。[0 到 1 阶段的 AGENT.md](docs/archive/AGENT-0-to-1.md) 原样归档，供追溯当时的阶段清单和设计决策。

## 1. 协作与产品原则

- 修改前读本文件、[CONTRIBUTING.md](CONTRIBUTING.md) 和相关 [STATUS.md](STATUS.md) 记录，检查工作区及受影响的实现。以用户当前提出的需求确定范围和验收条件，保留已有用户改动。
- 默认离线转录，音频解码、VAD 和 ASR 均在本机执行。禁止默认上传录音或接入第三方遥测。用户明确选择 DeepSeek 翻译时，在界面告知外发范围，只发送待翻译字幕文本。模型由用户提供，缺失时先检查模型目录和 `scripts/verify_models.py`，下载须由用户主动发起。
- DeepSeek 密钥取自环境变量或本地 `.env`，环境变量优先。令牌、密钥、完整原文/译文和私人媒体内容都不得进入日志、Git 或公开 issue。模型、本地配置、数据库、用户词表及导出内容属于本地数据。
- 首次 ASR 和翻译输出保留为只读原始记录。术语匹配只生成建议，日语原文纠错与中文译名统一分开处理。字幕编辑、接受、拒绝及撤销由用户操作，导出读取已保存的编辑结果。
- 本项目独立维护。旧项目 `faster_whisper_transwithai` 和 `Faster-Whisper-TransWithAI-ChickenRice` 可作实现参考，禁止覆盖、删除或直接依赖其包和本机路径。
- UI、面向用户的错误与业务日志默认用中文，变量、API 和文件名用英文。示例使用合成数据或来源明确的公开数据，功能声明与指标以实际验证为准。

## 2. 技术栈与依赖

| 层         | 当前基线                                                                                                                                                        |
| ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 桌面       | Node.js 24（项目要求 `>=24`）、pnpm 11.21.0、Electron 45.2.3、React 18、TypeScript、Vite、Zustand、CSS                                                          |
| Sidecar    | Python 3.10、FastAPI、Uvicorn、Pydantic v2、SQLite（标准库 `sqlite3`）                                                                                          |
| 音频与转录 | PyAV、NumPy、ONNX Runtime、faster-whisper 1.2.1、CTranslate2 4.8.5。默认清单使用本地 `whisper-ja-1.5B` CT2 模型                                                 |
| 翻译与术语 | HTTPX 调用 DeepSeek Chat Completions，配置默认 `deepseek-flash` 和 `https://api.deepseek.com`；系统提示词由 `app/translation/prompt.py` 组装（固定边界规则 + 可编辑预设），Key / 模型 / 思考强度可在设置页覆盖。术语匹配使用 pyahocorasick，缺失时用纯 Python 字符串搜索回退 |
| 检查与分发 | Ruff、pytest、ESLint、TypeScript 严格检查、Node 测试、Playwright 桌面烟雾（Windows 烟雾脚本使用 FFmpeg）。PyInstaller 冻结 sidecar，electron-builder 打包桌面端 |

桌面依赖以 [package.json](apps/desktop/package.json) 和 `pnpm-lock.yaml` 为准。后端以 `backend/requirements.in` 声明直接依赖，`requirements.txt` 固定版本及哈希。打包依赖使用同目录的 `requirements-build.in` 和 `requirements-build.txt`。开发时使用项目内 `.venv` 和 pnpm 的 `--frozen-lockfile`，依赖变更同步更新声明和锁文件。Python 版本如需偏离，记录原因和实际兼容性结果。

## 3. 架构与数据流

```text
React Renderer ⇄ preload contextBridge（window.api）⇄ Electron Main
                                                          ⇅ 环回 HTTP / WebSocket
                                                     FastAPI Sidecar
                                                          ├─ 单 worker 任务队列
                                                          ├─ PyAV → VAD → 本地 Whisper
                                                          ├─ 按需调用 DeepSeek
                                                          ├─ 词表匹配、字幕复核、导出
                                                          └─ SQLite 任务与复核 / JSON 词表
```

- **Renderer → Main**。渲染器处理录音、拖放、任务进度和字幕 UI，通过 `window.api` 调用受限 IPC。窗口启用 `contextIsolation` 和 `sandbox`，关闭 `nodeIntegration`。主进程验证 IPC 来源，管理文件对话框、媒体路径、临时录音、sidecar 和导出落盘。
- **Main → Sidecar**。桌面模式下主进程生成随机会话令牌，子进程监听 `127.0.0.1` 的系统分配端口，通过私有管道交付就绪信息。HTTP 使用 `X-Sidecar-Token`，WebSocket 可用同一请求头或 `jp-workbench, <token>` 子协议鉴权。令牌只在主进程与 sidecar 间传递。手工启动见 [README.md](README.md)。
- **Sidecar 数据流**。PyAV 解码为 16 kHz 单声道 `float32` → ONNX VAD（不可用时按能量阈值回退）→ 按最长 30 秒切块 → 本地 ASR → 按需翻译 → 生成分字段术语建议 → 保存任务结果与词表快照 → 人工复核 → 导出已保存字幕。
- **持久化与恢复**。一个数据库由一个 sidecar 使用。重启时历史任务和已保存字幕可恢复，原先排队或运行的任务标记为中断（`cancelled`），不自动重跑。旧历史缺少复核快照时，保留已保存字幕和原始输出，并用可读取的词表重新生成建议。录音默认临时保存并清理，只有用户选择保留时才留在 `recordings/`。导入的媒体原文件由用户管理。
- **开发和打包**。开发版从项目目录读取默认模型与 `.env`，桌面任务数据库位于 Electron 用户数据目录。独立启动 sidecar 时默认使用 `data/jobs.sqlite3`。打包版以用户数据目录为运行根目录，并从资源目录加载冻结的 sidecar 和默认模型清单模板。详见 [架构说明](docs/architecture.md)。

## 4. 目录结构

```text
apps/desktop/
  src/main/          窗口、IPC、sidecar 管理、文件及导出落盘
  src/preload/       受限的 window.api（index.cts）
  src/renderer/      React 界面、组件和 Zustand 状态
  src/shared/api.ts  桌面 IPC 接口与共享类型
  scripts/           开发启动、烟雾检查和打包
  tests/             桌面逻辑测试
backend/
  app/main.py        FastAPI 入口、环回鉴权和应用生命周期
  app/config.py      本地配置与环境变量
  app/api/           health、models、jobs、glossary 路由
  app/audio/         解码、VAD、切块与临时文件
  app/asr/           模型管理和转录
  app/translation/   DeepSeek 文本翻译与系统提示词组装
  app/glossary/      词表校验、导入导出、存储、匹配和替换预览
  app/jobs/          请求与结果模型、任务队列、取消和复核
  app/storage/       SQLite 任务及词表快照
  app/export/        字幕格式化
  tests/             后端测试
  pyinstaller.spec  sidecar 冻结构建
scripts/             仓库检查、模型校验、合成样本和 CLI 烟雾
examples/            可提交的模型清单模板与合成词表
docs/                架构、演示、截图与 archive/ 历史归档
.github/workflows/   常规 CI 与 macOS 打包
models/、data/       被 Git 忽略的开发环境模型与本地数据
```

## 5. 数据契约

后端以 [jobs/schemas.py](backend/app/jobs/schemas.py)、[glossary/models.py](backend/app/glossary/models.py) 和实际路由为准，桌面桥接以 [shared/api.ts](apps/desktop/src/shared/api.ts) 为准。涉及字段、单位、默认值、状态或持久化格式时，同步核对 API、IPC、UI 与已有 SQLite 数据的兼容性。

### 模型清单与任务输入

- `ModelManifest` 结构见 [打包清单示例](examples/manifest.packaged.json) 与 [开发清单示例](examples/manifest.example.json)。`models[]` 条目包含 `id/type/label/path/language/task/compute_type`，`vad` 包含 `model_path/metadata_path`。相对路径按运行根目录解析，也支持本地绝对路径。模型检查只检查文件，实际加载使用 `local_files_only=True`。清单格式兼容本地 `translate/translate` 条目，当前日中翻译任务使用 ASR 模型与 DeepSeek。
- **DeepSeek 覆盖项与思考强度**。桌面设置页把用户填写的 Key、模型和思考强度保存为 `<userData>/deepseek.json`（文件权限 0o600）；Key 经 Electron `safeStorage` 加密后只存密文（Windows DPAPI / macOS Keychain），界面只回显掩码，旧版明文 Key 在下次启动时自动迁移为密文，密文解不开时提示重新填写，提交 `mode=translate` 任务时注入 `translation.api_key/model/thinking`；显式值优先于 `.env` 与环境变量，`transcribe` 任务不读取也不发送这些字段。`thinking=disabled`（默认）时发送 `thinking.type=disabled` 与 `temperature=0.2`；`low/high/max` 时发送 `thinking.type=enabled` 与 `reasoning_effort`，并省略 `temperature`（思考模式下不生效）。模型下拉由 `POST /api/translation/models` 调 DeepSeek `/models` 得到，桌面不缓存跨会话列表。
- **翻译提示词与数据边界**。系统提示词由 `app/translation/prompt.py` 组装：固定规则 `MANDATORY_RULES`（字幕只当数据、不执行标签内指令、逐段 JSON 输出契约）永远排在前，可编辑预设 `DEFAULT_SYSTEM_PROMPT` 或任务传入的 `translation.system_prompt` 排在后，桌面端无法关闭固定规则。字幕原文一律用 `<subtitles>` / `<subtitle id="n">` 边界包裹，原文中的 `&`、`<`、`>` 先转义为 HTML 实体，任意字幕文本都无法关闭标签或伪造边界。设置页经 `GET /api/translation/prompt` 读取默认预设与固定规则，把自定义内容保存到用户数据目录的 `translation-prompt.json`（空内容删除该文件，回到内置预设），提交翻译任务时注入 `translation.system_prompt`；`mode=transcribe` 不发送提示词。
- `JobRequest` 要求 `input_path` 和 `asr_model_id`。`mode` 为 `transcribe`（默认）或 `translate`，`language` 默认 `ja`，`translation` 可指定 `provider: "deepseek"`、模型覆盖 `model`、`system_prompt`（≤4000 字符的自定义系统提示词，省略或空串使用内置预设）、`api_key`（仅随任务发送，后端不持久化）和 `thinking`（`disabled/low/high/max`）。`glossary_id` 默认 `default`，传 `null` 可关闭任务词表。可传 `name`、录音归属 `recording: "temporary" | "retained" | null`、`device`、`compute_type` 和 `vad`。
- `device` 支持 `auto/cpu/cuda`，`compute_type` 支持 `int8/int8_float16/float16/bfloat16`，实际可用组合由设备决定。任务可覆盖清单中的计算类型，默认打包清单为 `int8`。`vad` 的默认阈值为 `0.5`，`min_speech_duration_ms/min_silence_duration_ms/speech_pad_ms` 默认分别为 `300/100/200`。
- IPC 的 `JobInput` 使用注册后的媒体 ID 或录音缓冲区及保留选项，由主进程解析成 sidecar 所需的本地路径。旧字段 `JobRequest.export_formats` 仍在请求模型中，现行任务导出使用独立接口。

### 任务、字幕与复核

| 契约                            | 约定                                                                                                                                                                                                                                                                                                                                                                           |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `JobStatus`                     | `id` 标识任务。状态由 `queued` 进入 `running` 后到达 `succeeded/failed/cancelled`，排队中也可取消。`progress` 范围为 0–1，`stage` 为 `decode/vad/asr/glossary/export` 或 `null`，翻译进度归入 `asr`。快照包含 `message/error`、`segments`、`cancel_requested` 和任务元数据。HTTP 查询和 WebSocket 返回快照，客户端按任务 `revision` 避免用旧消息覆盖新状态，断线时查询最新快照 |
| `Segment`                       | `id` 是任务内整数，`start/end` 为媒体时间轴上的整数毫秒。`raw_text/raw_translation` 保留首次输出，`text/translation` 是可编辑副本。纯转录时两种译文字段都为 `null`。`hits` 记录建议与复核状态，`revision` 是独立的片段版本                                                                                                                                                     |
| `SegmentEdit` / `SegmentReview` | 保存传 `text`、`translation` 和当前片段 `revision`。接受或拒绝传 `action`、`revision` 和 `hit: {entry_id, field, start, end}`，撤销传 `action: "undo"` 和 `revision`。版本冲突返回 `409`。受影响字段重新匹配，撤销作用于该片段最近一次仍有效的已接受替换                                                                                                                       |
| `ExportRequest`                 | 对成功任务提交 `{format}`（`srt/vtt/lrc/txt`）。Sidecar 返回已保存字幕的 UTF-8 文本，双语按原文、译文顺序写出。主进程在用户选择的位置落盘，默认保护同名文件，明确允许覆盖时通过同目录临时文件替换                                                                                                                                                                              |

### 词表和命中

- `GlossaryEntry` 包含 `id/source/variants/target/category/match_mode/regex/priority/field/policy/enabled`。启用规则按 `field` 匹配当前字段的 `source` 和 `variants`。当前只支持 `exact`，使用 Unicode 规范化、大小写折叠和假名归一化。同起点优先选最长命中，再比较 `priority`，重叠命中按起点顺序保留。
- `correct` 仅用于 `text`（日语原文），`translate` 仅用于 `translation`（中文译文），两者要求非空 `target`。`keep` 只标记。`regex/fuzzy` 匹配和 `mask` 策略当前会被校验拒绝。
- CSV 列见 [glossary/io.py](backend/app/glossary/io.py)，`variants` 用 `|` 分隔。JSON 支持数组或 `{ "entries": [...] }`。重复 `source` 合并别名，`target/field/policy` 冲突时拒绝。仓库示例见 [glossary.demo.json](examples/glossary.demo.json)。
- `TermHit` 包含 `entry_id/field/start/end/matched_text/replacement/policy/confidence`。`start/end` 指当前字段中的 Unicode 码点偏移，左闭右开。桌面高亮按码点切分。`ReviewHit` 在此基础上记录 `decision: pending/accepted/rejected`、`original_text` 和后端用于撤销排序的 `applied_revision`。

### API 入口

| 方法         | 路径                                              | 用途                                                             |
| ------------ | ------------------------------------------------- | ---------------------------------------------------------------- |
| GET          | `/api/health`、`/api/models`                      | 健康状态与本地清单校验                                           |
| GET / POST   | `/api/jobs`                                       | 任务列表 / 创建任务（`202`）                                     |
| GET          | `/api/jobs/{job_id}`                              | 查询任务快照                                                     |
| POST         | `/api/jobs/{job_id}/cancel`                       | 请求取消                                                         |
| WS           | `/ws/jobs/{job_id}`                               | 推送任务快照，终态后关闭                                         |
| PATCH        | `/api/jobs/{job_id}/segments/{segment_id}`        | 保存当前编辑文本                                                 |
| POST         | `/api/jobs/{job_id}/segments/{segment_id}/review` | 接受、拒绝或撤销术语替换                                         |
| POST         | `/api/jobs/{job_id}/export`                       | 渲染已保存字幕                                                   |
| GET          | `/api/glossary`                                   | 词表列表                                                         |
| PUT / DELETE | `/api/glossary/{glossary_id}`                     | 保存 / 删除本地词表                                              |
| POST         | `/api/glossary/import`                            | 导入 CSV/JSON（`glossary_id`、`format`、`content`）              |
| GET          | `/api/glossary/{glossary_id}/export`              | 读取 CSV/JSON 词表（`format` 查询参数）                          |
| POST         | `/api/glossary/preview`                           | 按 `glossary_id`、`field`、`text` 返回命中与预览，不改字幕或词表 |
| GET          | `/api/translation/prompt`                         | 返回翻译默认预设、固定边界规则与长度上限（只读，供设置页展示） |
| GET          | `/api/translation/config`                         | 返回 `.env` / 环境变量里的生效模型、思考强度与 Key 是否已配置（不返回 Key） |
| POST         | `/api/translation/models`                         | 按请求里的 `api_key`（或服务端配置）读取 DeepSeek 模型列表 |

## 6. Git 与开发工程基线

- `main` 为稳定分支，功能、修复与文档工作使用 `feat/<topic>`、`fix/<topic>`、`docs/<topic>` 等短期分支，验收后再合入。提交使用 `feat`、`fix`、`docs`、`test`、`chore` 等前缀，一个提交围绕一个目的。
- 开始前执行 `git status --short`。提交前检查 `git diff` 与 `git diff --cached`，按明确路径暂存。提交源码、测试、示例、构建配置和依赖锁文件。发现误跟踪的敏感内容时先停止提交和推送，检查历史范围。
- 共享历史优先用 `git revert` 回退。禁止擅自破坏工作区、改写历史、强制推送或修改全局 Git 配置。远程仓库操作、推送、标签与发布按用户明确指示执行。
- 文本遵守 `.editorconfig` 和 `.gitattributes`，默认 UTF-8、LF。Python 使用 4 空格缩进，TS/JSON/YAML 使用 2 空格。
- 每次提交运行仓库基础检查和受影响模块的检查。接口变更核对失败路径、兼容性及持久化影响。行为或交付有变化时同步对应文档与 `STATUS.md`，记录实际执行的命令、结果和验收缺口。

| 改动范围                 | 检查入口                                                                                                                  |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------- |
| 仓库通用                 | `python scripts/check_repository.py`、`git diff --check`                                                                  |
| Python                   | `python -m ruff check backend scripts`、`python -m ruff format --check backend scripts`、`python -m pytest -q`            |
| 桌面                     | 在 `apps/desktop/` 执行 `pnpm lint`、`pnpm typecheck`、`pnpm test`、`pnpm build`                                          |
| 模型、录音、窗口、安装包 | 按 [README.md](README.md) 和 [演示说明](docs/demo.md) 运行相应验收，分别记录 mock、真实模型、人工操作与目标平台产物的结果 |

常规 CI 在 Windows 和 Linux 运行无大模型检查，使用合成素材或 mock。模型、GPU、安装包和人工验收单独记录。

## 7. 开发清单

优先级用于安排开发顺序。三项均须在本轮发布前完成验收。

本轮实现与逐项验收结果见 [STATUS.md 的本轮验收记录](STATUS.md#本轮开发清单验收记录)；未执行的人工/设备相关项在 STATUS 单独列出。

- **P0 · 核心流程**。先复用现有字幕导出能力，打通单任务与批量共用的输出路径，再完成多文件导入、排队转录和自动落盘。7.2 依赖 7.1。
- **P1 · 安装与交付**。Windows 安装版和 `model/` 改造可与 P0 并行开发。发布前用最终 NSIS 安装包验收模型识别和缺失指引，并跑通 P0 的转录与字幕输出流程。

### 7.1 [P0 · 前置] 可选字幕输出格式

- [x] 保留单任务导出入口，默认 SRT，继续支持 SRT、WebVTT（`.vtt`）、LRC、TXT。单任务与批量入口共用格式列表、后端字幕 writer 和主进程的写入逻辑。
- [x] 单任务导出继续读取已保存的字幕，保留保存位置选择和覆盖策略。格式、文件扩展名和实际内容须一致，文件使用 UTF-8。
- [ ] 验收时对同一条已编辑字幕分别导出四种格式，检查已保存文本、扩展名及各格式的时间戳或纯文本内容。至少在字幕播放器中加载一份 SRT 和一份 VTT。

### 7.2 [P0 · 核心] 批量导入、转录与自动导出

- [x] 支持通过文件对话框多选或一次拖放多个媒体文件，允许同批混合已支持的音频和视频格式（这里的实现可以参考faster_whisper）。显示待处理文件列表和逐项校验结果。更新媒体注册，使同批文件 ID 在提交前均有效，主进程负责真实路径与文件校验。
- [x] 开始前为整批选择一次模型、字幕格式和输出目录。一个媒体文件对应一条现有转录任务，按待处理列表顺序进入现有单 worker 队列，沿用任务历史、进度和单项取消。单文件导入和麦克风录音继续可用。
- [x] 每条转录任务成功后，直接把已保存的转录字幕写入所选目录，使用媒体文件的主文件名和所选字幕扩展名。待复核的术语建议继续留在编辑器，用户复核后可重新导出。每份文件直接落盘，整批只选择一次输出目录。
- [x] 遇到同名目标时自动追加序号，使用排他写入保护已有文件。单项提交、转录或写入出错时显示具体文件和原因，其余任务继续。区分转录成功和字幕写入成功，写入失败时可从已完成任务重新导出，复用已有转录结果。
- [ ] 验收时混合导入音频和视频，包含两份主文件名相同的有效媒体和一份损坏文件。分别选择 SRT 和 VTT 跑批次，检查每条成功任务的输出文件、命名及状态，并验证已存在的同名字幕受到保护。另验收单项取消、输出目录不可写以及从历史重新导出。

### 7.3 [P1 · 发布前必验] Windows 安装版与 `model/` 目录

- [x] Windows 后续构建和分发只保留 NSIS 安装版，移除 `portable` 打包目标，同步更新产物验收脚本和安装文档。
- [x] 安装时在实际安装目录创建 `model/`。用户将模型文件放到 `<安装目录>/model/<模型子目录>/`。模型资产由用户准备，安装包交付程序和模型放置指引。应用按安装位置定位 `model/`，支持自定义安装路径，任务历史等本地用户数据沿用现有存储位置。
- [x] 启动时自动扫描 `model/`。设置页显示模型目录、发现的本地 Whisper CT2 模型和文件校验结果，并提供「打开模型目录」与「重新扫描」。界面和任务加载使用同一份发现结果，用户放好文件后无需手写 `manifest.json` 即可选择模型。文件齐全与实际加载成功分别验证。
- [x] 空目录或文件缺失时，显示准确的放置路径、模型目录示例、缺少的文件名及模型获取说明。目录不可访问时给出权限提示。未就绪的 ASR 模型不可提交任务，VAD 缺失时单独显示现有回退状态。
- [ ] 为 `v0.1.0` 用户提供迁移指引，能从旧用户数据目录或旧配置中找到模型来源，再由用户复制到 `model/`。升级测试确认已放入新目录的模型和既有任务历史得到保留。
- [ ] 验收时在带空格或中文的自定义路径安装，从空 `model/` 检查指引，再放入不完整模型检查缺件提示，最后放入完整模型并重新扫描。使用识别到的模型跑一次真实转录与字幕导出，核对 Windows 分发产物只包含安装版。
