# 项目状态

更新日期：2026-11-08（Asia/Shanghai）。

## 当前范围

本轮实现 Phase 5 的 Electron 工作台。桌面端支持录音和文件导入、任务进度和取消、原始与编辑字幕对照、词表 CRUD 与预览、推理设置及四种字幕格式导出。导航、录音面板、任务栏和导出条使用 Glasswork v1.1.0。

## 阶段进展

| Phase | 状态 | 测试/验收 | 备注 |
| --- | --- | --- | --- |
| 0 项目初始化 | 完成 | 基础检查、Ruff、8 个文件校验测试、依赖兼容检查通过；模型检查按实际缺失返回 1 | 独立仓库、文档、忽略规则、Python 3.10 `.venv`、锁定依赖、模型检查脚本均已准备；缺模型明确报告路径，不下载 |
| 1 Python Sidecar | 完成 | backend 目录 pytest：32 passed；实际 Uvicorn + curl、鉴权、CORS、监听地址验收通过 | 随机 token、受限 CORS、配置、health/models、错误路径及测试已实现；只监听 127.0.0.1 |
| 2 音频处理 | 完成 | 音频/全量 pytest 通过；Ruff、仓库基础检查通过；6 种格式实际解码与本地 ONNX 只读烟雾通过 | 16 kHz 单声道 float32 解码、ONNX 优先/能量回退、≤30 秒切块、任务临时目录清理；`[V1]` waveform peaks 未做 |
| 3 ASR/翻译 | 完成（3.1–3.5） | 全量 pytest 111 passed；真实日语样本 30 秒冒烟与真实 API 任务通过；完整 144.9 秒样本真实 DeepSeek 翻译生成 17 段双语 SRT；Ruff/仓库检查通过 | model_manager、faster-whisper 后端、任务状态机、POST/GET jobs、DeepSeek 翻译与 smoke 脚本已实现；翻译仅文本外发，音频本地 |
| 4 术语引擎 | 完成（4.1–4.7 首版 exact） | pytest 111 passed；`scripts/glossary_demo.py` 实际输出命中与替换结果；API 导入/预览/导出通过 | exact 匹配、别名、最长匹配、priority、correct/translate/keep、字段隔离、CSV/JSON、预览与任务应用；regex/fuzzy/mask 属 V1/STRETCH 未实现 |
| 5 Electron/React | 完成（5.1–5.6） | Windows Electron 开发启动、生产界面烟雾、录音与拖放转写、词表导入预览、字幕编辑与 SRT 导出。前端检查通过，pytest 113 passed | 使用模拟麦克风输入本地日语样本。任务与编辑为会话态 |
| 6 队列/持久化 | 未开始 | 不适用 | 按实际需求推进 |
| 7 编辑/导出/隐私 | 未开始 | 不适用 | 尚无实现 |
| 8 测试/评测 | 未开始 | 不适用 | 尚无业务或真实模型评测 |
| 9 打包交付 | 未开始 | 不适用 | 尚无安装包或跨平台验收 |

## 环境与兼容性

- Git 2.52.0.windows.1；原始基线提交 `8e1f9ea`，稳定分支 `main`，Phase 1 功能分支 `feat/sidecar-foundation`（提交 `a7720c3`），Phase 2 功能分支 `feat/audio-processing`。沿用现有身份，不改全局 Git 配置。
- 桌面端使用 Node v24.16.0、pnpm 11.21.0、Electron 45.2.3、React 18.3.1、Vite 7.3.7 和 TypeScript 5.9.3。前端依赖已写入 pnpm 锁文件。
- 系统默认 Python 3.12.7（Anaconda）未用于项目依赖。通过 uv 安装 Python 3.10.21 并创建项目 `.venv`，没有修改系统默认版本，无 Python 版本偏离。
- Phase 1 所需的 FastAPI 0.115.12、Pydantic 2.11.5、Uvicorn 0.34.2、HTTPX 0.28.1、pytest 8.3.5、Ruff 0.11.11 已预先安装。
- Phase 2 新增 PyAV 15.1.0、NumPy 2.2.6、ONNX Runtime 1.23.2（含传递依赖）；全部 33 个依赖及哈希锁定在 `backend/requirements.txt`，`uv pip check` 通过。系统 `ffmpeg 8.1` 可用于生成测试样本，解码本身走 PyAV。
- Phase 3 新增 faster-whisper 1.2.1、CTranslate2 4.8.5 及其传递依赖；全部 45 个依赖及哈希锁定在 `backend/requirements.txt`，`uv pip check` 通过。`ctranslate2.get_cuda_device_count()` 返回 1，支持 `bfloat16/float16/float32/int8*`。
- Phase 4 新增 pyahocorasick 2.3.1（多模式匹配，失败时可回退纯 Python find）；全部 46 个依赖及哈希锁定，`uv pip check` 通过。
- 打包依赖将在 Phase 9 安装；本轮不宣称 PyInstaller/安装包或 macOS 兼容性已验证。
- DeepSeek 翻译复用已有 `httpx 0.28.1`，未新增第三方 SDK；`.env` 由项目内简单解析，未新增 python-dotenv。

## Phase 0 验收记录

- `.venv/Scripts/python.exe scripts/check_repository.py`：通过；暂存后、提交前再次运行。
- `.venv/Scripts/python.exe scripts/verify_models.py`：退出码 1，逐项报告两个默认 CT2 模型各 5 个文件及 2 个 VAD 文件缺失，均带完整路径；没有下载或复制模型。此命令的验收要求允许明确报告缺失。
- 本地 `models/manifest.json` 由无个人路径的示例创建，已被忽略；旧项目模型目录只读检查，不猜测其模型身份、不改动其文件。
- `.venv/Scripts/python.exe -m ruff check backend scripts`、`ruff format --check backend scripts`：通过。原有仓库脚本仅整理 import/空行以纳入统一检查。
- `TMPDIR=<项目>/data/tmp .venv/Scripts/python.exe -m pytest -q`：8 passed。覆盖文件齐全/缺失、损坏/错误清单、重复 id、错误 type/task、CLI 错误输出；临时空文件只用于文件检查，不代表真实模型测试。
- `uv pip check --python .venv/Scripts/python.exe`：23 个包兼容。安装命令末尾曾尝试 `python -m pip --version`，因 uv 环境默认无 pip 返回 1；依赖安装已成功，后续使用 uv 检查。
- 已建立 Windows/Linux Python 3.10 CI，实际远端运行尚未发生；本地相同检查通过。

## Phase 1 验收记录

- Phase 0 已独立提交 `011b7c1`（`chore: complete phase 0 environment and model verification`），开始 Phase 1 前再次阅读状态并确认工作区干净。
- FastAPI 已实现随机 token、受限 CORS 和 health/models API。显式 `SIDECAR_TOKEN=dev` 仅用于固定示例验收，token 不通过 HTTP 返回。配置支持项目根、模型目录、清单、临时目录、设备和计算类型的环境覆盖。
- 在 backend 目录运行 `SIDECAR_TOKEN=dev ../.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765`，随后执行 `curl -H "X-Sidecar-Token: dev" http://127.0.0.1:8765/api/health`：HTTP 200，返回 `{"status":"ok","version":"0.1.0","models_ok":false}`。
- 实际 HTTP 的 `/api/models` 返回两个默认模型的缺失状态；无 token 返回 401，非法 Origin 返回 403；允许来源的 401 保留 CORS 响应头。`Get-NetTCPConnection` 确认只监听 `127.0.0.1:8765`。验收进程完成后关闭。
- backend 目录执行 `TMPDIR=<项目>/data/tmp ../.venv/Scripts/python.exe -m pytest -q`：32 passed，1 条第三方弃用警告（Starlette 0.46.2 的 TestClient 引用 AnyIO 已弃用的 BlockingPortal 别名），不影响结果，未隐藏警告。
- 测试覆盖模型正常/缺失/损坏、随机 token 轮换、鉴权、CORS/预检、环境配置和错误路径。独立审查发现非法路径导致 500、合法来源 401 缺 CORS 两处问题，均已修复并增加回归；非法路径和权限异常现返回中文检查结果。
- Ruff 静态/格式、仓库基础和23个依赖兼容检查通过；没有执行真实 ASR、GPU 或远端 CI。README 已同步安装、启动、token、模型和检查命令。
- 阶段提交前按明确路径暂存并审阅差异；本地提交通过 `git log --oneline` 查看。

## Phase 2 验收记录

- 在 `feat/audio-processing` 分支实现 `audio/decode.py`、`audio/vad.py`、`audio/chunks.py`、`audio/tempfiles.py` 与 `scripts/make_demo_assets.py`，仅覆盖 2.1–2.5；`[V1]` waveform peaks 未实现。
- 解码：PyAV 将输入统一重采样为 16 kHz 单声道 `float32`，时长由实际采样数计算；不支持后缀、缺失文件、无音轨、空采样和解码异常均给出中文错误。
- VAD：优先本地 `whisper_vad.onnx`，按 30 秒窗口生成 Whisper log-Mel 特征并读取 metadata；末端帧数按实际采样裁剪，避免补齐部分越过真实时长。ONNX/metadata/特征配置缺失或运行失败时记录中文警告并降级为 RMS 能量阈值；不联网下载特征配置。
- 切块：毫秒、左闭右开区间；合并 `<=500 ms` 静音间隔并硬切为每块 `<=30000 ms`，用性质断言确认不重叠且不丢失原语音区间。临时目录以 `job_temp_directory` 上下文管理，正常/异常路径均删除，拒绝路径穿越。
- `TMPDIR=<项目>/data/tmp .venv/Scripts/python.exe -m pytest backend/tests/test_audio.py -q`：30 passed。含 44.1k 双声道转 16k mono、不支持/缺失文件、能量边界与纯静音、显式 padding、ONNX 优先与失败降级/末端裁剪（mock）、35 秒硬切、短静音合并、非法参数、临时目录异常清理与非法 job-id。
- `python scripts/make_demo_assets.py --out data/demo`：生成 6 秒合成 `sample.wav`（440/660 Hz 正弦 + 静音）和如实说明信号内容的 `sample.txt`；两者被 Git 忽略，明确不是日语语音或 ASR 参照文本。
- 格式烟雾：用 ffmpeg 从同一合成 WAV 转出 mp3/m4a/flac/mp4/mkv，`decode_audio` 均返回 16 kHz mono float32，时长 6000–6016 ms，符合容差；临时文件随上下文清理。
- 本地 ONNX 只读烟雾：以旧项目 `models/whisper_vad.onnx` + metadata 解码 `data/demo/sample.wav` 并推理成功，6 秒音频末段未越界；正弦波被判为非语音，返回空区间，未冒充语音识别结果。
- 审查：指定的独立审查子代理两次异常/失败无输出，未据此写成已审查；改由 Lead 人工复核代码与差异，未发现阻塞问题。

## Phase 3 验收记录

- 在 `feat/asr-integration` 分支实现 `asr/model_manager.py`、`asr/whisper_backend.py`、`jobs/schemas.py`、`jobs/manager.py`、`api/jobs.py` 与 `scripts/smoke_transcribe.py`，覆盖 3.1–3.5；3.6 的批量/流式属 `[V1]`，未实现。
- 本地 `models/manifest.json` 已将 `whisper-ja-1.5B` 指到用户确认的旧项目 `faster_whisper_transwithai/models`（本地绝对路径仅写入被忽略的 manifest，只读引用，不复制权重、不进 Git）；`chickenrice-v2` 目录仍缺失。健康接口因此保持 `models_ok=false`，如实反映并非所有模型齐全。
- 真实加载：`ModelManager.load("whisper-ja-1.5B")` 在 RTX 4070 上以 `cuda/bfloat16` 成功初始化并卸载；未下载任何权重。
- 真实日语样本：用户提供的本地 MP3（144.9 秒，被 `.gitignore` 忽略）。取前 30 秒临时片段验收，不复制原文件、不提交、不在文档记录原文。结果 4 段，首段 `00:00:00,840 → 00:00:09,140`、末段 `00:00:28,200 → 00:00:29,980`，全部文本非空，共 91 字符；临时音频与 SRT 用后删除。
- 真实 API：用会话随机 token 调用 `POST /api/jobs` 返回 202（`job-20261108-001`，初始 running/decode），轮询 `GET /api/jobs/{id}` 最终 `succeeded`、`progress=1.0`、4 段、`error=null`；与脚本结果一致。
- 完整长音频：同一 144.9 秒样本完整运行，检测语音 115.0 秒、17 个 ≤30 秒推理块、17 段；首段 `00:00:00,840 → 00:00:09,160`、末段 `00:02:15,280 → 00:02:23,220`，全部非空；GPU 显存无溢出，进程正常结束。
- AGENT 固定验收示例使用合成 `data/demo/sample.wav`；该正弦波在真实模型上返回 0 段（属预期），不能证明日语转写，因此以用户提供的真实日语样本作为 ASR 验收素材，并在 README 说明差异。
- `TMPDIR=<项目>/data/tmp .venv/Scripts/python.exe -m pytest -q`：91 passed（新增 `test_asr.py` / `test_jobs.py` / `test_translation.py`，覆盖模型清单/设备/精度/缓存、时间戳偏移与裁剪、任务成功/失败/404/鉴权/CORS、DeepSeek 环境变量与 .env、分批、乱序 id、重试、401 与格式错误）。1 条 Starlette TestClient 第三方弃用警告，未隐藏。
- Ruff 静态/格式、仓库基础检查通过；未做批次并发、取消、WebSocket、持久化或打包验收。
- 翻译模式：2026-11-08 需求变更，改为 **DeepSeek Chat Completions API**（`deepseek-flash`，`base_url=https://api.deepseek.com`），不再使用本地翻译模型。AGENT.md 已同步：音频始终本地；只有 `mode=translate` 时发送字幕文本，音频不上传；API Key 只从 `.env`/环境变量读取。
- `translation/deepseek.py`：按 20 段/6000 字符分批，JSON 模式要求 id 对齐；处理 401/402/429、超时、格式错误并返回中文错误；不记录正文或 Key。`JobRequest.translation` 为 `{provider:"deepseek", model:"deepseek-flash"}`。
- `.env.example` 已提交（无密钥）；本地 `.env` 由用户填写 `DEEPSEEK_API_KEY`，该文件被 Git 忽略，未读取或记录 Key 内容。
- 新增 `tests/test_translation.py`（MockTransport，不发真实网络）覆盖环境变量/.env、缺 Key、分批、乱序 id、重试、401、格式错误；`test_jobs.py` 增加翻译管线注入测试。
- Mock DeepSeek 端到端：用本地 HTTP mock 服务跑 30 秒样本，4 段全部生成“日语原文 + 中文译文”双语 SRT；仅验证脚本/客户端/字幕链路，不代表真实 DeepSeek 翻译质量。
- **真实 DeepSeek 翻译验收**：用户填写本地 `.env` 后，完整 144.9 秒 MP3 真实运行 `scripts/smoke_translate.py`；ASR 17 段 → DeepSeek `deepseek-flash` 单批返回 17 段译文。双语 SRT 共 17 块，每块 4 行（序号/时间/日语/中文），日语 476 字符、中文 371 字符，所有译文非空且无一段与原文相同；首段 `00:00:00,840 → 00:00:09,160`，末段 `00:02:15,280 → 00:02:23,220`。字幕保存在 `data/review/`（Git 忽略），未提交原文/译文；真实翻译质量由用户人工复核。

## Phase 4 验收记录

- 在 `feat/glossary-engine` 分支实现 `glossary/models.py`、`normalizer.py`、`matcher.py`、`replacer.py`、`io.py`、`store.py`、`api/glossary.py` 与 `scripts/glossary_demo.py`，覆盖 4.1–4.7 首版 exact 范围；`regex`/`fuzzy`/`mask` 明确拒绝，不静默跳过。
- 归一化：NFKC + 英文 casefold + 片假名折叠平假名；每个归一化字符保留原文索引映射，命中位置按原文 `start/end` 返回。已覆盖全角/半角、大小写、假名与中文/日文混排。
- 匹配：`pyahocorasick 2.3.1` 多模式扫描（纯 Python `find` 回退），最长匹配优先、同长度按 priority 高者优先，重叠候选按左起贪心去重；禁用词条与不一致 field 不参与。
- 替换：`correct` 仅作用 `text`，`translate` 仅作用 `translation`，`keep` 只高亮；`apply_to_segment()` 返回副本，只改 `text/translation` 并写入 `hits`，`raw_text/raw_translation` 保持首次模型输出。任务管线在 `glossary_id` 存在时自动应用词表。
- CSV/JSON：表头 `source,variants,target,category,match_mode,regex,priority,field,policy,enabled`，variants 用 `|`；重复 source 合并，target/field/policy 冲突拒绝；CSV 往返解析一致。
- API：`GET /api/glossary`、`POST /api/glossary/import`、`GET /api/glossary/{id}/export`、`POST /api/glossary/preview` 已用 TestClient 验证导入、预览、导出和 404。
- `TMPDIR=<项目>/data/tmp .venv/Scripts/python.exe -m pytest backend/tests/test_glossary.py -q`：19 passed；全量 `pytest -q`：111 passed（1 条 Starlette 第三方弃用警告，未隐藏）。
- `python scripts/glossary_demo.py --text "田中さんと渋谷で会いました" --glossary data/glossary/demo.json`：命中 2 条（`田中`→`田中太郎` correct、`さん` keep），输出 `田中太郎さんと渋谷で会いました`；`--field translation` 时只命中 `渋谷`→`涩谷`，验证字段隔离。
- 词表 demo 使用合成 `examples/glossary.demo.json`，复制到被忽略的 `data/glossary/demo.json` 验收；未使用真实用户词表或私人文本。Ruff、仓库基础检查通过。

## 环境故障与处理

首次 pytest 在测试 setup 阶段遇到系统临时目录权限问题，8 个用例未执行。改用项目内的 `data/tmp` 作为 TMPDIR 后，8 个测试通过。复现命令见 README。

## Phase 5 验收记录

- 在 `feat/electron-workbench` 分支实现 Electron + React 工作台。渲染器通过受限 preload IPC 调用本地服务、打开媒体及保存对话框。主进程校验私有 `SIDECAR_READY` 握手，关闭时等待子进程退出。字幕编辑和导出使用主进程中的会话副本，模型原始结果只读。
- Glasswork 使用 v1.1.0（`2fb84e9`）的 CSS、Chromium SVG 折射和 MIT 许可证，随应用本地打包。应用根据主题选择玻璃材质，降低透明度时切换为实底。按两种主题的桌面截图抽查玻璃表面文字与背景，所测最小对比度为浅色 7.23:1、深色 9.61:1。
- `pnpm --dir apps/desktop dev` 启动 Vite、Electron 和 Python 服务。本机的 TCP 保留范围覆盖 5173，已验证改用系统分配的环回端口。Electron 下载遇到 GitHub 504，使用同版镜像并核对官方 npm 包附带的 SHA-256 后运行。
- Windows Electron 生产界面烟雾通过。合成正弦信号验证了录音 WebM 解码、任务成功、临时录音清理、拖放和空 SRT。用此前验收的本地日语样本模拟麦克风约 10 秒得到 3 段，并验证保留录音副本。拖放同一完整样本得到 17 段，手工编辑后导出 SRT，模型原文保持不变。验收使用模拟麦克风和受控保存路径，未做物理麦克风人工验收或重跑真实 DeepSeek 请求。
- 通过桌面 UI 导入合成词表并显示命中及替换预览。Ruff 静态和格式检查、仓库基础检查、后端 pytest 113 项、前端 lint/严格 typecheck/2 项单测/build 通过。CI 已配置 Windows/Linux 上的前端检查，远端运行待实际触发。

## 遗留与下一步

- Phase 0–5 的首版范围已完成。Phase 6 的跨会话任务存储和 WebSocket、Phase 7 的逐条术语接受/拒绝/撤销及保存接口、Phase 9 的安装包仍待开发。Phase 5 提供轮询与处理步骤边界取消。
- Phase 4 的 regex/fuzzy 属 V1、mask 属 STRETCH，均未实现；导入时会明确拒绝，不影响 exact 范围验收。
- Phase 3 的 DeepSeek 翻译已真实跑通，真实翻译质量与专名一致性仍需按样本继续评估。
- Phase 2 的 `[V1]` waveform peaks、Phase 3 的批量任务和流式转写、Phase 5 的自动保存草稿仍待开发。
- 未创建远程仓库，未推送、发布或打标签。
