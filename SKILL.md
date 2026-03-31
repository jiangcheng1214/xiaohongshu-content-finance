---
name: xiaohongshu-smart-gen
description: 小红书多垂类内容智能生成技能。支持金融、美妆、科技等垂类，从话题研究到内容创作、封面生成的全链路自动化。
license: MIT
compatibility: Requires Python 3, requests, nano-banana-pro skill, and GEMINI_API_KEY. Works on macOS/Linux/Windows.
argument-hint: "<vertical> <topic> [--max-retries N]"
disable-model-invocation: false
user-invocable: true
metadata:
  openclaw:
    requires:
      bins: [python3]
      skills: [nano-banana-pro]
      env: [GEMINI_API_KEY]
    emoji: "\U0001F4A1"
    os: [darwin, linux, windows]
    stateless: true
    no_context: true
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
   python3 scripts/cli.py generate <vertical> "<topic>"
3. [Agent] 查看 session 信息
   python3 scripts/cli.py info <session_dir>
```

### 快捷调用方式

```bash
# 使用 CLI（推荐）
cd ~/.openclaw/skills/xiaohongshu-smart-gen
python3 scripts/cli.py generate finance "PLTR还能追吗"

# 使用 hook
bash hooks/xhs_do.sh finance "PLTR还能追吗"
```

### Session 管理

每个任务创建独立的 session 目录：

```
~/.openclaw/agents/main/agent/xhs_session_<timestamp>_<safe_topic>/
├── session.json       # session 元数据
├── content.md         # 生成的文字内容
├── cover.png          # 生成的封面图
└── images/            # 搜索到的参考图
```

### 垂类选择

| 垂类 | 代码 | 人设 | 特点 |
|------|------|------|------|
| 金融投资 | `finance` | 量化交易员 | 数据驱动，风险提示 |
| 股票 | `stock` | 股票分析 | 实时行情，数据驱动 |
| 美妆护肤 | `beauty` | 资深博主 | 真实测评，避坑指南 |
| 数码科技 | `tech` | 专业测评人 | 参数分析，购买建议 |
| 壁纸 | `wallpaper` | 壁纸分享 | 高清壁纸 |

---

## Python CLI 命令

> **工作目录**: `~/.openclaw/skills/xiaohongshu-smart-gen`

### 主命令

```bash
# 设置工作目录
cd ~/.openclaw/skills/xiaohongshu-smart-gen

# 完整生成（内容 + 封面 + 发送）
python3 scripts/cli.py generate finance "PLTR还能追吗"

# 分步执行
python3 scripts/cli.py content finance "PLTR" --max-retries 3
python3 scripts/cli.py cover finance "PLTR"
python3 scripts/cli.py send <session_dir>

# 查看信息
python3 scripts/cli.py info <session_dir>
python3 scripts/cli.py list
python3 scripts/cli.py verticals
```

---

## CLI 子命令参考

### generate - 完整生成流程

```bash
python3 scripts/cli.py generate <vertical> "<topic>" [--max-retries N]
```

执行完整的 7 步流水线：研究 → 内容生成 → 验证 → 封面生成 → 发送

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `vertical` | 垂类代码 (finance/stock/tech/beauty/wallpaper) | - |
| `topic` | 内容主题（必需） | - |
| `--max-retries` | 内容生成最大重试次数 | 2 |

**输出示例**：
```json
{
  "success": true,
  "session_id": "xhs_session_1712345678_PLTR",
  "session_dir": "/Users/user/.openclaw/agents/main/agent/xhs_session_1712345678_PLTR",
  "vertical": "finance",
  "topic": "PLTR还能追吗",
  "status": "completed",
  "content": {
    "title": "PLTR还能追吗？",
    "subtitle": "数据告诉你真相",
    "content_length": 523
  },
  "cover": "/path/to/cover.png",
  "content_file": "/path/to/content.md"
}
```

### content - 仅生成内容

```bash
python3 scripts/cli.py content <vertical> "<topic>" [--max-retries N]
```

执行步骤 1-3：研究 → 内容生成 → 验证

**输出示例**：
```json
{
  "success": true,
  "session_id": "xhs_session_1712345678_PLTR",
  "content": {
    "title": "PLTR还能追吗？",
    "subtitle": "数据告诉你真相",
    "content_length": 523
  },
  "content_file": "/path/to/content.md"
}
```

### cover - 仅生成封面

```bash
python3 scripts/cli.py cover <vertical> "<topic>"
```

执行步骤 4-6：封面变量收集 → 图片生成 → Logo 叠加

**注意**：需要先执行 `content` 命令生成内容

### info - 显示 Session 信息

```bash
python3 scripts/cli.py info <session_dir>
```

查看指定 session 的详细状态、生成内容、文件等信息

**输出示例**：
```json
{
  "success": true,
  "session": {
    "id": "xhs_session_1712345678_PLTR",
    "vertical": "finance",
    "topic": "PLTR还能追吗",
    "status": "completed",
    "session_dir": "/path/to/session",
    "created_at": "2025-03-30T10:00:00Z",
    "updated_at": "2025-03-30T10:05:00Z"
  },
  "steps": {
    "research": {"status": "completed"},
    "generate": {"status": "completed"},
    "validate": {"status": "completed"},
    "prepare_img": {"status": "completed"},
    "gen_img": {"status": "completed"},
    "overlay": {"status": "completed"},
    "deliver": {"status": "completed"}
  },
  "files": {
    "content": "/path/to/content.md",
    "cover": "/path/to/cover.png"
  }
}
```

### list - 列出所有 Sessions

```bash
python3 scripts/cli.py list
```

**输出示例**：
```json
{
  "success": true,
  "count": 3,
  "sessions": [
    {
      "id": "xhs_session_1712345678_PLTR",
      "vertical": "finance",
      "topic": "PLTR还能追吗",
      "status": "completed",
      "session_dir": "/path/to/session1"
    }
  ]
}
```

### verticals - 列出支持的垂类

```bash
python3 scripts/cli.py verticals
```

**输出示例**：
```json
{
  "success": true,
  "verticals": [
    {"code": "finance", "name": "金融投资", "description": "量化交易员人设，数据驱动，风险提示"},
    {"code": "stock", "name": "股票", "description": "股票分析，实时行情，数据驱动"},
    {"code": "tech", "name": "数码科技", "description": "专业测评人，参数分析，购买建议"},
    {"code": "beauty", "name": "美妆护肤", "description": "资深博主，真实测评，避坑指南"},
    {"code": "wallpaper", "name": "壁纸", "description": "高清壁纸分享"}
  ]
}
```

### send - 发送到 Telegram

```bash
python3 scripts/cli.py send <session_dir>
```

将已生成的内容发送到 Telegram

---

## 退出码

| 退出码 | 说明 |
|--------|------|
| 0 | 成功 |
| 1 | 部分失败（如内容生成成功但封面失败） |
| 2 | 完全失败 |

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
| `--images` | 搜索参考图片 | - |
| `--cover` | 生成封面图 | - |
| `--info` | 显示 session 信息 | - |
| `--all` | 执行全部步骤（默认） | - |
| `--send` | 发送已有内容到 Telegram | - |

---

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `GEMINI_API_KEY` | AI 图片生成 API Key | 从 openclaw.json 读取 |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | 从 openclaw.json 读取 |
| `TELEGRAM_CHAT_ID` | 目标 chat ID | 自动获取 |

---

## Telegram 发送

使用 `--send` 参数自动发送内容到 Telegram：

```bash
# 生成并发送
python scripts/xhs_do.py finance "PLTR" --all --send

# 仅发送已有内容
python scripts/xhs_do.py finance "PLTR" --send
```

发送前会自动：
1. 整理文件到导出目录（跨平台）
2. 发送封面图 + 内容文字
3. 如果封面不存在，仅发送文字

**导出目录位置**：
- macOS/Linux: `~/Desktop/Xiaohongshu_Exports/`
- Windows: `%USERPROFILE%\Desktop\Xiaohongshu_Exports\`

---

## 参考文档

| 文档 | 说明 |
|------|------|
| [README.md](README.md) | 项目说明和安装指南 |
| [personas/](personas/) | 各垂类人设规范 |
| [verticals/](verticals/) | 垂类配置文件 |
