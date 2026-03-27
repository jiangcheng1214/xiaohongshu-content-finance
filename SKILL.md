---
name: xiaohongshu-smart-gen
description: 小红书多垂类内容智能生成技能。支持金融、美妆、科技等垂类，从话题研究到内容创作、封面生成的全链路自动化。
license: MIT
compatibility: Requires ImageMagick, Python 3, uv, nano-banana-pro skill, and GEMINI_API_KEY. Works on macOS/Linux.
argument-hint: "<vertical> <topic> [--init|--content|--cover|--info|--all]"
disable-model-invocation: false
user-invocable: true
metadata:
  openclaw:
    requires:
      bins: [python3, convert]
      skills: [nano-banana-pro]
      env: [GEMINI_API_KEY]
    emoji: "\U0001F4A1"
    os: [darwin, linux]
---

# 小红书智能内容生成技能

多垂类内容自动生成：**研究** → **内容** → **封面** → **发布**

支持金融、美妆、科技等多个垂类，每个垂类拥有独立的人设和内容风格。

---

## Agent 快速参考

### 完整内容生成流程

当用户请求 "生成[垂类]内容..." 时：

```
1. [用户] 提供垂类和主题
2. [Agent] 执行完整生成流程
   cd ~/.openclaw/skills/xiaohongshu-smart-gen
   PYTHONPATH=. python -m scripts.xhs_cli <vertical> "<topic>" --all
3. [Agent] 查看 session 信息
   PYTHONPATH=. python -m scripts.xhs_cli info "<topic>"
```

### Session 管理

每个任务创建独立的 session 目录：

```
~/.openclaw/agents/main/agent/xhs_session_<timestamp>_<safe_topic>/
├── session.json       # session 元数据
├── vertical.json      # 垂类配置副本
├── content.md         # 生成的文字内容
├── cover.png          # 生成的封面图
└── images/            # 搜索到的参考图
```

### 垂类选择

| 垂类 | 代码 | 人设 | 特点 |
|------|------|------|------|
| 金融投资 | `finance` | 量化交易员 | 数据驱动，风险提示 |
| 美妆护肤 | `beauty` | 资深博主 | 真实测评，避坑指南 |
| 数码科技 | `tech` | 专业测评人 | 参数分析，购买建议 |

---

## Python CLI 命令

> **工作目录**: `~/.openclaw/skills/xiaohongshu-smart-gen`

### 主工作流

```bash
# 设置工作目录
cd ~/.openclaw/skills/xiaohongshu-smart-gen

# 完整生成（内容 + 封面）
PYTHONPATH=. python -m scripts.xhs_cli finance "PLTR还能追吗" --all

# 分步执行
PYTHONPATH=. python -m scripts.xhs_cli finance "PLTR" --init     # 初始化
PYTHONPATH=. python -m scripts.xhs_cli finance "PLTR" --content  # 生成内容
PYTHONPATH=. python -m scripts.xhs_cli finance "PLTR" --cover    # 生成封面
PYTHONPATH=. python -m scripts.xhs_cli finance "PLTR" --info     # 查看信息
```

### 新接口命令

```bash
# 初始化新 session
PYTHONPATH=. python -m scripts.xhs_cli init <vertical> "<topic>"

# 显示 session 信息
PYTHONPATH=. python -m scripts.xhs_cli info "<topic>"

# 列出所有 sessions
PYTHONPATH=. python -m scripts.xhs_cli list

# 检查配置
PYTHONPATH=. python -m scripts.xhs_cli check-config
```

### xhs-do 快捷方式

```bash
# 使用快捷包装器（绕过 AI 解析）
~/.openclaw/bin/xhs-do finance "PLTR还能追吗"
~/.openclaw/bin/xhs-do beauty "雅诗兰黛DW值得买吗"
~/.openclaw/bin/xhs-do tech "iPhone 16 Pro评测"
```

---

## 数据格式

### 垂类配置结构

```json
{
  "code": "finance",
  "name": "金融",
  "generation_mode": "strict",
  "persona_id": "finance",
  "keywords": ["美联储", "利率", "A股"],
  "content_structure": {
    "min_length": 400,
    "max_length": 600,
    "paragraphs": [
      {"order": 1, "type": "hook", "name": "开篇钩子"},
      {"order": 2, "type": "body", "name": "核心观点"}
    ],
    "requires_risk_warning": true
  },
  "title_template": {
    "patterns": ["{topic}：{核心观点}"],
    "max_length": 20
  },
  "cover_config": {
    "logo_file": "finance.png",
    "background_prompt_template": "Professional gradient background..."
  }
}
```

### 内容结构

| 字段 | 说明 |
|------|------|
| title | 标题，≤20字 |
| content | 正文内容，遵循垂类 paragraph 结构 |
| tags | 话题标签，5-8个 |

---

## 技能联动

### 输出到 xhs-auto-publish

生成完成后，可使用 `xhs-auto-publish` 技能发布：

```bash
# 1. 生成内容
cd ~/.openclaw/skills/xiaohongshu-smart-gen
SESSION=$(PYTHONPATH=. python -m scripts.xhs_cli finance "PLTR" --all | tail -1)

# 2. 提取数据
TITLE=$(grep '^# ' "$SESSION/content.md" | head -1 | sed 's/^# //')
CONTENT=$(sed '1d;/^#/d' "$SESSION/content.md")
COVER="$SESSION/cover.png"

# 3. 创建发布数据
echo "{\"title\":\"$TITLE\",\"content\":\"$CONTENT\"}" > /tmp/xhs_data.json

# 4. 调用发布技能
cd ~/.openclaw/skills/xhs-auto-publish
xhs draft create --type image --data-file /tmp/xhs_data.json --cover "$COVER"
```

---

## 参数说明

### Python CLI

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `<vertical>` | 垂类代码 | finance |
| `<topic>` | 内容主题（必需） | - |
| `--init` | 初始化新 session | - |
| `--content` | 生成文字内容 | - |
| `--cover` | 生成封面图 | - |
| `--info` | 显示 session 信息 | - |
| `--all` | 执行全部步骤（默认） | - |

---

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `GEMINI_API_KEY` | AI 图片生成 API Key | 从 openclaw.json 读取 |
| `TELEGRAM_ACCOUNT` | Telegram bot 账号 | default |
| `TELEGRAM_TARGET` | 目标 chat ID | 自动回复 |

---

## 参考文档

| 文档 | 说明 |
|------|------|
| [README.md](README.md) | 项目说明和安装指南 |
| [personas/](personas/) | 各垂类人设规范 |
| [verticals/](verticals/) | 垂类配置文件 |
