# 批量导入和自动导出

用户一次放入多个媒体，看到逐项校验，选择一个输出目录后按列表顺序转录，并在成功后把字幕写进该目录。同名文件保留，新文件追加序号。

## Sub-features

- `batch-list` 一次导入两份同名有效媒体和一份损坏文件，并显示各自的校验结果。
- `batch-order` 有效文件按列表顺序进入现有队列。
- `batch-protect` 已存在的同名字幕保持原样，新文件使用 `clip (1)` 这类序号名。
- `batch-format` 换一种字幕格式后再跑一批，扩展名和格式一致。

## How to get to it (user POV)

- 在工作台点击「拖入多个文件，或点击多选」，或者把多个文件拖进该区域。
- 选择可用的转录模型、批量输出格式和字幕输出目录。
- 点击「开始批量处理」。
- 成功项显示已保存路径。损坏项显示具体文件和原因，其他项继续。

## Driving it with verify-desktop

Preconditions:

- 已执行 `pnpm --dir apps/desktop build`。
- 本机有 ffmpeg。
- doctor 同类条件下 `modelsOk: true`。模型文件不齐时不要把失败任务改记为通过。

- **跑仓库已有的批量冒烟。** 在仓库根目录运行 `node apps/desktop/scripts/smoke-batch.mjs`。它启动隔离的 Electron 配置，导入两份同名有效 WAV 和一份损坏 WAV，并检查 `clip.srt` 原样保留、写出 `clip (1).srt` 与 `clip (2).srt`，再切换到 VTT。
- 通过时日志含有「成功 2 / 失败 1」。损坏文件不产生字幕。

## Gotchas

- 没有可用 ASR 模型时，两份有效媒体都会转录失败。这是失败，不是序号规则已验证。
- `smoke-batch.mjs` 会替系统文件对话框返回它刚生成的路径。这是仓库现有冒烟的做法，用来检查队列和落盘。它不代替用户在真实对话框里点选目录。
- 不要为了让批量通过而去改断言或改用内部接口创建任务。
