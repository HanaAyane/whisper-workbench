# 项目状态

更新日期：2026-11-06（Asia/Shanghai）。

## 当前范围

本轮只完成 Phase 0、Phase 1。日语转录、日中翻译、专名纠错、译名统一与字幕复核仍是后续主线；本轮不实现 Phase 2 及以后功能。

## 阶段进展

| Phase | 状态 | 测试/验收 | 备注 |
| --- | --- | --- | --- |
| 0 项目初始化 | 完成 | 基础检查、Ruff、8 个文件校验测试、依赖兼容检查通过；模型检查按实际缺失返回 1 | 独立仓库、文档、忽略规则、Python 3.10 `.venv`、锁定依赖、模型检查脚本均已准备；缺模型明确报告路径，不下载 |
| 1 Python Sidecar | 未开始 | 不适用 | 下一阶段在 Phase 0 提交后开始 |
| 2 音频处理 | 未开始 | 不适用 | 尚无解码、VAD 或切块实现 |
| 3 ASR/翻译 | 未开始 | 不适用 | 未加载模型或转录样本 |
| 4 术语引擎 | 未开始 | 不适用 | 尚无实现 |
| 5 Electron/React | 未开始 | 不适用 | 尚无前端项目 |
| 6 队列/持久化 | 未开始 | 不适用 | 按实际需求推进 |
| 7 编辑/导出/隐私 | 未开始 | 不适用 | 尚无实现 |
| 8 测试/评测 | 未开始 | 不适用 | 尚无业务或真实模型评测 |
| 9 打包交付 | 未开始 | 不适用 | 尚无安装包或跨平台验收 |

## 环境与兼容性

- Git 2.52.0.windows.1；原始基线提交 `8e1f9ea`，稳定分支 `main`，本轮功能分支 `feat/sidecar-foundation`。沿用现有身份，不改全局 Git 配置。
- Node v24.16.0、pnpm 11.21.0；前端未初始化，无前端兼容性或构建通过声明。
- 系统默认 Python 3.12.7（Anaconda）未用于项目依赖。通过 uv 安装 Python 3.10.21 并创建项目 `.venv`，没有修改系统默认版本，无 Python 版本偏离。
- Phase 1 所需的 FastAPI 0.115.12、Pydantic 2.11.5、Uvicorn 0.34.2、HTTPX 0.28.1、pytest 8.3.5、Ruff 0.11.11 已预先安装；全部 23 个直接/传递依赖及哈希锁定在 `backend/requirements.txt`，`uv pip check` 通过。
- ASR/音频/打包依赖将在对应阶段安装；本轮不宣称 faster-whisper/CTranslate2、GPU/CUDA 或模型推理兼容性已验证。

## Phase 0 验收记录

- `.venv/Scripts/python.exe scripts/check_repository.py`：通过；暂存后、提交前再次运行。
- `.venv/Scripts/python.exe scripts/verify_models.py`：退出码 1，逐项报告两个默认 CT2 模型各 5 个文件及 2 个 VAD 文件缺失，均带完整路径；没有下载或复制模型。此命令的验收要求允许明确报告缺失。
- 本地 `models/manifest.json` 由无个人路径的示例创建，已被忽略；旧项目模型目录只读检查，不猜测其模型身份、不改动其文件。
- `.venv/Scripts/python.exe -m ruff check backend scripts`、`ruff format --check backend scripts`：通过。原有仓库脚本仅整理 import/空行以纳入统一检查。
- `TMPDIR=<项目>/data/tmp .venv/Scripts/python.exe -m pytest -q`：8 passed。覆盖文件齐全/缺失、损坏/错误清单、重复 id、错误 type/task、CLI 错误输出；临时空文件只用于文件检查，不代表真实模型测试。
- `uv pip check --python .venv/Scripts/python.exe`：23 个包兼容。安装命令末尾曾尝试 `python -m pip --version`，因 uv 环境默认无 pip 返回 1；依赖安装已成功，后续使用 uv 检查。
- 已建立 Windows/Linux Python 3.10 CI，实际远端运行尚未发生；本地相同检查通过。

## 环境故障与处理

首次 pytest 在测试 setup 阶段遇到系统临时目录权限问题，8 个用例未执行。改用项目内的 `data/tmp` 作为 TMPDIR 后，8 个测试通过。复现命令见 README。

## 遗留与下一步

- Phase 1 待实现；Phase 2 及以后不在本轮范围。
- 模型文件仍缺失；有确认的模型身份/目录后编辑本地 manifest，重新运行校验。本轮不自动下载权重、不运行推理。
- 未创建远程仓库，未推送、发布或打标签。
