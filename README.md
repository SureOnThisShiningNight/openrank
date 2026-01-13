# 队内成员情况：

队名：艾雅队

队长：于雅

队员：邓艾迪

分别主要负责 *数据爬取与网页代码*、*数据分析与文稿撰写*



# 学术开源项目分析项目文件说明

本项目围绕「学术开源项目（论文+GitHub仓库）」的爬取、分析、可视化展开，文件结构如下：

```
├── 📂 data/                   
│   ├── crawled_data.jsonl      
│   ├── scored_data.jsonl       
│   └── 论文详情_批量爬取.jsonl   
│
└── 📂 代码/                   
    ├── 计算github仓库的贡献度与活跃度.py   
    ├── 爬取GitHub信息.py        
    ├── 爬取joss已出版论文信息.py 
    └── 学术开源项目分析网站生成.py   
```

文件功能如下：

| 文件名                                      | 类型/格式      | 功能说明                                                     |
| ------------------------------------------- | -------------- | ------------------------------------------------------------ |
| `academic_open_source_analysis_report.html` | HTML 网页文件  | 学术开源项目分析的交互式可视化报告（含时间轴、筛选功能等）   |
| `crawled_data.jsonl`                        | JSONL 数据文件 | 从 GitHub 爬取的仓库原始数据（含活跃度、贡献度等基础信息）   |
| `openrank终版.pptx`                         | PPTX 演示文件  | 项目成果展示PPT（含数据结论、可视化效果、功能说明）          |
| `scored_data.jsonl`                         | JSONL 数据文件 | 处理后的仓库评分数据（含总分、贡献度得分、活跃度得分等计算结果） |
| `计算github仓库的贡献度与活跃度.py`         | Python 脚本    | 对 GitHub 仓库原始数据进行清洗、计算，生成 `scored_data.jsonl` 的评分脚本 |
| `论文详情_批量爬取.jsonl`                   | JSONL 数据文件 | 从 JOSS 平台批量爬取的论文详情数据（含论文标题、发表时间、GitHub链接等） |
| `爬取GitHub信息.py`                         | Python 脚本    | 调用 GitHub API 爬取仓库数据，生成 `crawled_data.jsonl` 的爬取脚本 |
| `爬取joss已出版论文信息.py`                 | Python 脚本    | 爬取 JOSS 平台已出版论文信息，生成 `论文详情_批量爬取.jsonl` 的爬取脚本 |
| `数据报告.pdf`                              | PDF 文档       | 项目数据结论的静态报告（含统计分析、图表、核心发现）         |
| `学术开源项目分析网站生成.py`               | Python 脚本    | 生成交互式可视化报告（`academic_open_source_analysis_report.html`）的脚本 |




# 运行说明：

`爬取GitHub信息.py`这一代码需填写github的token才能运行；其余.py文件均**可直接运行**（所需的数据已经通过相对路径写在代码里了）



  网页部分:



  该项目的核心，即**学术开源项目交互网页**已经生成（`academic_open_source_analysis_report.html`），直接点击可打开；

  数据部分：`论文详情_批量爬取.jsonl`为论文的原始数据；

​                `crawled_data.jsonl`为根据论文数据爬取的Github数据；；

​                `scored_data.jsonl`为根据crawled_data.jsonl计算的评分。

  代码部分：`爬取joss已出版论文信息.py`爬取出`论文详情_批量爬取.jsonl`

​                `爬取GitHub信息.py`爬取出`crawled_data.jsonl` 

​                `计算github仓库的贡献度与活跃度.py`计算出`scored_data.jsonl`

​                 