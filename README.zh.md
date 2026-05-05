# zpaper — Claude Code 文献管理与阅读助手

在 [Claude Code](https://claude.ai/code) 内部运行的个人科研助手。导入论文、搜索文献库、逐节精读 PDF、记录笔记、发现文献关联、生成综述草稿——全部通过自然语言完成，无需离开终端。

无 GUI，无云端，所有数据存储在本地。

---

## 功能一览

| 功能 | 说明 |
|---|---|
| **导入论文** | 粘贴 arXiv ID 或 URL，自动获取元数据并下载 PDF；也可以直接导入本地 PDF |
| **搜索文献库** | 跨标题、摘要、关键词和笔记的全文检索 |
| **搜索 arXiv** | 直接查询 arXiv 并一步导入结果 |
| **总结模式** | Claude 阅读全文，生成结构化摘要：背景 / 方法 / 结果 / 局限性 / 相关工作 |
| **精读模式** | 逐节引导阅读，每节后 Claude 提问检验理解，记录疑问 |
| **笔记系统** | 为任意论文添加笔记，跨库检索，导出为 Markdown |
| **相关论文** | 自动发现库中与指定论文相关的文献，并说明关联原因 |
| **文献网络** | 展示库的时间线与连接图谱（可按主题筛选） |
| **综述模式** | 指定主题，Claude 将相关论文和你的笔记综合成带引用的综述草稿 |

---

## 环境要求

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)（CLI 版本）
- Python 3.9+
- `pymupdf` 和 `requests`（见下方安装步骤）

---

## 安装

### 1. 克隆仓库

```bash
git clone https://github.com/YOUR_USERNAME/zpaper.git
cd zpaper
```

### 2. 运行安装脚本

```bash
bash scripts/install.sh
```

脚本会完成三件事：
1. 安装 `zpaper` Python 包（通过 `pip install -e .` 的可编辑安装）
2. 创建 `~/.scholarmind/` 目录，用于存放文献数据库和 PDF
3. 将 Claude Code skill 文件复制到 `~/.claude/skills/paper/`

安装完成后，终端中可以直接使用 `paper` 命令，Claude Code 也会自动识别 `/paper` skill。

完成后打开 Claude Code 会话，即可使用 `/paper` 命令。

---

## 快速上手

```
# 从 arXiv 导入论文
/paper add 1706.03762

# 从 URL 导入
/paper add https://arxiv.org/abs/2310.06825

# 导入本地 PDF
/paper add ~/Downloads/my_paper.pdf

# 搜索 arXiv 并选择导入
/paper web-search "vision language model survey"

# 搜索本地文献库
/paper search "attention mechanism"

# 总结一篇论文
/paper read arxiv:1706.03762

# 精读模式（逐节阅读）
/paper read arxiv:1706.03762 --mode deep

# 阅读时添加笔记
/paper note arxiv:1706.03762 这里是他们放弃 RNN 的核心理由

# 查找相关论文
/paper related arxiv:1706.03762

# 生成综述草稿
/paper survey transformer language model
```

也可以直接用自然语言和 Claude 对话：

> "把 BERT 论文加入我的文献库"
> "帮我总结一下 GPT-3 那篇论文"
> "我的库里有哪些跟扩散模型相关的文献？"
> "帮我写一篇关于视觉语言预训练的综述"

---

## 完整命令参考

### 导入与管理

```
/paper add <arxiv_id|url|path>            导入论文
/paper list                               列出所有论文
/paper list --status unread               按状态筛选（unread/reading/read）
/paper search <关键词>                    全文检索本地文献库
/paper web-search <关键词>               搜索 arXiv
/paper show <id>                          查看论文详情
/paper tag <id> <标签1,标签2>             为论文添加标签
/paper status <id> <unread|reading|read>  更新阅读状态
/paper delete <id>                        从库中删除（PDF 文件保留）
```

### 阅读与笔记

```
/paper read <id>                          总结模式（默认）
/paper read <id> --mode deep              精读模式（逐节引导）
/paper read <id> --mode deep --section N  跳到第 N 节
/paper sections <id>                      列出 PDF 检测到的章节
/paper note <id> <文本>                   为论文添加笔记
/paper notes <id>                         列出某篇论文的所有笔记
/paper notes --search <关键词>            跨全库检索笔记
/paper export <id>                        输出笔记为 Markdown
/paper export <id> -o 笔记.md             保存笔记到文件
```

### 发现与综述

```
/paper related <id>                       查找相关论文（附关联原因）
/paper graph                              全库文献网络概览
/paper graph <主题>                       按主题筛选的网络视图
/paper survey                             全库综述概览
/paper survey <主题>                      生成指定主题的综述草稿
```

### 配置

```
/paper config                             查看库位置和统计信息
/paper config --set-lib-dir <路径>        更改文献库目录
```

---

## 工作原理

**仓库结构：**

```
zpaper/
├── src/zpaper/          # Python 包
│   ├── cli.py           # CLI 入口 — 所有子命令
│   ├── library.py       # SQLite 数据库 + PDF 元数据提取
│   ├── search.py        # arXiv API 搜索 + PDF 下载
│   ├── reader.py        # PDF 文本提取 + 章节检测
│   └── graph.py         # 相似度计算 + 主题聚类
├── skill/
│   └── skill.md         # Claude Code skill 定义
├── docs/
│   ├── PRD.md           # 产品需求文档（英文）
│   └── PRD.zh.md        # 产品需求文档（中文）
├── scripts/
│   └── install.sh       # 一键安装脚本
├── pyproject.toml       # 包元数据 + `paper` 命令行入口
├── README.md
└── README.zh.md
```

**安装后的运行时结构：**

```
~/.claude/skills/paper/
└── skill.md             # 告诉 Claude 如何调用各工具

~/.scholarmind/
├── library.db           # SQLite 数据库（论文 + 笔记）
└── pdfs/                # 下载的 PDF 文件
```

**架构设计：** Python 脚本负责所有 I/O（数据库读写、PDF 解析、arXiv API 调用）；Claude 负责所有推理（总结、精读、综述写作、网络分析）。无需额外 API Key，复用已有的 Claude Code 会话。

**相似度算法：** 基于 TF-IDF 加权的词重叠，覆盖摘要、标题和关键词字段，用户标签额外加权。无需向量数据库或嵌入模型，完全本地计算。

---

## 论文 ID 格式

每篇论文会被分配一个稳定 ID：

| 格式 | 来源 |
|---|---|
| `arxiv:2301.12345` | 通过 arXiv ID 或 URL 导入的论文 |
| `local:abc123def` | 未检测到 arXiv ID 的本地 PDF |

在命令中直接使用这些 ID，例如 `/paper read arxiv:1706.03762`。

---

## PRD

驱动本项目实现的完整产品需求文档见 [`PRD.zh.md`](PRD.zh.md)。

---

## License

MIT
