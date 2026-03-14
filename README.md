# xiaohongshu-content-finance

<div align="center">

![License](https://img.shields.io/badge/license-MIT-blue)
![Platform](https://img.shields.io/badge/platform-macos-lightgrey)
![Openclaw](https://img.shields.io/badge/openclaw-skill-orange)

</div>

<div align="center">

![工作流程](demo/process.png)

**小红书金融内容生成系统** — 量化交易员视角，数据驱动

`研究` → `内容` → `封面` → `发布`

</div>

## ✨ 示例效果

<table>
<tr>
<td align="center" width="50%">
<img src="demo/example1.png" alt="示例 1" />
<br />
<b>示例 1</b>
</td>
<td align="center" width="50%">
<img src="demo/example2.png" alt="示例 2" />
<br />
<b>示例 2</b>
</td>
</tr>
</table>

## 📖 项目介绍

**xiaohongshu-content-finance** 是一个专为金融领域设计的小红书内容自动化生成工具。它采用一线量化交易员的人设视角，通过数据驱动的方式，从市场研究到内容创作、封面生成、最终发布，实现全流程自动化。

### 为什么需要这个工具？

- **节省时间**：从收集数据到发布，原本需要 1-2 小时的工作，现在几分钟完成
- **专业视角**：量化交易员的人设确保内容专业、有深度，拒绝 AI 感
- **数据驱动**：基于 24 小时内真实市场数据，确保内容时效性和准确性
- **风格统一**：遵循预设的人设规范，保持内容风格一致性

### 核心特性

| 特性 | 说明 |
|------|------|
| 📊 **实时研究** | 聚合 24 小时内市场数据，多源交叉验证 |
| ✍️ **人设写作** | 量化交易员视角，口语化，拒绝 AI 痕迹 |
| 🎨 **AI 封面** | 城市夜景背景 + 本地合成文字，专业质感 |
| 📤 **一键发布** | 自动发送到 Telegram 频道或私聊 |

## 功能

- **市场研究**：基于 24 小时内真实数据进行深度分析
- **内容创作**：遵循专业人设规范，生成高质量小红书笔记
- **封面生成**：AI 驱动的封面图，支持 3:4 竖版规格
- **Telegram 发布**：一键发送到指定的 Telegram 频道或私聊

## 使用方法

```
/skill:xiaohongshu-content-finance --topic="美联储最新利率决议" --vertical="金融"
```

### 参数

| 参数 | 说明 | 必需 | 默认值 |
|------|------|------|--------|
| `--topic` | 内容主题 | 是 | - |
| `--vertical` | 内容领域 | 否 | 金融 |

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `TELEGRAM_ACCOUNT` | Telegram bot 账号 | `default` |
| `TELEGRAM_TARGET` | 目标 chat ID 或 @username | 自动回复 |

## 安装

### 一键安装

```bash
~/.openclaw/skills/xiaohongshu-content-finance/scripts/install.sh
```

### 手动安装

#### 1. 系统依赖

**macOS (Homebrew)**:
```bash
brew install imagemagick python3
```

**uv (Python 包管理器)**:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### 2. 配置 API Key

创建 `~/.openclaw/openclaw.json`:

```json
{
  "env": {
    "GEMINI_API_KEY": "your-api-key-here"
  }
}
```

获取 API Key: https://makersuite.google.com/app/apikey

#### 3. 安装依赖技能

```bash
openclaw skill install nano-banana-pro
```

#### 4. 安装 openclaw CLI (可选)

用于 Telegram 发送功能:

```bash
npm install -g @openclaw/cli
```

## 依赖检查

运行检查脚本验证所有依赖:

```bash
~/.openclaw/skills/xiaohongshu-content-finance/scripts/check.sh
```

## 依赖详情

### 必需工具

| 工具 | 用途 | 安装 |
|------|------|------|
| ImageMagick | 图片处理 | `brew install imagemagick` |
| Python 3 | 脚本运行 | `brew install python3` |
| uv | Python 包管理 | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

### 技能依赖

| 技能 | 用途 |
|------|------|
| nano-banana-pro | AI 背景图生成 |

### 配置需求

| 配置 | 用途 |
|------|------|
| GEMINI_API_KEY | AI 图片生成 |

## 目录结构

```
xiaohongshu-content-finance/
├── SKILL.md              # 技能定义
├── persona.md           # 人设规范
├── README.md            # 本文件
├── assets/
│   └── logo.png         # 品牌标识
├── scripts/
│   ├── install.sh       # 一键安装脚本
│   ├── check.sh         # 依赖检查脚本
│   ├── generate_cover.sh # 封面生成
│   ├── send_telegram.sh # Telegram 发送
│   └── add_overlay.sh   # 文字叠加
└── templates/
    └── content.json     # 内容模板
```

## 内容人设

本技能采用**一线量化交易员**人设，内容特点：

- 直接、坚定、数据驱动
- 拒绝 AI 感，使用职业黑话
- 短句为主，像交易员聊天室说话
- 明确立场，不模棱两可

详细规范请参考 [persona.md](persona.md)。

## 平台支持

目前主要支持 **macOS**。Linux 用户可能需要调整字体路径。

## License

MIT

## Contributing

欢迎提交 Issue 和 Pull Request！
