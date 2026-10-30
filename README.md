# 实验报告工作流

用于Codex的中文课程实验报告技能，覆盖预习与现场记录表、原始数据与图片对应、报告制作和修订、抄写打印版，以及实验文件夹归档。

规范从光电检测、微波实验的实际任务要求整理，区分通用要求、课程格式和单次实验例外。公开版不包含原始对话、个人身份信息、实验数据、学校校徽或本机绝对路径。

## 安装

将仓库中的 `skills/lab-report-workflow` 整个目录复制到Codex技能目录，使其入口为：

```text
~/.codex/skills/lab-report-workflow/SKILL.md
```

Windows默认技能目录为 `%USERPROFILE%\.codex\skills`。已经安装同名技能时，先备份个人配置，再合并更新。

示例请求：

```text
用 $lab-report-workflow，预习这次实验，并制作实验室用的现场记录表。
用 $lab-report-workflow，先对应数据表和现场照片。
用 $lab-report-workflow，按讲义和确认记录完成实验报告。
用 $lab-report-workflow，修改当前报告，并同步我要求的抄写版。
用 $lab-report-workflow，整理实验7到12的文件夹，保留历史版本。
```

## 环境与辅助脚本

技能说明可独立阅读。辅助脚本使用Python 3.10及以上版本；安装所需库：

```shell
python -m pip install -r requirements.txt
```

以下命令从 `skills/lab-report-workflow` 目录执行，输入与输出路径按实际文件设置：

```shell
python scripts/inventory_lab_sources.py INPUT_DIR --recursive --hashes --out inventory.json
python scripts/extract_docx_records.py SOURCE.docx --out records.json --media-dir media
python scripts/jpeg_display_pdf.py INPUT.jpg OUTPUT.pdf
```

文件清点只读文件与图像头部信息；Word提取工具保留原表文字、嵌套结构与嵌入图片字节，不推断图像对应关系；JPEG工具仅用于显示尺寸异常，将原字节嵌入尺寸明确的PDF容器，并明确拒绝非标准EXIF方向。输出已存在时默认停止。

LaTeX模板使用XeLaTeX，默认字体为宋体、黑体和Times New Roman。Windows可使用MiKTeX；其他环境需配置等效字体。Word、PDF、Excel与科学绘图任务会遵循运行环境中可用的对应技能和工具。

## 规范划分

| 文件 | 用途 |
|---|---|
| [技能入口](skills/lab-report-workflow/SKILL.md) | 任务范围、优先级和数据边界 |
| [数据与记录](skills/lab-report-workflow/references/data-records.md) | 预习、现场公式表、提取与来源对应 |
| [报告与图表](skills/lab-report-workflow/references/report-writing.md) | 正式语言、公式、完整表格和图表信息密度 |
| [光电检测](skills/lab-report-workflow/references/opto-course.md) | 课程偏好及单次更正的适用边界 |
| [微波实验](skills/lab-report-workflow/references/microwave-course.md) | MATLAB、黑白版式、思考题及图片使用 |
| [课程格式](skills/lab-report-workflow/references/course-profile.md) | 封面字段与可选本地个人配置 |
| [渲染交付](skills/lab-report-workflow/references/rendering.md) | PDF、Word、不同抄写用途与源包 |
| [文件归档](skills/lab-report-workflow/references/file-organization.md) | 当前版本、历史稿、路径依赖与完整性 |

课程信息来自用户的讲义、模板和记录。可选的 `course-profile.local.md` 仅存个人环境，已设为Git忽略项。报告、数据、图表和源包应来自同一次修订；归档时校验文件完整性与快捷入口。

## 验证辅助工具

测试只使用临时生成的样例，覆盖空白/0/未能测得、无关系文件Word、嵌套表格、图片字节、EXIF方向、拒绝覆盖和格式别名：

```shell
python -X utf8 -m unittest discover -s tests -v
```
