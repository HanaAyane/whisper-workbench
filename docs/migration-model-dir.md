# 从 v0.1.0 迁移模型到 `model/` 目录

`v0.1.0` 通过 `manifest.json` 指定模型路径，模型可以放在用户数据目录，也可以放在任意外部目录。新的 Windows 安装版改为自动扫描 `<安装目录>/model/`，不再需要手写清单。任务历史、词表和已保存字幕仍在原来的用户数据目录 `%APPDATA%\jp-voice-workbench`，升级不会丢失。

## 1. 找到旧模型文件位置

打开旧的 `v0.1.0` 应用「设置」页，查看「模型清单」路径；或直接检查：

- `%APPDATA%\jp-voice-workbench\models\manifest.json`（首启自动生成的默认清单），其中每个模型的 `path` 指向实际模型目录；相对路径以用户数据目录解析，绝对路径直接使用。
- 若曾在设置中「选择目录」，选择记录保存在 `%APPDATA%\jp-voice-workbench\model-directory.json`，值即外部清单目录。

## 2. 复制到安装目录的 `model/`

假设新版本安装在 `D:\Apps\Whisper工作台`：

1. 为新版本创建模型子目录，例如 `D:\Apps\Whisper工作台\model\whisper-ja-1.5B\`。
2. 把旧清单里该模型目录下的 `model.bin`、`config.json`、`tokenizer.json`、`preprocessor_config.json`、`vocabulary.json` 复制进去。
3. 把 VAD 文件 `whisper_vad.onnx`、`whisper_vad_metadata.json` 复制到 `D:\Apps\Whisper工作台\model\`（根目录，不在子目录里）。
4. 模型目录名会成为模型 id，可以用 `whisper-ja-1.5B` 或其它便于识别的名字。

## 3. 启动并重新扫描

启动新版本，在「设置」页确认「模型目录」正确、模型显示为「可用」，必要时点「重新扫描」。随后即可在「新建」中选择该模型。旧任务历史和已保存字幕仍在原用户数据目录中。

## 注意

- 只复制模型文件，不要移动或删除旧版本目录，先确认新版本可正常转录再考虑清理。
- 模型权重由用户自行准备，工作台不会自动下载。
- 若安装目录不可写或 `model/` 无法访问，设置页会给出权限提示；请把应用安装到当前用户可写的位置。
