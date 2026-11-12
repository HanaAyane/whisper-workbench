---
name: verify-desktop
description: "Drive Whisper工作台 (apps/desktop Electron window) the way a user does. Use to launch an isolated profile, check the local sidecar, exercise a mapped feature such as glossary preview, model status, recording, export, or batch import, and keep screenshots. Reach for it when a desktop change needs proof, not a unit-test proxy."
---

# Verify Whisper工作台

Whisper工作台的用户只接触 Electron 窗口。Sidecar 和 HTTP 是窗口后面的本地服务，不是另一套用户界面。本技能启动一个隔离的桌面实例，按用户路径操作，并留下证据。功能步骤在 [features/README.md](features/README.md)。先读索引，再打开对应功能文件。

已有的整包冒烟不要重写。它们是 `pnpm --dir apps/desktop smoke`、`node apps/desktop/scripts/smoke-batch.mjs`、`node apps/desktop/scripts/smoke-package.mjs`。本技能的 helper 负责单次隔离启动和按功能取证。导出字节和批量落盘仍走前两个冒烟脚本。

## Launch

在仓库根目录执行。Node 须满足 `apps/desktop/package.json` 的 `>=24`，pnpm 为 11.21.0，仓库根有 Python 3.10 的 `.venv`。

准备命令只在缺件时跑。

```bash
pnpm --dir apps/desktop install --frozen-lockfile
pnpm --dir apps/desktop build
```

`.venv` 按 README 用 Python 3.10 创建，并安装 `backend/requirements.txt`。Sidecar 默认执行 `.venv/bin/python`（Windows 是 `.venv/Scripts/python.exe`）。

启动一个空用户目录。就绪的标志是窗口标题 `Whisper工作台`，并且状态文本为 `本地服务就绪`。健康检查能通过而界面仍停在「正在连接」时，不要开始操作。

```bash
node .cursor/skills/verify-desktop/control.mjs launch --evidence /tmp/verify-desktop-evidence
```

这次启动会：

- 把用户数据放到 `/tmp/verify-desktop/runs/<id>/user-data`，词表放到同一次运行的 `glossary/`。
- 设置 `JP_WORKBENCH_VITE=0`，加载 `apps/desktop/dist`。
- 不设置 `JP_WORKBENCH_SMOKE`。该变量会把窗口设为隐藏，截图和录屏都看不到界面。
- 删掉环境里的 `ELECTRON_RUN_AS_NODE`。留下它时 Electron 会以 Node 模式启动。
- 从空数据库启动。不复制用户自己的 `jp-voice-workbench` 配置。

`launch` 发现已有未 cleanup 的实例时直接失败。不要附到用户正在用的窗口上。不同的 `JP_WORKBENCH_USER_DATA` 可以并存，因为主进程先改 `userData` 再要单实例锁。

只有录音功能才额外设置 `VERIFY_DESKTOP_FAKE_MIC=1`。只有 Chromium 拒绝沙箱时才设置 `VERIFY_DESKTOP_NO_SANDBOX=1`。用户本机的正常启动不做这两步。

## Doctor

实例看起来不对时，先跑 doctor，再决定要不要操作。

```bash
node .cursor/skills/verify-desktop/control.mjs doctor
```

通过条件是 Electron 进程仍是本次 launch 的 pid，标题为 `Whisper工作台`，界面有 `本地服务就绪`，`window.api.health()` 返回 `status=ok` 且 `version` 与 `apps/desktop/package.json` 一致，渲染进程没有 `token` 也没有 `require`。报告写入 `--evidence/doctor.json`。`modelsOk: false` 仍可操作术语表、设置页和录音就绪。它不能用来证明转录、导出或批量落盘。

## Drive

用 helper 的角色和标签操作，不要用坐标。标签来自界面，和 `apps/desktop/scripts/smoke.mjs` 相同。

- 主导航是按钮 `新建`、`工作台`、`术语表`、`设置`。`设置` 钉在栏底。录音、拖入文件和批量提交在 `新建`。
- 术语表输入的标签是 `词表 ID`、`导入词表文件`、`待检查文本`。预览按钮是 `预览匹配`。
- 录音按钮是 `开始录音` 和 `停止录音`。就绪文本是 `录音已就绪`。
- 设置页标题是 `工作台设置`。
- 导出控件的标签是 `字幕格式`、`覆盖策略`，按钮是 `选择位置并保存`。
- 应用根节点是 `.app-shell`。

`click` 默认精确匹配 accessible name。`wait --text` 默认子串匹配，加 `--exact` 才整句匹配。文件对话框是操作系统窗口。helper 不替换 `dialog.showSaveDialog`。导入词表走界面上的 `导入词表文件`，那是用户点击「导入 CSV / JSON」时使用的文件控件。

每个功能的命令在对应功能文件里。一次证明只把一个功能从入口做到可观察的结束状态。

## Evidence

证据只写入 launch 的 `--evidence`。默认是 `/tmp/verify-desktop-evidence`。

每次证明至少留下：

- 操作前和结果出现后的 PNG。窗口里要能看到 `Whisper工作台`。
- `.app-shell` 的 ARIA 快照。
- 改变了磁盘的功能，还要有第二份只读结果。术语表是 `--evidence/glossary-preview/stored.json`，来源是本次运行的词表目录，不是界面上的一句提示。
- 需要录像时，对可见窗口另录屏幕。不要给 Playwright 的 Electron `launch` 传 `recordVideo`。在这套 Electron 上，这个参数会让启动停住。

不要只截最终画面。不要调用 `window.api` 去制造用户没有做的保存、导入或任务。DeepSeek 不在这条路径上。没有本地 CT2 模型时，不要把转录、翻译、字幕导出或批量自动导出记成已验证。

## Cleanup

```bash
node .cursor/skills/verify-desktop/control.mjs cleanup
```

cleanup 只关闭本次 launch 的 Electron pid，并删除本次的 `user-data` 和 `glossary`。它不按进程名杀 Electron。它不删除 `--evidence`。结束后 `--evidence/KEEP` 必须还在。失败的一轮也要 cleanup，避免占着用户目录和端口。

## Helpers

[control.mjs](control.mjs) 可执行。在仓库根目录调用。

```bash
node .cursor/skills/verify-desktop/control.mjs launch --evidence /tmp/verify-desktop-evidence
node .cursor/skills/verify-desktop/control.mjs doctor
node .cursor/skills/verify-desktop/control.mjs click --role button --name 术语表
node .cursor/skills/verify-desktop/control.mjs fill --label 词表 ID --value verify-preview
node .cursor/skills/verify-desktop/control.mjs files --label 导入词表文件 --path examples/glossary.demo.json
node .cursor/skills/verify-desktop/control.mjs wait --text 已导入 3 条词条
node .cursor/skills/verify-desktop/control.mjs shot --path glossary-preview/open.png
node .cursor/skills/verify-desktop/control.mjs aria --path glossary-preview/open.aria.txt
node .cursor/skills/verify-desktop/control.mjs select --label 字幕格式 --value srt
node .cursor/skills/verify-desktop/control.mjs assert-glossary --id verify-preview
node .cursor/skills/verify-desktop/control.mjs assert-models
node .cursor/skills/verify-desktop/control.mjs list
node .cursor/skills/verify-desktop/control.mjs cleanup
```

`shot` 和 `aria` 的路径必须落在 `--evidence` 里面。

界面变化后用 `/maintain-verification-skill` 核对功能图。不要靠记忆改选择器。
