# 录音就绪

用户开始录音再停止，界面显示录音已经可以提交。这一步不创建转录任务。

## Sub-features

- `record-start` 从工作台的麦克风按钮开始录音。
- `record-stop` 停止后显示 `录音已就绪`。

## How to get to it (user POV)

- 打开应用后留在「工作台」。
- 点击麦克风按钮。录音中同一个按钮的名称变为「停止录音」。
- 再次点击，等待「录音已就绪」。

## Driving it with verify-desktop

Preconditions:

- doctor 已通过。
- launch 前设置 `VERIFY_DESKTOP_FAKE_MIC=1`。helper 会加上 Chromium 的 `--use-fake-device-for-media-stream`。
- 不点击「开始处理」。

- **确认在工作台。** 运行 `node .cursor/skills/verify-desktop/control.mjs click --role button --name 工作台`。
- **开始录音。** 运行 `node .cursor/skills/verify-desktop/control.mjs click --role button --name 开始录音`。按钮变为「停止录音」。运行 `node .cursor/skills/verify-desktop/control.mjs wait --role button --name 停止录音 --exact`，再运行 `node .cursor/skills/verify-desktop/control.mjs shot --path record-ready/recording.png`。
- **停止录音。** 运行 `node .cursor/skills/verify-desktop/control.mjs click --role button --name 停止录音`。运行 `node .cursor/skills/verify-desktop/control.mjs wait --text 录音已就绪 --exact`，再运行 `node .cursor/skills/verify-desktop/control.mjs shot --path record-ready/ready.png` 和 `node .cursor/skills/verify-desktop/control.mjs aria --path record-ready/ready.aria.txt`。

## Gotchas

- 没有 `VERIFY_DESKTOP_FAKE_MIC=1` 时，无麦克风的环境会停在权限或设备错误。这不是录音功能通过。
- 用户本机有麦克风时不要设置 `VERIFY_DESKTOP_FAKE_MIC`。那是无设备环境的替代步骤。
- 「开始处理」在没有可用模型时是禁用的。不要为了让它可点而去写任务或改模型状态。
- `JP_WORKBENCH_SMOKE=1` 会隐藏窗口。本技能的 launch 不会设置它。
