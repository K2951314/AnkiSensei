# AnkiSensei

`AnkiSensei` 是一个把日语句库导出为 Anki APKG 的命令行工具。

仓库本身不再内置句库、音频或导出结果。你通过根目录的 `ankisensei.json` 指定输入文件和输出位置，也可以在命令行里临时覆盖。

## 安装

```powershell
py -3 -m pip install -r requirements.txt
```

## 配置文件

默认配置文件名是 `ankisensei.json`，放在项目根目录。

路径规则：

- 配置文件里的相对路径，按配置文件所在目录解析
- 命令行里的相对路径，按执行命令时的当前目录解析
- 命令行参数优先级高于配置文件

主要配置项：

- `"paths.source"`
- `"paths.apkg_output"`
- `"paths.audio_dir"`
- `"export.deck_name"`
- `"tts.voice"`
- `"tts.concurrency"`
- `"layout.front_sections"`
- `"layout.front_answer_sections"`
- `"layout.reverse_front_sections"`
- `"layout.reverse_back_sections"`

## 输入格式

推荐使用每行一个卡片、Tab 分隔五列（第 5 列可选）：

```text
日语整句<TAB>注音词列表<TAB>音频文件名<TAB>中文<TAB>TTS_TEXT
```

示例：

```text
お忙しいところ恐れ入りますが、こちらの図面に承認印をお願いできますか。	忙（いそが）|恐（おそ）|図面（ずめん）|承認印（しょうにんいん）|願（ねが）	approval.mp3	百忙之中打扰您很抱歉，能请您在这个图纸上盖个批准印章吗？	おいそがしいところおそれいりますが、こちらのずめんにしょうにんいんをおねがいできますか。
```

说明：

- 第 1 列：正面上方显示的日语整句
- 第 2 列：正面中间显示的注音词列表，支持 `|`、`;`、`；`，也兼容空格分隔的注音词
- 第 3 列：音频文件名，支持 `file.mp3` 或 `[sound:file.mp3]`
- 第 4 列：中文释义
- 第 5 列（可选）：仅用于 TTS 语音生成，不参与卡片字段显示；有值时优先于第 1 列
- 卡片内容仍只使用前 4 列；当第 5 列为空时，程序会参考第 2 列注音词列表去修正第 1 列读音后再做 TTS

旧格式依然兼容：

```text
JP_FURIGANA[sound:FILE.mp3] ZH_MEANING
```

## 常用命令

只校验源文件：

```powershell
py -3 run.py export-apkg --check-only
```

按配置导出 APKG：

```powershell
py -3 run.py export-apkg
```

强制重生全部音频：

```powershell
py -3 run.py export-apkg --force-audio
```

临时覆盖配置中的路径：

```powershell
py -3 run.py export-apkg `
  --source C:\anki\sentences.txt `
  --output C:\anki\out\ankisensei.apkg `
  --audio-dir C:\anki\out\audio
```

使用其他配置文件：

```powershell
py -3 run.py export-apkg --config C:\anki\ankisensei.json
```

## 排版配置

排版不需要改代码，可以通过 `"layout"` 调整：

- 正向卡正面区块顺序：`front_sections`
- 正向卡背面区块顺序：`front_answer_sections`
- 反向卡正面区块顺序：`reverse_front_sections`
- 反向卡背面区块顺序：`reverse_back_sections`
- 字体、字号、颜色、边距、行高

可用区块名只有 4 个：

- `sentence`
- `notes`
- `audio`
- `translation`

默认效果是：

- 正向卡正面：`sentence -> notes -> audio`
- 正向卡背面：`translation`
- 反向卡正面：`translation`
- 反向卡背面：`sentence -> notes -> audio`

## 产物说明

运行时会在你配置的音频目录里生成：

- `.mp3`
- `.ankisensei_audio_manifest.json`

运行时也会在你配置的 APKG 位置生成：

- `.apkg`

这些产物默认不应提交到仓库。
