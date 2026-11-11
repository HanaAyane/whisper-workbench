# 字幕导出

用户对一条已经成功的任务选择字幕格式和覆盖策略，再把已保存字幕写到自己选定的路径。

## Sub-features

- `export-format` 在 SRT、VTT、LRC、TXT 之间选择。
- `export-protect` 默认保留已有同名文件。
- `export-replace` 在用户改成允许覆盖后替换同名文件。
- `export-bytes` 写出的文件是 UTF-8，内容和已保存字幕一致。

## How to get to it (user POV)

- 在工作台选中一条状态为已完成的任务。
- 在导出条选择「字幕格式」和「覆盖策略」。
- 点击「选择位置并保存」，在系统保存对话框里确认路径。

## Driving it with verify-desktop

Preconditions:

- doctor 报告 `modelsOk: true`，或者已经有一条不依赖新转录的成功任务。
- 当前选中任务的状态是成功。按钮「选择位置并保存」可点。
- 没有成功任务时，这条功能失败。原因写进结果，不要改成调用 `window.api.createJob`。

- **选择格式。** 运行 `node .cursor/skills/verify-desktop/control.mjs select --label 字幕格式 --value srt`。界面上的格式是 `SRT`。
- **字节和覆盖策略。** 运行 `pnpm --dir apps/desktop build`，然后运行 `pnpm --dir apps/desktop smoke`。脚本用受控保存路径检查四种格式的 UTF-8 内容，以及默认保留同名文件。通过日志含有「四格式 UTF-8 导出和覆盖策略」。
- 没有可用模型时不要运行 smoke 来充当导出证明。smoke 里的导出发生在转录任务成功之后。模型缺失时任务不会成功，导出也就没有被验证。

## Gotchas

- 「选择位置并保存」打开的是操作系统对话框。`control.mjs` 不拦截 `dialog.showSaveDialog`。需要文件字节时跑 `smoke.mjs`，不要在 helper 里再写一套对话框替身。
- 纯静音或合成正弦波在真实模型上可能得到空字幕。空文件只能证明写盘，不能证明日语转写。
- 批量自动导出不是这一条。它在 [batch-import.md](batch-import.md)。
