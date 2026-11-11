# 设置页模型状态

用户在设置页看到本机模型清单或模型目录的检查结果。文件缺失和模型可用是两种不同的结果。

## Sub-features

- `model-open` 从主导航打开设置。
- `model-missing` 在没有可加载模型时显示清单错误、缺件或未就绪。
- `model-ready` 在模型文件齐全时显示可用。

## How to get to it (user POV)

- 点击主导航里的「设置」。
- 工作台在没有可用模型时，提示条里的「检查模型路径」也会打开设置。验证 `model-open` 时走主导航。

## Driving it with verify-desktop

Preconditions:

- doctor 已通过。
- doctor 报告里的 `modelsOk` 决定走 `model-missing` 还是 `model-ready`。
- 开发版读取仓库 `models/manifest.json`。没有这个文件时，界面显示无法读取清单。

- **打开设置。** 点击「设置」。运行 `node .cursor/skills/verify-desktop/control.mjs click --role button --name 设置`。标题成为 `工作台设置`。运行 `node .cursor/skills/verify-desktop/control.mjs wait --role heading --name 工作台设置 --exact`。
- **核对和健康检查一致的状态。** 运行 `node .cursor/skills/verify-desktop/control.mjs assert-models`。`modelsOk` 为 false 时，页面含有 `无法读取模型清单`、`未就绪` 或 `缺少文件`。`modelsOk` 为 true 时，页面含有 `可用`。
- **留证。** 运行 `node .cursor/skills/verify-desktop/control.mjs shot --path model-status/settings.png` 和 `node .cursor/skills/verify-desktop/control.mjs aria --path model-status/settings.aria.txt`。

## Gotchas

- 开发版不是 Windows 安装版。设置页显示「模型清单」，不是安装目录 `model/` 的自动扫描。不要把开发版的清单路径写成安装版发现结果。
- 工作台首页的「未找到可用的日语转录模型」不在设置页上。设置页的证明以 `assert-models` 为准。
- `modelsOk: true` 只说明清单里的文件都在。它不说明转录已经跑过。
