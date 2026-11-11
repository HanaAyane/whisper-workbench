# 术语表导入和匹配预览

用户导入一份本地 JSON 词表，输入一段字幕，看到命中高亮和替换预览。词表文件留在本次运行的词表目录里。

## Sub-features

- `glossary-open` 从主导航打开术语表。
- `glossary-import` 用新的词表 ID 导入 `examples/glossary.demo.json`。
- `glossary-preview` 对日语原文做匹配预览。
- `glossary-stored` 用词表目录里的 JSON 再确认一次保存结果。

## How to get to it (user POV)

- 点击主导航里的「术语表」。

## Driving it with verify-desktop

Preconditions:

- doctor 已通过，界面显示 `本地服务就绪`。
- 本次词表目录里没有 `verify-preview.json`。
- 不需要可用的 ASR 模型。

- **打开术语表。** 点击「术语表」。运行 `node .cursor/skills/verify-desktop/control.mjs click --role button --name 术语表`。标题成为 `术语表`。运行 `node .cursor/skills/verify-desktop/control.mjs shot --path glossary-preview/open.png`。
- **填写词表 ID。** 在「词表 ID」输入 `verify-preview`。运行 `node .cursor/skills/verify-desktop/control.mjs fill --label "词表 ID" --value verify-preview`。
- **导入示例词表。** 选择 `examples/glossary.demo.json`。运行 `node .cursor/skills/verify-desktop/control.mjs files --label 导入词表文件 --path examples/glossary.demo.json`。状态里出现 `已导入 3 条词条`。运行 `node .cursor/skills/verify-desktop/control.mjs wait --text "已导入 3 条词条"`，再运行 `node .cursor/skills/verify-desktop/control.mjs shot --path glossary-preview/imported.png`。
- **输入待检查文本。** 在「待检查文本」输入 `🎙田中さんと渋谷で会いました`。运行 `node .cursor/skills/verify-desktop/control.mjs fill --label 待检查文本 --value "🎙田中さんと渋谷で会いました"`。
- **预览匹配。** 点击「预览匹配」。运行 `node .cursor/skills/verify-desktop/control.mjs click --role button --name 预览匹配`。结果区出现 `替换预览`。运行 `node .cursor/skills/verify-desktop/control.mjs wait --text 替换预览`。
- **确认界面和文件。** 运行 `node .cursor/skills/verify-desktop/control.mjs assert-glossary --id verify-preview`。高亮文本是 `田中`，预览含 `田中太郎`，并且 `verify-preview.json` 里有同样的替换。运行 `node .cursor/skills/verify-desktop/control.mjs shot --path glossary-preview/preview.png` 和 `node .cursor/skills/verify-desktop/control.mjs aria --path glossary-preview/preview.aria.txt`。

## Gotchas

- 词表 ID 留空时，导入会使用文件名 `glossary.demo`。断言必须对着实际填写的 `verify-preview`。
- 同一个 ID 再导入会弹出覆盖确认。helper 会关掉这个对话框并让命令失败。换一个新的 launch，不要把覆盖当成成功。
- 词条列表里本来就有「田中太郎」。只看见这四个字不能证明预览已经跑过。要看到 `替换预览`，并且 `assert-glossary` 通过。
- `渋谷` 的策略是译文统一。在「日语原文」预览里它不会被换成「涩谷」。
- 状态文案是 `已导入 3 条词条。`。`wait` 不要加 `--exact`。
