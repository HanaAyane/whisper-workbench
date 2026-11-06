# 开发与版本控制

## 开始一项工作

先阅读 `AGENT.md` 和 `STATUS.md`，只处理当前阶段。查看已有改动，保留并说明用户尚未提交的内容。

```powershell
git status --short
git log -5 --oneline
git switch -c feat/short-topic
```

分支名按目的使用 `feat/`、`fix/`、`docs/` 或 `chore/`。仓库使用 `main` 作为稳定分支；首次工程初始化可以直接建立基线提交。后续合入前完成对应验收，工作区有无关改动时不直接切换或覆盖它们。

## 环境和依赖

- Python 使用项目内 `.venv`。优先 Python 3.10，偏离时记录原因与兼容性结果，不把系统默认 Python 当作已经验证过的项目环境。
- 前端统一 pnpm；创建项目时固定实际使用的包管理器版本并提交 `pnpm-lock.yaml`，之后使用冻结锁文件的安装方式。
- 创建后端时提交依赖声明与可复现的锁定清单。新增依赖说明用途，避免提交其他环境导出的无关包。
- 遵守 `.editorconfig` 和 `.gitattributes`；Python 用 4 空格，TS/JSON/YAML 用 2 空格，文本默认 LF。
- 当前未初始化前后端依赖；对应安装和启动命令在实际实现后写入 README。

## 检查与提交

先运行仓库基础检查和本次修改涉及的模块检查，再用明确路径暂存内容。以下路径为示例，提交时替换为本次实际文件：

```powershell
git diff
python scripts/check_repository.py
git add -- AGENT.md README.md STATUS.md
git diff --cached --stat
git diff --cached
python scripts/check_repository.py
git commit -m "docs: clarify transcription workflow"
git status --short
```

提交前缀使用 `feat`、`fix`、`docs`、`test`、`chore` 等；一个提交解决一件可说明的事。不要用笼统的“全部完成”代替真实变更说明，也不要把 AI 协作生成的工作默认描述为个人独立完成。

新增业务代码时同步建立对应检查：

| 阶段 | 提交前的检查 |
| --- | --- |
| 当前工程基础 | 仓库基础检查、文档与暂存差异人工核对 |
| Python 后端引入后 | Python 格式/静态检查、相关 pytest、接口的正常及错误路径 |
| Electron/React 引入后 | lint、TypeScript 严格类型检查、相关测试、build；窗口和 IPC 按阶段烟雾验收 |
| 模型接入后 | 合成/可说明来源的样本、模型与设备记录；mock 和真实模型结果分别标注 |
| 打包阶段 | 构建日志、产物启动、首次模型缺失提示；未验收的平台明确列出 |

引入业务代码时配置真正执行相应检查的 CI。常规 CI 不要求私人音频、模型权重或 GPU；真实模型与安装包验收另行记录。尚未实现的检查不写成已通过。

## 数据与历史

模型、用户词表、音视频、字幕结果、数据库、密钥、日志和缓存不提交。`.gitignore` 是默认保护，不能替代查看差异；不要用 `git add -f` 绕过它来提交个人材料。

可用以下命令检查某个路径为何被忽略，命令不需要创建这个文件：

```powershell
git check-ignore -v -- models/model.bin data/glossary/private.json outputs/session.txt
```

误纳入历史的敏感文件不能靠新增忽略规则解决，应停止提交/推送并先定位影响范围。不要擅自改写历史、强制推送，或使用清理/重置命令覆盖未提交工作。需要撤销已提交的普通变更时优先使用 `git revert`。

远程仓库创建、推送、发布和版本标签在明确需要时单独执行；本地 Git 提交并不代表已备份到远程。

## 进度记录

每个阶段更新 `STATUS.md`：实际完成项、检查命令与结果、未完成项和下一步。功能故障记录输入条件、复现步骤、预期/实际行为和修复验证，不将原始私人音频或未脱敏文本写入日志、公开 issue 或提交说明。
