<div align="center">

# 📚 zpaper

**运行在 [Claude Code](https://claude.ai/code) 内部的个人科研助手。**

导入论文 · 搜索文献库 · 精读 PDF · 记录笔记 · 发现关联 · 生成综述

*全部通过自然语言完成。无 GUI，无云端，所有数据存储在本地。*

---

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Claude Code](https://img.shields.io/badge/Claude_Code-skill-CC785C?style=flat-square&logo=anthropic&logoColor=white)](https://claude.ai/code)
[![License](https://img.shields.io/badge/License-MIT-22C55E?style=flat-square)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux-lightgrey?style=flat-square)]()

</div>

---

![zpaper showcase](docs/showcase.png)

---

## ✨ 功能

<table>
<tr>
<td width="50%">

**📥 导入与管理**
- 粘贴 arXiv ID、URL 或本地路径，自动获取元数据并下载 PDF
- 为论文打标签、追踪阅读状态（`unread` / `reading` / `read`）
- 跨标题、摘要、关键词和笔记的全文检索

</td>
<td width="50%">

**🌐 文献发现**
- 直接搜索 arXiv，一步导入结果
- 自动发现库中相关论文，并说明关联原因
- 将文献库可视化为时间线与连接图谱

</td>
</tr>
<tr>
<td width="50%">

**🔍 阅读与理解**
- 结构化摘要：背景 · 方法 · 结果 · 局限性
- 逐节精读，Claude 全程解释并提问检验理解
- 输入任意术语，Claude 在 PDF 中定位并结合上下文解释

</td>
<td width="50%">

**📝 笔记与综述**
- 为任意论文添加笔记，跨库检索，导出为 Markdown
- 指定主题，Claude 综合相关论文和你的笔记生成带引用的综述草稿

</td>
</tr>
</table>

---

## 🚀 安装

**前置要求：** [Claude Code](https://docs.anthropic.com/en/docs/claude-code) · Python 3.9+ · `pymupdf` · `requests`

```bash
git clone https://github.com/YOUR_USERNAME/zpaper.git
cd zpaper
bash scripts/install.sh
```

安装脚本会完成三件事：

1. 📦 安装 `zpaper` Python 包（`pip install -e .`）
2. 🗄️ 创建 `~/.scholarmind/` 目录，用于存放数据库和 PDF
3. 🔌 将 skill 文件复制到 `~/.claude/skills/paper/`

> 打开任意 Claude Code 会话，即可使用 `/paper`。

---

## ⚡ 快速上手

```bash
# ── 导入 ────────────────────────────────────────────
/paper add 1706.03762
/paper add https://arxiv.org/abs/2310.06825
/paper add ~/Downloads/my_paper.pdf
/paper add 1706.03762 2310.06825 2301.12345   # 批量导入

# ── 搜索 ────────────────────────────────────────────
/paper search "attention mechanism"
/paper web-search "vision language model survey"

# ── 阅读 ────────────────────────────────────────────
/paper read arxiv:1706.03762                       # 总结模式
/paper read arxiv:1706.03762 --mode deep           # 逐节精读

# ── 笔记 ────────────────────────────────────────────
/paper note arxiv:1706.03762 这里是他们放弃 RNN 的核心理由
/paper related arxiv:1706.03762

# ── 综述 ────────────────────────────────────────────
/paper survey "transformer language model"
```

也可以直接用自然语言和 Claude 对话：

> 💬 *"把 BERT 论文加入我的文献库"*

> 💬 *"帮我总结一下 GPT-3 那篇论文"*

> 💬 *"我的库里有哪些跟扩散模型相关的文献？"*

> 💬 *"帮我写一篇关于视觉语言预训练的综述"*

---

## 📖 完整命令参考

<details>
<summary><b>📥 导入与管理</b></summary>

```
/paper add <id|url|path> [...]             导入论文（支持批量，空格分隔多个来源）
/paper list                                列出论文（最近 20 篇）
/paper list --all                          列出所有论文
/paper list --status <unread|reading|read> 按状态筛选
/paper search <关键词>                     全文检索本地文献库
/paper web-search <关键词>                 搜索 arXiv
/paper show <id>                           查看论文详情
/paper edit <id> field=value ...           编辑元数据字段
/paper tag <id> <标签1,标签2>              追加标签
/paper status <id> <状态>                  更新阅读状态
/paper delete <id>                         从库中删除（PDF 文件保留）
```

</details>

<details>
<summary><b>🔍 阅读与笔记</b></summary>

```
/paper read <id>                           总结模式（默认）
/paper read <id> --mode deep               精读全文
/paper read <id> --mode deep --section N   精读指定章节
/paper sections <id>                       列出检测到的章节
/paper explain <id> <关键词或句子片段>     在 PDF 中查找并解释
/paper note <id> <文本>                    为论文添加笔记
/paper notes <id>                          列出某篇论文的所有笔记（显示笔记 ID）
/paper notes --search <关键词>             跨全库检索笔记
/paper note-delete <note_id>               按 ID 删除笔记
/paper export <id>                         输出笔记为 Markdown
/paper export <id> -o 笔记.md              保存笔记到文件
```

</details>

<details>
<summary><b>🗺️ 发现与综述</b></summary>

```
/paper related <id>                        查找相关论文（附关联原因）
/paper graph                               全库文献网络概览
/paper graph <主题>                        按主题筛选的网络视图
/paper survey                              全库综述概览
/paper survey <主题>                       生成指定主题的综述草稿
```

</details>

<details>
<summary><b>⚙️ 配置</b></summary>

```
/paper config                              查看库位置和统计信息
/paper config --set-lib-dir <路径>         更改文献库目录
```

</details>

---

## 🏗️ 工作原理

**Python 负责所有 I/O** —— 数据库读写、PDF 解析、arXiv API 调用。
**Claude 负责所有推理** —— 总结、精读、综述写作、图网络分析。

无需额外 API Key，复用已有的 Claude Code 会话即可。

**仓库结构**

```
zpaper/
├── src/zpaper/
│   ├── cli.py           # 所有子命令
│   ├── library.py       # SQLite 数据库 + 元数据提取
│   ├── search.py        # arXiv API + PDF 下载
│   ├── reader.py        # PDF 文本提取 + 章节检测
│   └── graph.py         # 相似度计算 + 主题聚类
├── skill/
│   └── skill.md         # Claude Code skill 定义
├── scripts/
│   └── install.sh       # 一键安装脚本
└── pyproject.toml
```

**安装后的运行时结构**

```
~/.claude/skills/paper/
└── skill.md             # 告诉 Claude 如何调用各工具

~/.scholarmind/
├── library.db           # 论文 + 笔记（SQLite）
└── pdfs/                # 下载的 PDF 文件
```

> **相似度算法：** 基于 TF-IDF 加权的词重叠，覆盖摘要、标题和关键词，用户标签额外加权。无需嵌入模型或向量数据库，完全本地计算。

---

## 🔖 论文 ID 格式

每篇论文会被分配一个稳定的可读 ID：

| 格式 | 来源 |
|:---|:---|
| `arxiv:2301.12345` | 通过 arXiv ID 或 URL 导入的论文 |
| `local:abc123def` | 未检测到 arXiv ID 的本地 PDF |

在命令中直接使用这些 ID，例如 `/paper read arxiv:1706.03762`。

---

## 📄 License

[MIT](LICENSE) · Built for [Claude Code](https://claude.ai/code)
