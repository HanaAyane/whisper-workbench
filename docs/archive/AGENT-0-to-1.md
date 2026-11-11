# JP Voice Workbench — 日语语音转录 / 翻译 / 术语替换工作台

> 这是给 AI 编码助手的执行清单，也是项目的唯一需求基线。
> 项目目标：基于个人长期使用本地语音模型处理日语音频的需求，开发集日语转录、日中翻译、专名纠错、译名统一和字幕复核于一体的本地优先 Electron 工作台。
> 扩展方向：词表与规则模块采用可配置的匹配、替换和人工确认机制，便于后续探索其他文本处理场景。中文法律文本脱敏仅作为可讨论的技术迁移方向，合成数据演示可选。**不声称具备法律行业经验，不使用真实法律文件。**

---

## 0. AI 执行规则（先读这一节）

1. **先读完整份 `AGENT.md`，再开始任何代码修改。**
2. 每个 Phase 开始前：
   - 查看 `STATUS.md`（不存在就创建）；
   - `git status`，确认工作区干净或知道未提交改动；
   - 只实现当前 Phase，不要一次写完全部项目。
3. 每个 Phase 完成后：
   - 运行该 Phase 的“验收命令”；
   - 更新 `STATUS.md`：完成项、测试结果、遗留问题；
   - 提交一个语义清晰的 commit（如 `feat(audio): add 16k decode pipeline`）。
4. 不要伪造数据、指标或用户经历；demo 数据必须是合成/公开、可说明来源的。
5. 不要删除或覆盖用户已有的 `faster_whisper_transwithai`、`Faster-Whisper-TransWithAI-ChickenRice` 目录。
6. 不要把模型权重、音频、用户词表提交进 Git；它们只放本地目录。
7. 遇到模型文件缺失时，先检查 `models/` 和 `scripts/verify_models.py`，不要擅自下载超大模型。
8. 优先使用 `pnpm`、Python 3.10、`faster-whisper` 1.2.1、CTranslate2 4.8；版本冲突时记录原因再偏离。
9. 所有 UI/日志/错误信息默认中文；代码变量、API、文件名用英文。
10. 本文件的验收标准优先级高于 AI 的临时想法。
11. 功能优先级以真实的日语转录、翻译和字幕校对需求为准。中文语音评测、中文法律文本脱敏及 `mask` 演示不作为首版或完善版的必做验收，不为招聘展示额外扩大范围。
12. Git、环境复现和质量检查按第 3.5 节执行。阶段提交前查看暂存差异，不混入用户文件或无关修改；不要擅自重置历史、强制推送或修改全局 Git 配置。

---

## 1. 项目定位

### 1.1 一句话

一个**本地优先**的 Electron 桌面工作台：导入或录制日语音频 → 本地 Whisper 模型转录与按需日中翻译 → 用术语表生成原文纠错和译名统一建议 → 在字幕编辑器中人工复核 → 导出 SRT/VTT/LRC/TXT。

### 1.2 真实使用场景

用户经常处理日语长音频，实际痛点：

- ASR 经常把人名、地名、组织名、作品名、专有术语听错；
- 同一专名在不同片段里写法/译名不一致；
- 翻译结果中的人名、地名、术语需要统一；
- 逐句手工查找替换很耗时；
- 不想把私人音频上传到云端。

### 1.3 专名处理原则

- **原文纠错**：在日语原文中匹配词表里的已知别名、写法变体和常见误识别，建议改为正确日语写法。词表无法保证从任意错误转录中恢复未知专名。
- **译名统一**：在中文译文中匹配专名的已知译名变体或仍保留的日语写法，建议改为用户指定的中文译名。词表替换不承担整句翻译。
- **处理范围分开**：规则明确作用于日语原文或中文译文，不把原文纠错规则无条件应用到译文，也不以中文译名覆盖日语原文。
- **人工决定**：保留首次模型输出；展示命中位置和替换前后内容，支持接受、拒绝、手工修改及撤销。导出使用用户当前确认的编辑结果。
- **匹配方式按需增加**：先做好精确词表、别名和重叠处理，再为有稳定模式的内容添加正则；模糊匹配作为后续增强。词表命中不等同于已经正确理解上下文。

### 1.4 可选的技术迁移说明

术语/专名替换的抽象是：

> 文本规范化 → 词表/规则匹配 → 命中分类 → 替换建议（纠正 / 译名统一 / 保留）→ 人工复核 → 导出

匹配接口、规则管理、替换策略和人工确认流程可复用于其他文本处理场景。例如，后续可以探索增加 `mask` 策略，对命中的内容进行掩码替换。但中文法律文本需要单独定义实体类型、语言规则和测试数据，验证误报与漏报；不能仅凭日语词表功能就声称已经支持中文法律文本脱敏。

迁移方向可在项目说明或面试中简要讨论，不作为产品主线或交付前置条件。如实际实现演示，只使用合成数据，并明确其覆盖范围；未实现时只表述为设计上的扩展可能。

---

## 2. 范围与非目标

### 2.1 必须做（MVP）

- Electron 桌面应用可启动；
- 麦克风录音或拖入音频/视频；
- 本地 faster-whisper / CTranslate2 模型转写；
- 日语转录 + 可选日中翻译（本地 ASR；翻译默认通过 DeepSeek API，仅发送字幕文本，音频不上传）；
- VAD 分段，长音频不一次性爆显存；
- 术语表（CSV/JSON 导入导出）、精确词表/别名匹配及 `correct/translate/keep` 策略；
- 字幕编辑器：区分原文纠错与译名统一，高亮命中、接受/拒绝替换，保留模型原始结果；
- 导出 SRT / VTT / LRC / TXT；
- 本地运行；音频始终本地处理、不上传；启用翻译时仅将字幕文本发送到用户配置的 DeepSeek API；
- pytest 单元测试 + 一个端到端 demo；
- README + 实际功能验收记录 + 截图/录屏脚本。

### 2.2 后续增强（V1）

- 任务队列、暂停/取消、历史记录；
- 模型管理 UI（CPU/GPU、int8/fp16、模型目录）；
- 术语正则规则、模糊匹配、禁用词；
- 批量文件处理；
- 自动保存/恢复；
- 根据日语样本记录专名错误、替换效果和性能 benchmark；
- Windows 安装包；macOS 构建说明（可在 GitHub Actions macOS runner 上打）。

`[STRETCH]`：文本输入 tab、`mask` 策略及合成数据迁移演示均为可选扩展，不影响 MVP/V1 完成判定。

### 2.3 明确不做

- 不做云端账号、同步、多人协作；
- 不做模型训练/微调（本项目是推理应用）；
- 不做法律意见、合规判断、真实客户数据处理；
- 不把本项目包装成“法律 AI 产品”；
- 不默认录音上传，不接入第三方分析/遥测；DeepSeek 翻译是用户显式启用的文本外发功能，不是默认遥测。

---

## 3. 技术栈

### 3.1 前端 / Electron

- Node.js 20+，pnpm 9+
- Electron 31+
- React 18 + TypeScript + Vite
- Zustand（轻量状态）
- 原生 CSS 或 CSS Modules；不要为了 UI 引入重型组件库
- `electron-builder` 打包
- `vitest` 或 `jest` 做 renderer 单测（可选）
- Playwright 做 Electron 烟雾测试（V1）

### 3.2 后端 / Python

- Python 3.10
- FastAPI + Uvicorn
- Pydantic v2
- `faster-whisper==1.2.1`
- `ctranslate2>=4.5.0`
- `av`（PyAV，音视频解码）
- `numpy`
- `pyahocorasick`（术语多模式匹配；如果安装失败，用纯 Python Trie 兜底）
- `regex`（Unicode 正则）
- `jiwer`（CER 评测）
- `pytest`
- `pyinstaller`（sidecar 打包）

### 3.3 模型 / 音频工具

- 主 ASR 模型：`whisper-ja-1.5B` 的 CT2 版本（本地目录）
- 翻译：DeepSeek Chat Completions API（默认 `deepseek-flash`，`base_url=https://api.deepseek.com`），通过 `DEEPSEEK_API_KEY` 显式启用；只发送字幕文本，不发送音频。原本地翻译模型 `chickenrice0721/whisper-large-v2-translate-zh-v0.2-st-ct2` 不再是首版依赖，可在未来作为离线备选。
- VAD：复用 `whisper_vad.onnx` + `whisper_vad_metadata.json`
- `ffmpeg` 可执行文件（优先系统安装，打包时可带 `ffmpeg-static` 或平台 ffmpeg）
- 模型目录不提交 Git，通过 `settings.json` / 环境变量指定

### 3.4 关键原则

- Electron renderer **不能直接访问 Node/文件系统**；必须通过 preload 的 contextBridge 暴露受限 API。
- Python sidecar 只监听 `127.0.0.1`，启动时生成随机 token，Electron 通过 header 传入。
- 音频解码、VAD 与 ASR 全部在本地完成，音频文件不上传。
- 默认不联网；只有用户显式选择 DeepSeek 翻译时，才将`待翻译字幕文本`发送到 `https://api.deepseek.com`。请求前须在界面/日志中明确提示外发范围；API Key 只从本地 `.env` 或环境变量读取，不写入日志、不提交 Git。
- 模型下载是显式操作，单独提示。

### 3.5 Git 与开发工程基线

#### 版本控制

- 项目使用独立 Git 仓库，默认分支为 `main`。新增功能、修复或较大的文档变更使用 `feat/<topic>`、`fix/<topic>`、`docs/<topic>` 等短期分支；只合入完成相应验收的内容。
- 每次修改前查看 `git status --short`；提交前查看 `git diff`、`git diff --cached`，明确区分已有改动与本次工作。使用明确路径暂存文件。
- 一个提交围绕一个可说明的目的，使用 `feat`、`fix`、`docs`、`test`、`chore` 等提交前缀。每个 Phase 可以有多个小提交，完成时同步 `STATUS.md` 和相关文档。
- 源码、测试、需求、示例配置、构建配置及依赖锁文件纳入 Git；模型、私人媒体、用户词表、转录/翻译结果、数据库、日志、缓存、密钥及本地环境不提交。可共享的合成文本/规则放在 `tests/fixtures/` 或 `examples/`，不使用个人材料冒充示例。
- Git 忽略规则不能清除已有历史；提交前运行仓库基础检查，发现误纳入文件先停止提交并处理。共享历史优先用 `git revert` 回退；不擅自执行破坏工作区的重置、清理或强制推送。
- 先建立本地版本记录；远程仓库创建、推送和发布按用户后续明确指示执行。

#### 环境与依赖

- 根目录的 `.editorconfig` 和 `.gitattributes` 统一 UTF-8、缩进与换行；Python 默认 4 空格，TS/JSON/YAML 默认 2 空格，文本默认 LF。
- 前端统一使用 pnpm。创建前端项目时写明实际 Node/pnpm 版本与 `packageManager`，提交 `pnpm-lock.yaml`，后续安装使用 `--frozen-lockfile`；不混用多种包管理器修改依赖树。
- Python 使用项目内 `.venv`，优先按第 3.2 节准备 Python 3.10。若采用其他版本，先验证依赖兼容性，并在 `STATUS.md` 记录偏离原因及实际版本；不要修改系统默认 Python 或全局安装项目依赖。
- 创建后端时记录直接依赖并提交可复现的锁定依赖清单；运行环境、GPU/CUDA 条件和复现命令写入 README。本机路径和敏感配置使用被忽略的本地文件，仓库只提交不含个人数据的示例。

#### 检查与交付

- 当前工程基础检查入口：`python scripts/check_repository.py`。它检查仓库位置、差异空白、误跟踪的忽略文件、大文件和已跟踪 Python 文件的语法；不能替代业务测试、模型运行或人工验收。
- Phase 1 引入后端时，配置实际可运行的 Python 格式/静态检查和 `pytest`；Phase 5 引入前端时，启用 TypeScript 严格检查，配置 lint、typecheck 和 build 脚本，按功能风险补充测试。
- 业务代码引入时同步增加真正执行对应检查的 CI；常规 CI 不下载大模型、不使用私人音频。真实模型、GPU 和安装包验收与 mock 测试分开记录。
- 每次提交运行仓库基础检查和受影响模块的检查；结果、命令和未完成项如实写入 `STATUS.md`。尚未存在的模块不写成已通过，也不以占位脚本代替验收。
- 具体分支、提交、检查和故障记录流程见 `CONTRIBUTING.md`。

---

## 4. 总体架构

```
┌──────────────────────────────────────────────────────────────┐
│ Electron Main                                                │
│  - window / lifecycle / file dialogs                         │
│  - spawn Python sidecar; discover port + token               │
│  - IPC via preload contextBridge                             │
└──────────────────────┬───────────────────────────────────────┘
                       │ local HTTP / WebSocket
┌──────────────────────▼───────────────────────────────────────┐
│ Electron Renderer (React)                                    │
│  - Record / Drop / Job list / Transcript editor              │
│  - Glossary panel / Settings / Export                        │
└──────────────────────┬───────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────────┐
│ Python Sidecar (FastAPI)                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐  │
│  │ audio       │  │ asr         │  │ glossary             │  │
│  │ ffmpeg/av   │→ │ faster-     │→ │ normalize + match    │  │
│  │ 16k mono    │  │ whisper     │  │ + replace policies   │  │
│  │ VAD / chunk │  │ CT2 models  │  │ + hit review         │  │
│  └─────────────┘  └─────────────┘  └──────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐  │
│  │ export      │  │ storage     │  │ job manager          │  │
│  │ SRT/VTT/LRC │  │ settings    │  │ queue/progress/cancel│  │
│  └─────────────┘  └─────────────┘  └──────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

**数据流**：Electron 录音/文件 → 临时音频文件 → 后端解码为 16k mono → VAD 切段 → 逐段 faster-whisper 转录/按需翻译 → 保留原始输出的 Segment → 按字段生成术语替换建议 → 字幕编辑器人工复核 → 导出当前编辑结果。临时音频按第 7.5 节清理，不等待用户完成复核。

---

## 5. 目录结构

```text
jp-voice-workbench/
├─ AGENT.md
├─ README.md
├─ STATUS.md
├─ CONTRIBUTING.md
├─ .gitignore
├─ .gitattributes
├─ .editorconfig
├─ apps/
│  └─ desktop/
│     ├─ package.json
│     ├─ electron-builder.yml
│     ├─ src/
│     │  ├─ main/
│     │  │  ├─ index.ts          # BrowserWindow, sidecar lifecycle
│     │  │  └─ sidecar.ts        # spawn Python, port/token
│     │  ├─ preload/
│     │  │  └─ index.ts          # contextBridge API
│     │  └─ renderer/
│     │     ├─ App.tsx
│     │     ├─ components/
│     │     │  ├─ RecorderPanel.tsx
│     │     │  ├─ JobList.tsx
│     │     │  ├─ TranscriptEditor.tsx
│     │     │  ├─ GlossaryPanel.tsx
│     │     │  └─ SettingsPanel.tsx
│     │     ├─ stores/
│     │     └─ styles.css
│     └─ vite.config.ts
├─ backend/
│  ├─ requirements.txt
│  ├─ pyinstaller.spec
│  └─ app/
│     ├─ main.py                  # FastAPI app, token check
│     ├─ config.py
│     ├─ api/
│     │  ├─ health.py
│     │  ├─ models.py
│     │  ├─ jobs.py
│     │  └─ glossary.py
│     ├─ audio/
│     │  ├─ decode.py             # ffmpeg/av → 16k mono wav
│     │  ├─ vad.py                # VAD segments
│     │  └─ chunks.py
│     ├─ asr/
│     │  ├─ model_manager.py
│     │  └─ whisper_backend.py
│     ├─ glossary/
│     │  ├─ models.py
│     │  ├─ normalizer.py
│     │  ├─ matcher.py
│     │  └─ replacer.py
│     ├─ export/
│     │  └─ writers.py
│     ├─ storage/
│     │  ├─ settings.py
│     │  └─ jobs.py
│     └─ jobs/
│        └─ manager.py
├─ models/                        # gitignored; user-provided CT2/ONNX assets
├─ data/
│  ├─ demo/                       # synthetic audio + glossary examples
│  └─ glossary/
├─ scripts/
│  ├─ check_repository.py
│  ├─ verify_models.py
│  ├─ bench.py
│  └─ make_demo_assets.py
└─ docs/
   ├─ architecture.md
   ├─ benchmark.md
   └─ demo.md
```

---

## 6. 数据契约（先定接口，再写实现）

### 6.1 `ModelManifest`

`models/manifest.json`：

```json
{
  "models": [
    {
      "id": "whisper-ja-1.5B",
      "type": "asr",
      "label": "Whisper Japanese 1.5B",
      "path": "models/whisper-ja-1.5B",
      "language": "ja",
      "task": "transcribe",
      "compute_type": "bfloat16"
    },
    {
      "id": "chickenrice-v2",
      "type": "translate",
      "label": "海南鸡 v2 日中翻译",
      "path": "models/chickenrice-v2",
      "language": "ja",
      "task": "translate",
      "compute_type": "bfloat16"
    }
  ],
  "vad": {
    "model_path": "models/whisper_vad.onnx",
    "metadata_path": "models/whisper_vad_metadata.json"
  }
}
```

### 6.2 `JobRequest`（`POST /api/jobs`）

```json
{
  "input_path": "C:/data/demo/sample.wav",
  "mode": "transcribe",
  "asr_model_id": "whisper-ja-1.5B",
  "translation": {
    "provider": "deepseek",
    "model": "deepseek-flash"
  },
  "language": "ja",
  "glossary_id": "default",
  "export_formats": ["srt", "vtt"],
  "vad": {
    "threshold": 0.5,
    "min_speech_duration_ms": 300,
    "min_silence_duration_ms": 100,
    "speech_pad_ms": 200
  }
}
```

### 6.3 `Segment`

```json
{
  "id": 0,
  "start": 1200,
  "end": 4350,
  "raw_text": "田中さんに会いに行きます。",
  "raw_translation": "去见田中先生。",
  "text": "田中さんに会いに行きます。",
  "translation": "去见田中先生。",
  "hits": []
}
```

`raw_text` / `raw_translation` 保存首次模型输出，复核时只读；`text` / `translation` 为可编辑副本，初始值与对应原始输出相同。仅转录时两个翻译字段为 `null`。接受替换、手工修改和撤销均作用于编辑副本；导出读取当前编辑副本，不覆盖原始输出。

### 6.4 `GlossaryEntry`

```json
{
  "id": "term-001",
  "source": "田中太郎",
  "variants": ["たなかたろう", "Tanaka Taro", "田中"],
  "target": "田中太郎",
  "category": "person",
  "match_mode": "exact",
  "regex": null,
  "priority": 100,
  "field": "text",
  "policy": "correct",
  "enabled": true
}
```

`field` 指定规则作用于 `text`（日语原文）或 `translation`（中文译文）；CSV/JSON 导入时校验作用字段与策略是否一致。

首版 `policy` 枚举：

- `correct`：作用于 `text`，将词表覆盖的误识别/变体纠正为正确日语写法；
- `translate`：作用于 `translation`，将已知译名变体或保留的日语专名统一为指定中文译名；
- `keep`：在指定字段只高亮，不替换。

`mask` 仅作为 `[STRETCH]` 扩展策略：未来可将命中内容替换为 `[人名]` / `[地名]` 等。首版无需实现或通过该策略的验收；尚未实现时，导入或请求使用该策略应明确提示不支持，不能静默跳过。

### 6.5 `TermHit`

```json
{
  "entry_id": "term-001",
  "field": "text",
  "start": 3,
  "end": 7,
  "matched_text": "田中",
  "replacement": "田中太郎",
  "policy": "correct",
  "confidence": 1.0
}
```

### 6.6 `JobStatus`

```json
{
  "id": "job-20261106-001",
  "state": "queued|running|succeeded|failed|cancelled",
  "progress": 0.0,
  "stage": "decode|vad|asr|glossary|export",
  "message": "",
  "segments": [],
  "outputs": [],
  "error": null
}
```

### 6.7 API 列表

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| GET | `/api/models` | 读取 manifest + 校验模型文件 |
| POST | `/api/jobs` | 创建转写任务 |
| GET | `/api/jobs/{id}` | 查询状态 |
| PATCH | `/api/jobs/{id}/segments/{segment_id}` | 保存人工复核后的原文/译文副本，原始输出只读 |
| POST | `/api/jobs/{id}/export` | 按指定格式导出当前编辑结果 |
| POST | `/api/jobs/{id}/cancel` | 取消任务 |
| WS | `/ws/jobs/{id}` | 进度/segment 推送 |
| GET | `/api/glossary` | 词表列表 |
| POST | `/api/glossary/import` | 导入 CSV/JSON |
| GET | `/api/glossary/{id}/export` | 导出词表 |
| POST | `/api/glossary/preview` | 对一段文本预览命中与替换 |

---

## 7. 开发阶段清单

> 标记说明：`[MVP]` = 满足真实日语使用需求的最小可用版；`[V1]` = 在日常使用中逐步完善的版本；`[STRETCH]` = 可选增强。以功能验收划分阶段，不承诺固定一天或三天完成，也不以投递时间要求补齐全部功能。

### Phase 0 — 项目初始化 `[MVP]`

- [ ] 0.1 创建独立仓库 `jp-voice-workbench`，使用 `git init -b main`；沿用已有提交身份，不修改全局 Git 配置。
- [ ] 0.2 核对 Node 20+、pnpm 和 Python；记录实际版本，准备兼容的项目 `.venv`。Python 版本偏离 3.10 时按第 3.5 节记录和验证。
- [ ] 0.3 创建 `README.md`、`STATUS.md`、`CONTRIBUTING.md`、`.gitignore`、`.gitattributes`、`.editorconfig`。
  - `.gitignore` 必须覆盖：`node_modules/`、`.venv/`、`models/`、`data/tmp/`、`dist/`、音视频、字幕输出、日志、数据库、缓存、密钥和本地配置；依赖锁文件和无敏感信息的示例配置应可提交。
- [ ] 0.4 写 `scripts/verify_models.py`：检查 manifest、`model.bin`、`tokenizer.json`、`preprocessor_config.json`、`vocabulary.json`、VAD 文件是否存在。
- [ ] 0.5 建 `STATUS.md` 表格：Phase / 状态 / 测试 / 备注。
- [ ] 0.6 创建并运行 `scripts/check_repository.py`，检查工程基础和提交内容；记录环境缺口，不把工具存在当作依赖已兼容。
- [ ] 0.7 检查明确暂存的文件，建立首个工程基础提交；确认 `main` 分支和工作区状态。

**验收**：

```bash
python scripts/check_repository.py
python scripts/verify_models.py
# 输出每个模型 OK/缺失；缺失时给出明确路径
git status --short
```

模型校验脚本、应用依赖或 `.venv` 尚未准备时，Phase 0 保持进行中；Git 与文档基础可先单独提交。

---

### Phase 1 — Python Sidecar 骨架 `[MVP]`

- [ ] 1.1 `backend/app/main.py`：FastAPI 实例、CORS 只允许 `http://127.0.0.1:*`、启动时生成随机 token。
- [ ] 1.2 `config.py`：项目根、模型目录、临时目录、默认设备/计算类型。
- [ ] 1.3 `GET /api/health` 返回 `{status, version, models_ok}`。
- [ ] 1.4 `GET /api/models` 读取 manifest，返回模型列表与校验状态。
- [ ] 1.5 `requirements.txt` 锁定版本。
- [ ] 1.6 `pytest` 建立 `tests/test_health.py`。

**验收**：

```bash
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8765
curl -H "X-Sidecar-Token: dev" http://127.0.0.1:8765/api/health
pytest -q
```

---

### Phase 2 — 音频输入与处理 `[MVP]`

- [ ] 2.1 `audio/decode.py`：接受 `.wav/.mp3/.m4a/.flac/.mp4/.mkv`，用 PyAV 或 ffmpeg 解码为 16kHz 单声道 float32。
- [ ] 2.2 `audio/vad.py`：优先使用 `models/whisper_vad.onnx`；VAD 不可用时提供能量阈值 fallback，并在日志中说明。
- [ ] 2.3 `audio/chunks.py`：把语音区间合并为 ≤30 秒的连续块；支持最大时长/静音 gap 参数。
- [ ] 2.4 临时文件管理：统一写 `data/tmp/<job-id>/`；任务结束后清理；异常也清理。
- [ ] 2.5 `tests/test_audio.py`：用 1–2 秒合成正弦波/静音生成 wav，验证采样率、声道、时长和切块边界。
- [ ] 2.6 `[V1]` 输出 waveform peaks（供 UI 画波形）。

**验收**：

```bash
python -m pytest tests/test_audio.py -q
python scripts/make_demo_assets.py --out data/demo
# 生成 demo 音频和对应文本
```

---

### Phase 3 — ASR / 翻译接入 `[MVP]`

- [ ] 3.1 `asr/model_manager.py`：
  - 读取 `models/manifest.json`；
  - 校验模型目录；
  - 加载/预热/卸载；
  - 支持 `device: cpu|cuda|auto`、`compute_type: int8|int8_float16|float16|bfloat16`。
- [ ] 3.2 `asr/whisper_backend.py`：
  - 使用 `faster_whisper.WhisperModel`；
  - `task="transcribe"` 或 `task="translate"`；
  - `language="ja"`；
  - 返回 `Segment` 列表（毫秒整数时间）；
  - 记录 `info.duration`、`duration_after_vad`。
- [ ] 3.3 `jobs/manager.py`：任务状态机 `queued → running → succeeded/failed/cancelled`；阶段进度 `decode/vad/asr/glossary/export`。
- [ ] 3.4 `POST /api/jobs` 创建任务，后台线程/进程执行；`GET /api/jobs/{id}` 查询。
- [ ] 3.5 先用 1 个短音频跑通“文件 → SRT”，不接 UI。
- [ ] 3.6 `[V1]` 批量文件任务；`[STRETCH]` 流式/实时转写。

**验收**：

```bash
python scripts/smoke_transcribe.py --audio data/demo/sample.wav --model whisper-ja-1.5B
# 输出 data/demo/sample.srt，首尾时间/文本非空
```

---

### Phase 4 — 术语表与替换引擎 `[MVP]`

- [ ] 4.1 `glossary/models.py`：`GlossaryEntry`、`TermHit`、`ReplacementPolicy`。
- [ ] 4.2 `glossary/normalizer.py`：
  - NFKC；
  - 日文假名/英文大小写归一；
  - 保留原文 offset 映射（至少对精确词表匹配保证原文位置）。
- [ ] 4.3 `glossary/matcher.py`：
  - `pyahocorasick` 多模式匹配，按最长匹配优先；
  - 同长度按 `priority` 高者优先；
  - `[MVP]` 支持 `match_mode: exact`，匹配 `source` 与 `variants`，仅使用作用字段一致的启用规则；
  - `[V1]` 增加 `regex` 模式，用于有稳定模式的内容，使用 `regex` 模块支持 Unicode；
  - `[V1]` 增加 `fuzzy` 模式，结果仍须人工确认。未实现的模式应明确提示不支持。
- [ ] 4.4 `glossary/replacer.py`：
  - `[MVP]` 实现 `correct` / `translate` / `keep` 三种策略；`[STRETCH]` 才扩展 `mask`；
  - 按 `field` 分别处理日语原文纠错和中文译名统一；
  - 生成替换后的文本 + `hits`；
  - 不修改原始 Segment，返回副本；
  - 支持“只预览不应用”。
- [ ] 4.5 `POST /api/glossary/preview`：输入待检查文本 + field + glossary_id，返回对应字段的高亮/替换预览。
- [ ] 4.6 CSV/JSON 导入导出：
  - 列：`source,variants,target,category,match_mode,regex,priority,field,policy,enabled`；
  - variants 用 `|` 分隔；
  - 重复 source 合并/提示。
- [ ] 4.7 `tests/test_glossary.py`：
  - `[MVP]` 精确匹配、最长匹配、变体、重叠、优先级、`correct/translate/keep`、原文/译文规则隔离、中文/日文混排、预览不改原始输出；
  - `[V1]` 正则边界及模糊匹配；`[STRETCH]` 仅在实现 `mask` 后增加其测试。

**验收**：

```bash
python -m pytest tests/test_glossary.py -q
python scripts/glossary_demo.py --text "田中さんと渋谷で会いました" --glossary data/glossary/demo.json
# 输出命中列表和替换文本
```

---

### Phase 5 — Electron 外壳与界面 `[MVP]`

- [ ] 5.1 `apps/desktop` 用 React + TypeScript + Vite 初始化。
- [ ] 5.2 `src/main/index.ts`：
  - 创建 `BrowserWindow`，`contextIsolation: true`、`nodeIntegration: false`、`sandbox: true`；
  - `preload` 暴露 API；
  - 启动/关闭 Python sidecar；
  - 开发时连接 `http://127.0.0.1:5173`，生产加载 `dist/index.html`。
- [ ] 5.3 `src/main/sidecar.ts`：
  - 选择空闲端口；
  - 生成随机 token；
  - spawn `backend`（开发：`python -m app.main`；生产：PyInstaller exe）；
  - 通过 stdout 解析 `SIDECAR_READY {port, token}`；
  - 退出时 kill，避免僵尸进程。
- [ ] 5.4 `src/preload/index.ts`：
  - `window.api.health()`
  - `window.api.models()`
  - `window.api.createJob(payload)`
  - `window.api.updateSegment(jobId, segmentId, payload)`
  - `window.api.exportJob(jobId, payload)`
  - `window.api.onJobUpdate(callback)`
  - `window.api.pickAudioFile()`
  - `window.api.saveTextFile()`
- [ ] 5.5 UI 页面/组件：
  - `RecorderPanel`：麦克风录音（MediaRecorder）+ 拖放/选择文件；
  - `JobList`：任务状态、进度、取消；
  - `TranscriptEditor`：段落列表、开始/结束、原文/译文、命中高亮、原始结果与编辑结果对照；
  - `GlossaryPanel`：词表 CRUD、CSV 导入导出、预览；
  - `SettingsPanel`：模型路径、设备、compute type、输出目录；
  - `ExportBar`：SRT/VTT/LRC/TXT 选择与导出。
- [ ] 5.6 录音流程：录音 Blob → 保存临时 webm/wav → `POST /api/jobs`；录音结束必须能清理/保留供调试。
- [ ] 5.7 `[V1]` 自动保存草稿；`[STRETCH]` 文本输入 tab 复用词表规则，`mask` 演示作为独立可选扩展。

**验收**：

```bash
pnpm --dir apps/desktop dev
# 手工验收：
# 1. 录音 10 秒，提交任务，能看到进度和转写结果
# 2. 拖入 data/demo/sample.wav，能生成 SRT
# 3. 打开 Glossary，导入 demo 词表，预览高亮
```

---

### Phase 6 — 任务队列与持久化 `[V1]`

- [ ] 6.1 `storage/jobs.py`：SQLite 或 JSON 保存任务元数据（不保存音频/原文到日志）。SQLite 也可用于词表、规则开关和设置持久化，按实际使用需求选择，不作为首版的前置条件。
- [ ] 6.2 任务恢复：应用重启后显示历史任务；不自动重跑。
- [ ] 6.3 取消：运行中任务收到 cancel 后尽快停止，状态 `cancelled`。
- [ ] 6.4 WebSocket 推送 `{progress, stage, segments?}`；UI 显示阶段进度。
- [ ] 6.5 错误处理：模型缺失、解码失败、显存不足给出可读错误 + 建议。

**验收**：

```bash
pytest -q
# 手工：创建 3 个任务，观察队列顺序；中途取消 1 个；重启后历史可见
```

---

### Phase 7 — 字幕编辑器、导出与隐私 `[MVP]`

- [ ] 7.1 `export/writers.py`：SRT/VTT/LRC/TXT 四种 writer；标准时间戳格式；UTF-8。
- [ ] 7.2 编辑器：点击段落可改原文/译文副本；通过保存接口更新 Segment，不覆盖 `raw_text/raw_translation`；支持“撤销最后一个替换”。
- [ ] 7.3 术语命中：区分日语原文纠错与中文译名统一，高亮命中范围，显示替换前后内容；逐条接受/拒绝。编辑改变文本后重新计算该字段命中，避免使用失效的位置。
- [ ] 7.4 导出前确认：选择格式、输出目录、覆盖策略；调用导出接口读取当前保存的编辑副本。推理阶段如输出初始字幕，只作为模型原始结果，不覆盖人工复核后的文件。
- [ ] 7.5 隐私：
  - 默认不联网；音频始终本地处理、不上传；
  - 启用 DeepSeek 翻译时，仅将待翻译字幕文本发送到 `https://api.deepseek.com`；界面必须明确提示文本外发范围，API Key 只从本地 `.env`/环境变量读取；
  - 临时音频任务结束即删除；
  - 日志不含完整原文/译文（只记录长度/段数），不记录 API Key；
  - 设置页显示“本地转录；翻译可选择 DeepSeek，文本将发送到云端”。
- [ ] 7.6 `[STRETCH]` 文本 input tab：粘贴文本，复用词表/规则匹配与人工确认流程。如另行实现 `mask` 迁移演示，只用合成数据并标注覆盖范围；未实现时仅在文档中讨论扩展可能，不影响日语工作台验收。

**验收**：

```bash
pytest -q
# 手工导出 SRT/VTT/LRC/TXT，检查 UTF-8、时间戳、无乱码
# 接受、拒绝、手改及撤销各演示一次，验证导出与当前保存结果一致，原始输出不变
```

---

### Phase 8 — 测试、benchmark 与性能 `[V1]`

- [ ] 8.1 单元测试：
  - `audio`：重采样、时长、切块；
  - `glossary`：匹配、重叠、替换策略；
  - `export`：时间戳格式；
  - `api`：health/models/jobs。
- [ ] 8.2 集成测试：使用 10–30 秒合成音频 + mock 模型或真实小模型，走完整 API。
- [ ] 8.3 `scripts/bench.py`：
  - 记录模型加载时间、RTF、峰值内存/显存（可用 `psutil` / `pynvml`）；
  - 对比 CPU vs GPU、int8 vs fp16（有 GPU 时）；
  - 输出 Markdown 表到 `docs/benchmark.md`。
- [ ] 8.4 Electron 烟雾测试（可选）：启动 app、健康检查、窗口可见。
- [ ] 8.5 至少 3 个回归音频：短句、1 分钟、5 分钟；记录转写文本/时间轴。
- [ ] 8.6 针对日语实际痛点建立小型样本：专名误识别、别名/写法变体、同一专名的中文译名不一致；人工核对参照文本，记录替换正确、误替换、遗漏和需要人工判断的案例。命中数量不直接等于正确数量；未测量的准确率、校对耗时或性能指标不填写。中文语音与法律脱敏评测不属于本阶段必做项。

**验收**：

```bash
pytest -q
python scripts/bench.py --audio data/demo/sample.wav --model whisper-ja-1.5B
cat docs/benchmark.md
```

---

### Phase 9 — 打包与交付 `[V1]`

- [ ] 9.1 Python sidecar 用 PyInstaller 打包，输出 `backend/dist/`；spec 文件提交仓库。
- [ ] 9.2 Electron 用 `electron-builder` 打 Windows NSIS/portable；把 sidecar exe 放入 `extraResources`。
- [ ] 9.3 首次启动检查模型目录；提供“打开模型目录”按钮和缺失提示。
- [ ] 9.4 `README.md`：
  - 环境要求；
  - 模型准备（路径/manifest）；
  - 开发启动；
  - 打包；
  - 已知限制。
- [ ] 9.5 `docs/demo.md`：1 分钟演示脚本、3 张截图、1 个 before/after 字幕样例。
- [ ] 9.6 `docs/architecture.md`：复制/更新本文件第 4 节架构图。
- [ ] 9.7 macOS：如果无 Mac 硬件，提供 GitHub Actions `macos-latest` 构建 workflow，说明未在本地验证。

**验收**：

```bash
pnpm --dir apps/desktop build
pnpm --dir apps/desktop dist
# 安装包能启动，首次启动能提示模型路径
```

---

## 8. 按功能验收的交付路径

### 8.1 最小可用版（MVP）

按顺序完成首版必做项，不包含各 Phase 中标为 `[V1]` / `[STRETCH]` 的增强：

- Phase 0（0.1–0.7）
- Phase 1（1.1–1.6）
- Phase 2（2.1–2.5）
- Phase 3（3.1–3.5）
- Phase 4（4.1–4.7 的首版项：exact、别名、correct/translate/keep、CSV/JSON、预览与测试）
- Phase 5（5.1–5.6 的外壳、录音、任务、编辑器和词表基础）
- Phase 7（7.1–7.5）

**首版验收**：

- 能启动 Electron；
- 能录制或拖入 30 秒音频；
- 本地模型能转写并显示分段，按需启用日中翻译；
- 能导入一个 2–3 词的术语表，分别展示原文纠错、译名统一和只高亮；
- 能逐条接受/拒绝建议、手工修改和撤销，原始模型结果保持不变；
- 能导出 SRT/VTT/LRC/TXT，内容与当前保存的编辑结果一致；
- 相关测试通过，README 可指导启动，有实际验收记录及一个 1 分钟录屏。

### 8.2 完善版（V1）

在最小可用版基础上，根据日常使用中的问题逐步补充：

- Phase 6 任务队列/持久化；
- Phase 4 的正则/模糊匹配等增强；
- Phase 5 自动保存草稿；
- Phase 8 回归测试、日语专名样本记录 + benchmark；
- Phase 9 打包 + README + demo。

文本输入、`mask` 及中文法律文本合成数据演示属于 `[STRETCH]`，可在真实需求出现或有余力时再做，不纳入 MVP/V1 完成判定。

---

## 9. 测试矩阵

| 模块 | 测试类型 | 最小用例 | 验收标准 |
|---|---|---|---|
| audio/decode | 单元 | 1 秒 44.1k 双声道 → 16k mono | 采样率 16000、单声道、float32 |
| audio/vad | 单元 | 静音 + 正弦波 | 语音段数量/边界合理 |
| audio/chunks | 单元 | 35s 语音 | 切为 ≤30s 块，不丢音频 |
| asr/whisper | 集成 | 10s demo 音频 | 返回非空 Segment、时间合法 |
| glossary/normalizer | 单元 | 全角/半角/大小写/假名 | 归一化后匹配一致 |
| glossary/matcher | 单元 | 重叠词条 | 最长匹配 + priority 正确 |
| glossary/replacer | 单元 | correct/translate/keep；原文与译文分别处理 | 文本/hits 正确、预览不修改原始输出 |
| glossary/mask（可选） | 单元 | 仅在实现 STRETCH 后使用合成数据 | 已实现的掩码规则符合预期，不据此声称通用实体识别 |
| editor/export | 集成/手工 | 接受、拒绝、手改、撤销后保存并导出 | 导出与当前编辑结果一致，原始输出不变 |
| export | 单元 | 2 段字幕 | SRT/VTT/LRC/TXT 格式正确 |
| api | 单元 | mock job | 状态流转正确 |
| electron | 烟雾 | 启动 + health | 窗口可见、sidecar ready |

---

## 10. Definition of Done

一个 Phase/项目完成必须同时满足：

以下完成标准只针对当前阶段必做范围；标为 `[V1]` / `[STRETCH]` 的项按对应阶段验收，可选迁移演示不作为完成前提。

- [ ] 代码可运行，错误路径有中文提示；
- [ ] 相关测试通过（`pytest -q`；前端至少手动 smoke）；
- [ ] 仓库基础检查及受影响模块的静态/构建检查通过，依赖变更同步锁文件；尚未存在的模块明确标记不适用；
- [ ] 关键入口有日志，但日志不含完整音频/文本内容；
- [ ] `STATUS.md` 已更新；
- [ ] 有目的清晰的 commit，已检查暂存差异，不包含无关修改；
- [ ] README/文档同步；
- [ ] 没有提交模型权重、个人音频、真实敏感数据；
- [ ] demo 能用 30 秒素材在 2 分钟内跑完。

---

## 11. AI 协作提示模板

### 11.1 实现一个 Phase

```text
请阅读 AGENT.md 的 Phase N（N=...）。
只实现这个 Phase 的未完成项，不要动其他 Phase。
先检查现有代码和 git status；完成后运行验收命令，更新 STATUS.md，并提交 commit。
如有不确定，先列出不超过 3 个问题，不要自行猜测数据/模型路径。
```

### 11.2 修 bug

```text
请复现这个问题：
...
先给出根因假设（最多 3 个），再读相关代码验证。
只改最小范围；补一个回归测试；运行 pytest 和对应验收命令。
```

### 11.3 代码审查

```text
请以 AGENT.md 的 Phase 验收标准为基准，审查当前 diff。
输出：阻塞问题 / 建议 / 测试缺口，按严重程度排序。
不要直接重写所有代码，先给具体文件:行号建议。
```

---

## 12. 项目说明、简历与面试映射（按实际完成范围填写）

### 12.1 简历 bullet 模板

以下均为完成后可选用的表述，按实际功能、验证记录及本人/AI 分工删改，不把计划写成已完成成果，也不默认使用“独立开发”。

- 基于个人日语音频处理需求，开发本地优先的转录/翻译工作台：Electron + React + Python sidecar + faster-whisper/CTranslate2，支持音频输入、VAD 分段、字幕复核与导出（按实际完成的输入方式和格式填写）；
- 针对专名误识别及译名不一致问题，实现可配置词表、别名/变体匹配、最长匹配和优先级，分别处理日语原文纠错与中文译名统一，支持替换预览、人工确认、手工修改及撤销；已完成正则规则时再补充该功能；
- 基于人工核对的日语样本记录专名替换效果、误替换与遗漏，使用 pytest 验证音频、词表、替换和导出模块；仅在实际测量后填写准确率、校对时间等指标；
- 将本地模型封装为 sidecar，完成实际设备/计算类型下的推理与打包验证；CPU/GPU、量化方式及 RTF、冷启动、显存 benchmark 只填写已验证或测量的部分。

### 12.2 可选的迁移说明

可在项目说明或面试中简要补充：

> 词表与规则模块将匹配、替换策略和人工确认分开，相关机制可复用于其他文本处理任务。中文法律文本脱敏是可能的扩展方向，但具体语言规则、实体覆盖及误漏报效果需要单独验证。

未实现 `mask` 时只讨论设计可能；实际完成合成数据演示后，才说明演示范围与结果。迁移说明不作为简历主体，不声称已具有法律脱敏或合规经验。

### 12.3 面试可讲的取舍

- 日常处理日语音频时遇到了什么具体问题，为什么先用词表解决；
- 日语无空格，人名/地名如何靠词表 + 最长匹配；
- 原文纠错与译名统一为何分别处理，哪些误识别无法靠词表可靠恢复；
- 哪些稳定模式适合正则，哪些专名依赖词表和上下文确认；
- 如何处理重叠词条、大小写/假名变体；
- 如何保留模型原始结果，确认、撤销并保证导出与编辑结果一致；
- 如何评测日语实际样本（正确替换、误替换、遗漏；CER/校对时间仅讲实际测过的）；
- 为什么本地部署、如何避免显存 OOM；
- 本人和 AI 分别完成了什么，实际发现并解决过哪个问题；
- 如被问及迁移，说明哪些匹配/替换机制可复用，以及中文法律脱敏仍需单独验证的部分。

---

## 13. 当前工作区参考

- 可参考的现有实现：
  - `<旧项目父目录>\Faster-Whisper-TransWithAI-ChickenRice\src\faster_whisper_transwithai_chickenrice\infer.py`：VAD、分段、字幕后处理、SubWriter；
  - `<旧项目父目录>\Faster-Whisper-TransWithAI-ChickenRice\src\faster_whisper_transwithai_chickenrice\vad_manager.py`：ONNX VAD 封装；
  - `<旧项目父目录>\faster_whisper_transwithai\models\`：本地模型资产（不要复制进 Git）。
- 新项目不要直接 import 旧项目包；可以复制算法思路，保持新项目独立可维护。
- 模型路径通过 `models/manifest.json` 配置，不写死绝对路径。

---

*本文件是项目执行基线；任何范围变更先更新本文件，再改代码。*
