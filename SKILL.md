---
name: xiaohongshu-smart-gen
description: "小红书智能内容生成：支持多垂类配置驱动。金融/美妆/科技等，可扩展。"
user-invocable: true
metadata:
  {
    "openclaw": {
      "emoji": "📱",
      "requires": {
        "bins": ["magick", "python3", "uv"],
        "env": ["GEMINI_API_KEY"],
        "skills": ["nano-banana-pro"]
      },
      "primaryEnv": "GEMINI_API_KEY",
      "install": [
        {
          "id": "imagemagick",
          "kind": "brew",
          "formula": "imagemagick",
          "bins": ["magick"]
        },
        {
          "id": "python",
          "kind": "system",
          "bins": ["python3"]
        },
        {
          "id": "uv",
          "kind": "pip",
          "formula": "uv",
          "bins": ["uv"]
        }
      ]
    }
  }
---

# xiaohongshu-smart-gen 小红书智能内容生成

## 使用方式

```
~/.openclaw/bin/xhs-do finance "美联储最新利率决议"
~/.openclaw/bin/xhs-do beauty "雅诗兰黛DW值得买吗"
~/.openclaw/bin/xhs-do tech "iPhone 16 Pro评测"
```

## 流程（确定性执行）

### Phase 1: Research（研究）

你是话题研究专家。根据垂类配置进行针对性研究：

**金融垂类（finance）研究方向：**
- 个股深挖：公司基本面、催化剂、估值、风险、投资展望
- 宏观分析：经济数据、地缘政治、市场情绪、资产展望

**美妆垂类（beauty）研究方向：**
- 产品信息：品牌、价格、规格、上市时间
- 质地体验：质地、延展性、吸收速度、妆感
- 效果表现：遮瑕力、持妆度、显色度、保湿力
- 肤质适配：干皮/油皮/混合皮/敏感肌

**科技垂类（tech）研究方向：**
- 产品参数：处理器、内存、存储、屏幕、电池
- 性能表现：跑分、实际体验、流畅度、游戏性能
- 功能特性：亮点功能、创新点、生态整合
- 竞品对比：对比机型、优势、劣势

**研究要求：**
1. 使用真实数据和可靠来源
2. 至少 2-3 个来源交叉验证
3. 区分相关性和因果性
4. 列出主要风险或注意事项
5. 提供详细的数据支撑

**数据来源优先级：**
- 一级：官方公告、财报、官网、官方统计
- 二级：行业媒体、测评、研究机构报告

### Phase 2: Write（内容写作）

你是内容创作专家。基于研究数据创建专业内容。

**人设规范：**
- 读取对应垂类的人设文件：`personas/{vertical}.md`
- 所有对外文案都必须遵循人设规范

**各垂类人设特点：**

| 垂类 | 人设 | 特点 |
|------|------|------|
| finance | 量化交易员 | 直接、坚定、数据驱动，拒绝 AI 感 |
| beauty | 资深博主 | 真实、亲切、避坑指南 |
| tech | 专业测评人 | 客观、详细、参数党 |

**通用写作原则（消除 AI 感）：**
- ❌ 禁止"值得注意的是"、"综上所述"、"然而"、"此外"等 AI 痕迹
- ❌ 禁止过度完整平衡的结构
- ❌ 禁止模棱两可的表达
- ✅ 直接下结论，用数据说话，短句为主
- ✅ 使用行业/垂类特定表达
- ✅ 像真人说话，口语化

**小红书笔记结构：**
- **标题：** 直接观点 + 关键信息，≤20字
- **开篇钩子：**（1-2 句）直接抛出结论
- **正文：**（3-5 段）数据/事实 → 逻辑 → 实用建议
- **风险提示/注意事项：**（如适用）
- **关注引导：** 自然、原创，每次不同
- **话题标签：**（5-8 个）

### Phase 3: Cover（封面生成）

两步法生成封面：AI 生成背景 + 本地合成文字。

**Step 1：AI 背景图（Nano Banana Pro）**
- 尺寸：1080x1440 像素（3:4 竖版）
- Prompt：根据垂类配置的 `cover_config.style_prefix`
- 需要 `GEMINI_API_KEY` 配置

**Step 2：本地合成（ImageMagick）**
- **主标题**：超大字号，视觉焦点
- **副标题**：中号字号，补充说明
- **配色方案**：从垂类配置随机选择
- **装饰元素**：从垂类配置随机选择

**执行脚本：**
```bash
~/.openclaw/skills/xiaohongshu-smart-gen/scripts/generate_cover.sh \
  "主标题" \
  "副标题" \
  "/tmp/xhs_cover_$(date +%s).png"
```

### Phase 4: Send（发送 Telegram）

将内容和封面发送到 Telegram。

**执行脚本：**
```bash
~/.openclaw/skills/xiaohongshu-smart-gen/scripts/send_telegram.sh \
  "$XHS_TITLE" \
  "$XHS_FULL_CONTENT" \
  "$XHS_COVER_PATH"
```

## 完整示例

用户输入：`~/.openclaw/bin/xhs-do finance "NVDA GTC 2026 大看点"`

执行流程：

1. **Research：** 搜索 NVIDIA GTC 2026 相关新闻、分析师观点
2. **Write：** 加载 finance 人设，生成小红书笔记
3. **Cover：** 生成封面图（金融风格背景 + 标题）
4. **Send：** 发送到 Telegram

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `TELEGRAM_ACCOUNT` | Telegram bot 账号 | `default` |
| `TELEGRAM_TARGET` | Telegram chat ID 或 @username | **可选** |

**说明：**
- 从 Telegram 激活 skill 时，无需设置 `TELEGRAM_TARGET`
- 从其他地方激活 skill 时，需要设置 `TELEGRAM_TARGET`

## 垂类扩展

使用引导器快速创建新垂类：

```bash
python3 ~/.openclaw/skills/xiaohongshu-smart-gen/scripts/bootstrap_vertical.py
```

垂类配置位于 `verticals/{code}.json`，包含：
- 搜索策略（search_strategy）
- 研究维度（research_dimensions）
- 内容结构（content_structure）
- 标题模板（title_template）
- 封面配置（cover_config）

人设文件位于 `personas/{code}.md`。

## 注意事项

- 所有内容必须基于真实数据，不编造信息
- 金融垂类必须包含风险提示
- 遵循人设规范，保持内容风格一致
- 封面生成失败时，继续完成文字内容即可
