#!/usr/bin/env python3
"""
垂类引导器 - 交互式创建新垂类
支持快速生成配置文件和人设文件模板
"""
import os
import sys
import json
import argparse
from datetime import datetime


def get_skill_dir():
    """获取技能目录"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_vertical_config(code: str, name: str, mode: str, keywords: list = None) -> dict:
    """
    创建垂类配置

    Args:
        code: 垂类代码
        name: 垂类名称
        mode: 生成模式 (strict/advanced)
        keywords: 关键词列表

    Returns:
        配置字典
    """
    if keywords is None:
        keywords = []

    config = {
        "code": code,
        "name": name,
        "generation_mode": mode,
        "persona_id": f"{code}-creator",
        "keywords": keywords,
        "search_strategy": {
            "data_sources": [
                "官方网站",
                "行业媒体",
                "社交媒体"
            ],
            "image_types": [
            "product",
            "scene",
            "demo"
            ],
            "image_keywords": [
            "产品图",
            "场景图",
            "效果图"
            ],
            "content_types": [
            "产品介绍",
            "使用心得",
            "测评"
            ],
            "search_queries_template": [
            "{topic} 介绍",
            "{topic} 测评",
            "{topic} 怎么样",
            "{topic} 值得买吗"
            ]
        },
        "research_dimensions": [
            {
            "name": "核心观点",
            "required": True,
            "data_driven": False
            },
            {
            "name": "产品信息",
            "required": True,
            "fields": [
                "品牌",
                "价格",
                "规格"
            ]
            },
            {
            "name": "使用体验",
            "required": True,
            "fields": [
                "优点",
                "缺点",
                "适用场景"
            ]
            },
            {
            "name": "购买建议",
            "required": True,
            "fields": [
                "推荐人群",
                "购买时机"
            ]
            }
        ],
        "content_structure": {
            "min_length": 350,
            "max_length": 550,
            "paragraphs": [
            {
                "order": 1,
                "type": "hook",
                "name": "开篇钩子",
                "length": "1-2句",
                "instruction": "直接说结论或制造悬念"
            },
            {
                "order": 2,
                "type": "body",
                "name": "核心观点",
                "length": "40-60字",
                "instruction": "这是什么，为什么重要"
            },
            {
                "order": 3,
                "type": "body",
                "name": "产品信息",
                "length": "60-100字",
                "instruction": "品牌、价格、规格等基本信息"
            },
            {
                "order": 4,
                "type": "body",
                "name": "使用体验",
                "length": "60-100字",
                "instruction": "实际使用感受，优缺点"
            },
            {
                "order": 5,
                "type": "body",
                "name": "购买建议",
                "length": "1-2句",
                "instruction": "推荐/不推荐，适合谁"
            },
            {
                "order": 6,
                "type": "cta",
                "name": "关注引导",
                "length": "1-2句",
                "instruction": "持续分享，每次原创"
            },
            {
                "order": 7,
                "type": "tags",
                "name": "话题标签",
                "count": "5-8",
                "instruction": f"#{code} #分享 等"
            }
            ],
            "requires_risk_warning": False,
            "requires_data_timestamp": False,
            "requires_sources": False
        },
        "title_template": {
            "patterns": [
            "{topic}真实测评",
            "{topic}值不值得买？",
            "{topic}使用感受",
            "说人话：{topic}怎么样"
            ],
            "max_length": 20,
            "style": "话题 + 结论/疑问"
        },
        "cover_config": {
            "logo_file": "logo.png",
            "default_subtitle": "分享",
            "color_schemes": [
            "warm gradient"
            ],
            "decorations": [
            "minimal geometric shapes"
            ],
            "style_prefix": "Clean background"
        }
    }

    return config


def create_persona_content(code: str, name: str) -> str:
    """
    创建人设文件内容

    Args:
        code: 垂类代码
        name: 垂类名称

    Returns:
        人设文件内容
    """
    content = f"""# 小红书{name}内容人设规范

## 人设
- 身份：**资深{name}创作者**，深耕{name}领域多年
- 气质：**专业、真实、接地气**。不说空话，不夸大其词
- 说话方式：像和朋友聊天，自然、口语化、有亲和力

## 核心能力
- **专业知识**：对{name}领域有深入了解
- **实战经验**：有实际使用/体验经验
- **信息筛选**：能辨别真伪，过滤营销信息
- **用户视角**：站在普通用户角度思考问题

## 语气与节奏
- **亲切自然**：像朋友聊天，不端着
- **简洁明了**：短句为主，快速传递信息
- **有立场**：明确表达观点，不模棱两可
- **口语化**：像说话，不像写文章

## 消除 AI 感的写作原则

### 禁止使用的 AI 痕迹表达
- ❌ "值得注意的是"、"值得关注的是"
- ❌ "综上所述"、"总而言之"
- ❌ "一方面...另一方面..."
- ❌ "然而"、"此外"、"另外"
- ❌ "随着...的发展"、"在...的背景下"
- ❌ 过度完整的结构（开头-发展-高潮-总结）
- ❌ 过度平衡的观点（既说优点又说缺点）
- ❌ 过度使用过渡词

### 真人创作者的表达方式
- ✅ 直接下结论："这个可以冲"、"这个建议pass"
- ✅ 用实际体验说话："用了X天，感觉是Y"
- ✅ 说人话："简单说就是X"
- ✅ 有立场：明确推荐/不推荐，不给模棱两可的观点
- ✅ 用具体场景："日常使用场景下，X体验更好"

### 句式特点
- 不用完整的关联词，直接说下句
- 用破折号、冒号代替"因为"、"所以"
- 用反问句表达观点
- 用简短的判断句

## 小红书内容结构

### 0. 输出格式要求（重要！）

**必须输出纯文本，可以直接粘贴到小红书：**
- ❌ 禁止 HTML 标签（如 `<b>`、`</b>`、`<br>` 等）
- ❌ 禁止 Markdown 加粗语法（如 `**文字**`）
- ❌ 禁止任何代码格式化标记
- ✅ 只输出纯文本，用换行分隔段落
- ✅ 标题和正文之间用空行分隔
- ✅ 话题标签用 `#` 开头

### 1. 标题（≤20字）
- 直接观点 + 关键信息

### 2. 开篇（1-2句）
- 直接抛结论，不要铺垫

### 3. 正文（3-5段）
- **观点层**：表达明确观点
- **体验层**：实际使用感受
- **建议层**：购买/使用建议
- 段落之间用空行分隔

### 4. 关注引导（自然）

### 5. 话题标签（5-8个）
- 格式：`#标签1 #标签2`

## 可复用句式（真人感）

### 开头
- "直接说结论"
- "这事儿没那么复杂"
- "简单说就是：X"

### 分析
- "从实际体验看"
- "用了X天，感觉是Y"
- "关键点是X"

### 判断
- "这个可以冲"
- "这个建议pass"
- "看个人需求"

### 反问
- "这种参数看着唬人？实际体验告诉你"

## 禁忌
- ❌ 编造数据
- ❌ 过度修饰、华丽辞藻
- ❌ 模棱两可的表达
- ❌ AI 痕迹的过渡词和总结
- ❌ "值得注意的是"之类的废话
- ❌ 过度完整平衡的结构

## 自然关注引导
- "关注我，持续分享干货"
- "一起学习，一起进步"
- "有用的话点个赞"
"""
    return content


def bootstrap_vertical(code: str, name: str, mode: str = "strict", keywords: list = None):
    """
    创建新垂类

    Args:
        code: 垂类代码
        name: 垂类名称
        mode: 生成模式
        keywords: 关键词列表
    """
    skill_dir = get_skill_dir()

    # 验证输入
    if not code.isalnum():
        print(f"错误: 垂类代码只能包含字母和数字")
        return False

    if mode not in ("strict", "advanced"):
        print(f"错误: 生成模式必须是 strict 或 advanced")
        return False

    # 创建配置文件
    verticals_dir = os.path.join(skill_dir, 'verticals')
    config_path = os.path.join(verticals_dir, f'{code}.json')

    if os.path.exists(config_path):
        print(f"警告: 垂类 {code} 已存在，将覆盖现有文件")
        response = input("是否继续？(y/n): ")
        if response.lower() != 'y':
            return False

    config = create_vertical_config(code, name, mode, keywords)
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"✓ 配置文件已创建: {config_path}")

    # 创建人设文件
    personas_dir = os.path.join(skill_dir, 'personas')
    os.makedirs(personas_dir, exist_ok=True)
    persona_path = os.path.join(personas_dir, f'{code}.md')

    persona_content = create_persona_content(code, name)
    with open(persona_path, 'w', encoding='utf-8') as f:
        f.write(persona_content)

    print(f"✓ 人设文件已创建: {persona_path}")

    # 验证配置
    from config_parser import VerticalConfig
    test_config = VerticalConfig.load(code, skill_dir)
    is_valid, errors = test_config.validate()

    if is_valid:
        print(f"✓ 配置验证通过")
    else:
        print(f"⚠ 配置验证发现问题:")
        for error in errors:
            print(f"  - {error}")

    print(f"\n垂类 {code} ({name}) 创建完成！")
    print(f"生成模式: {mode}")
    print(f"\n下一步:")
    print(f"1. 编辑配置文件: {config_path}")
    print(f"2. 编辑人设文件: {persona_path}")
    print(f"3. 测试生成: ~/.openclaw/bin/xhs-do {code} '测试话题'")

    return True


def interactive_bootstrap():
    """交互式创建垂类"""
    print("=== 小红书垂类引导器 ===\n")

    code = input("垂类代码 (英文，如 finance): ").strip()
    if not code:
        print("错误: 垂类代码不能为空")
        return

    name = input("垂类名称 (中文，如 金融): ").strip()
    if not name:
        print("错误: 垂类名称不能为空")
        return

    print("\n生成模式:")
    print("  1. strict - 严格模式 (简单模板，保持兼容)")
    print("  2. advanced - 高级模式 (完整配置，精细化内容)")
    mode_input = input("选择模式 (1/2，默认1): ").strip()

    mode = "strict" if mode_input in ("", "1") else "advanced"

    keywords_input = input("关键词 (逗号分隔，可选): ").strip()
    keywords = [k.strip() for k in keywords_input.split(",")] if keywords_input else []

    print(f"\n创建垂类: {code} ({name})")
    print(f"生成模式: {mode}")
    if keywords:
        print(f"关键词: {', '.join(keywords)}")

    confirm = input("\n确认创建？(y/n): ").strip().lower()
    if confirm == 'y':
        bootstrap_vertical(code, name, mode, keywords)
    else:
        print("已取消")


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description='小红书垂类引导器')
    parser.add_argument('code', nargs='?', help='垂类代码')
    parser.add_argument('name', nargs='?', help='垂类名称')
    parser.add_argument('mode', nargs='?', default='strict', choices=['strict', 'advanced'], help='生成模式')
    parser.add_argument('-i', '--interactive', action='store_true', help='交互式模式')
    parser.add_argument('-k', '--keywords', help='关键词（逗号分隔）')

    args = parser.parse_args()

    if args.interactive or not args.code:
        interactive_bootstrap()
    else:
        keywords = [k.strip() for k in args.keywords.split(",")] if args.keywords else None
        bootstrap_vertical(args.code, args.name, args.mode, keywords)


if __name__ == '__main__':
    main()
