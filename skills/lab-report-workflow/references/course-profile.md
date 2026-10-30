# 课程格式配置

封面和字体以当前讲义、模板或用户确认的上一份报告为依据，不预填他人身份或固定实验日期。需要个人封面设置时，可读取技能本地的references/course-profile.local.md；该文件可选，且不进入公开仓库或共享源包。

## 封面字段

模板支持报告标题、实验题目、院系、年级、学号、姓名、实验日期和校徽。分别通过ReportTitle、ExperimentTitle、Department、Grade、StudentID、StudentName、ExperimentDate和ReportLogo设置。

复制[LaTeX模板](../assets/report-template.tex)为项目main.tex，在同目录config.tex中用renewcommand填写已知字段。ReportLogo为空时不放校徽；有素材时使用项目相对路径。长实验题目分行，日期取实际实验记录，不用今天的日期代替。

## 模板与课程差异

模板提供A4、12pt、宋体正文、黑体标题、Times New Roman西文、左右2.5cm和1.35倍行距，作为可修改的起点。使用XeLaTeX，Windows可采用MiKTeX；其他环境需配置已安装的等效字体。

光电和微波系列遵循各自规范及当前指导书，不把一份封面、某次图数、页数或方向映射当成所有课程默认值。其他课程有现成模板时按其要求修改，不自动套用本系列结构和个人信息。
