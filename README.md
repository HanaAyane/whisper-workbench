# JP Voice Workbench

基于个人日常使用需求开发的本地日语音频工作台：日语转录、日中翻译、专名纠错、译名统一与字幕复核。计划使用 Electron、React、TypeScript 和 Python 本地服务接入 faster-whisper/CTranslate2。

## 当前状态

项目处于工程初始化阶段，尚无可启动的桌面应用或 ASR 服务。已完成范围和验证结果见 [STATUS.md](STATUS.md)，产品需求与分阶段验收以 [AGENT.md](AGENT.md) 为准。

中文法律文本脱敏属于可讨论的技术迁移方向，可选演示不影响日语工作台交付。

## 仓库入口

- [AGENT.md](AGENT.md)：需求、架构、接口和阶段验收。
- [CONTRIBUTING.md](CONTRIBUTING.md)：Git、环境、提交与开发检查约定。
- [STATUS.md](STATUS.md)：实际进展、验证结果和未完成项。
- `scripts/check_repository.py`：不依赖第三方包的仓库基础检查。

## 当前可运行的检查

在项目根目录执行：

```powershell
git status --short
python scripts/check_repository.py
```

检查需要 Git 与 Python 3.10+。它只验证工程和提交基础，不代表已经运行模型、通过应用测试或完成打包。

## 开发环境

前端计划使用 Node.js 20+ 与 pnpm；Python 优先 3.10，并在项目 `.venv` 内安装依赖。正式初始化业务模块时，记录实际兼容版本并提交相应依赖清单和锁文件。

当前机器的工具核对结果见 STATUS。桌面启动、后端安装、模型准备和打包命令将在对应模块实现并实际验证后补充。

## 本地数据

模型放在本地 `models/` 或外部模型目录，用户词表、临时音频等本地数据放在被忽略的 `data/`。本地字幕/导出放在被忽略的 `outputs/` 或 `exports/`，不把私人文本复制到源码或文档中。

Git 只记录源码、测试、文档、依赖和无敏感信息的配置示例。可共享的合成文本/规则放在 `tests/fixtures/` 或 `examples/`；测试音频按需生成，不提交私人媒体和模型权重。
