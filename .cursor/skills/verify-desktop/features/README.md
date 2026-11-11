# Whisper工作台验证图

先读本索引，再按功能文件操作。用户只通过 Electron 窗口使用 Whisper工作台。

## Baseline preconditions

- 在仓库根目录执行 `node .cursor/skills/verify-desktop/control.mjs launch --evidence /tmp/verify-desktop-evidence`。
- 用户数据和词表在 `/tmp/verify-desktop/runs/<id>/`，每次 launch 都是空目录。
- `node .cursor/skills/verify-desktop/control.mjs doctor` 必须报告标题 `Whisper工作台`、版本 `0.1.0`，以及本次 `userData`。
- 只操作本次 launch 的实例。
- 生产构建要先存在。命令是 `pnpm --dir apps/desktop build`。

## Driving conventions

- 每个功能从这次 launch 的初始界面开始，除非该功能自己写了前置条件。
- 用角色和 accessible name，不用坐标。
- 命令原文执行，保留引号和参数。
- 点击、填写、截图和 ARIA 都走 `control.mjs`。
- 导出文件内容和批量落盘走仓库已有的 `smoke.mjs` 与 `smoke-batch.mjs`。
- cleanup 可以删本次用户目录，不能删 `--evidence`。

## Proof and skip reporting

- 同时留下动作和动作之后的状态。
- 界面证据包含 ARIA 快照和一张能看见 `Whisper工作台` 的截图。
- 会写盘的功能再读一次写出的文件。
- 证据里记下功能 ID 和入口。
- 前置条件不满足就报告失败和原因。不要改用别的入口然后称该功能已验证。

## Feature entry contract

每个功能文件以一句用户可见行为开头，然后按这个顺序写四个二级标题。

1. `Sub-features`
2. `How to get to it (user POV)`
3. `Driving it with verify-desktop`
4. `Gotchas`

## Features

- [术语表导入和匹配预览](glossary-preview.md) 不依赖 Whisper 模型。
- [设置页模型状态](model-status.md) 展示清单缺失、文件缺失或模型可用。
- [录音就绪](record-ready.md) 只证明麦克风录音准备好，不提交转录。
- [字幕导出](export-subtitles.md) 需要一条已成功的任务。没有可用模型时这条失败。
- [批量导入和自动导出](batch-import.md) 使用已有的 `smoke-batch.mjs`。没有可用模型时这条失败。
