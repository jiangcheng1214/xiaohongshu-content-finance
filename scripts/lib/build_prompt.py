#!/usr/bin/env python3
"""
Prompt 模板加载和变量替换
用法: build_prompt.py <vertical_config> <persona_file> <topic> <vertical> <template_file>
"""

import json
import sys
import os
from datetime import datetime


def load_vertical_config(config_path):
    """加载垂类配置"""
    with open(config_path, 'r') as f:
        return json.load(f)


def load_persona(persona_file):
    """加载人设文件"""
    if not persona_file or not os.path.exists(persona_file):
        return ""
    with open(persona_file, 'r') as f:
        return f.read()


def generate_vertical_config_section(config):
    """生成垂类配置部分"""
    lines = ["## 垂类配置"]
    lines.append(f"垂类: {config.get('name', '')}")
    lines.append(f"生成模式: {config.get('generation_mode', 'strict')}")
    lines.append("")

    # 内容结构要求
    structure = config.get('content_structure', {})
    lines.append("### 内容结构要求")
    lines.append(f"最小长度: {structure.get('min_length', 300)}字")
    lines.append(f"最大长度: {structure.get('max_length', 600)}字")
    lines.append("")

    # 段落配置
    paragraphs = structure.get('paragraphs', [])
    if paragraphs:
        lines.append("### 段落结构")
        for p in paragraphs:
            order = p.get('order', 0)
            p_type = p.get('type', 'body')
            name = p.get('name', '')
            length = p.get('length', '')
            instruction = p.get('instruction', '')
            lines.append(f"{order}. [{p_type}] {name} - {length}")
            lines.append(f"   指令: {instruction}")
        lines.append("")

    # 特殊要求
    if structure.get('requires_risk_warning'):
        lines.append("### 要求: 需要风险提示")
    if structure.get('requires_data_timestamp'):
        lines.append("### 要求: 需要数据时间戳")
    if structure.get('requires_sources'):
        lines.append("### 要求: 需要数据来源")
    lines.append("")

    # 标题指导
    title_guidance = config.get('title_guidance', {})
    if title_guidance:
        lines.append("### 标题创作指导")
        main = title_guidance.get('main_title', {})
        sub = title_guidance.get('subtitle', {})
        lines.append(f"主标题：{main.get('length', '4-8字')}，{main.get('style', '')}")
        lines.append(f"副标题：{sub.get('length', '8-15字')}，{sub.get('style', '')}")
        lines.append("")
        lines.append("参考示例（仅供参考，请根据话题自由创作）：")

        main_examples = main.get('examples', [])[:3]
        sub_examples = sub.get('examples', [])[:3]
        if main_examples:
            lines.append("主标题参考：")
            for ex in main_examples:
                lines.append(f"  • {ex}")
        if sub_examples:
            lines.append("副标题参考：")
            for ex in sub_examples:
                lines.append(f"  • {ex}")

    return "\n".join(lines)


def generate_persona_section(persona_content):
    """生成人设部分"""
    if not persona_content:
        return ""
    return f"## 人设规范\n{persona_content}"


def generate_search_instruction(vertical, topic):
    """生成搜索指令 - 根据不同垂类生成精确的搜索查询"""
    current_year = datetime.now().year
    current_month = datetime.now().month

    instructions = {
        'stock': f"""【🚨最高优先级指令：在动笔创作前，你必须调用你的 Web 联网搜索工具检索以下内容（必须按顺序执行）】

第1步：核实股票代码有效性
搜索查询："{topic} stock current status {current_year}"
目的：确认该股票代码是否仍在交易，是否已被并购、退市或更名。如主体已变更，必须在内容中明确指出。

第2步：获取最新行情和财报
搜索查询："{topic} stock price today latest news earnings {current_year}"
目的：获取今日股价、涨跌幅、最新季度财报数据

第3步：获取最新催化剂
搜索查询："{topic} stock news today catalyst {current_year}"
目的：获取今日或本周影响股价的最新新闻、催化剂事件

【关键要求】
- 所有数据必须来自搜索结果，绝不允许编造股价、财报或新闻
- 如搜索到主体变更（如并购、退市），必须在内容开头明确说明
- 必须在内容中注明数据来源时间（如"截至{current_year}年X月X日"）""",

        'finance': f"""【🚨最高优先级指令：在动笔创作前，你必须调用你的 Web 联网搜索工具检索以下内容】

搜索查询："{topic} latest news today {current_year}"
目的：获取关于"{topic}"的最新市场动态、数据或政策进展

【关键要求】
- 所有数据必须来自搜索结果的最新信息
- 必须在内容中注明数据时间戳
- 如无最新数据，请明确说明""",

        'tech': f"""【🚨最高优先级指令：在动笔创作前，你必须调用你的 Web 联网搜索工具检索以下内容】

搜索查询："{topic} review latest {current_year}"
目的：获取关于"{topic}"的最新评测、参数或发布信息

【关键要求】
- 产品信息必须是最新的，如产品已更新换代，请说明当前版本
- 价格信息仅供参考，请说明获取时间""",

        'beauty': f"""【🚨最高优先级指令：在动笔创作前，你必须调用你的 Web 联网搜索工具检索以下内容】

搜索查询："{topic} review latest {current_year}"
目的：获取关于"{topic}"的最新测评、使用体验

【关键要求】
- 产品信息必须是最新的
- 效果描述基于真实测评，非编造"""
    }

    return instructions.get(vertical, f"""【🚨最高优先级指令：在动笔创作前，你必须调用你的 Web 联网搜索工具检索 "{topic} latest {current_year}" 的最新信息】""")


def render_template(template_path, vertical_config_section, persona_content, topic, vertical, search_instruction):
    """渲染模板"""
    with open(template_path, 'r') as f:
        template = f.read()

    # 变量替换
    replacements = {
        '{{VERTICAL_CONFIG}}': vertical_config_section,
        '{{PERSONA_CONTENT}}': persona_content,
        '{{TOPIC}}': topic,
        '{{VERTICAL}}': vertical,
        '{{SEARCH_INSTRUCTION}}': search_instruction,
    }

    for key, value in replacements.items():
        template = template.replace(key, value)

    return template


def main():
    if len(sys.argv) < 5:
        print("用法: build_prompt.py <vertical_config> <persona_file> <topic> <vertical> [template_file]", file=sys.stderr)
        sys.exit(1)

    vertical_config_path = sys.argv[1]
    persona_file = sys.argv[2] if sys.argv[2] != 'None' else None
    topic = sys.argv[3]
    vertical = sys.argv[4]
    template_file = sys.argv[5] if len(sys.argv) > 5 else None

    # 加载配置
    config = load_vertical_config(vertical_config_path)
    persona_content = load_persona(persona_file)

    # 生成各部分内容
    vertical_config_section = generate_vertical_config_section(config)
    persona_section = generate_persona_section(persona_content)
    search_instruction = generate_search_instruction(vertical, topic)

    # 确定模板文件
    if not template_file or not os.path.exists(template_file):
        # 优先级：垂类配置中的模板 > 垂类专属模板 > 通用模板
        custom_template = config.get('content_prompt_template')
        skill_dir = os.path.dirname(os.path.dirname(vertical_config_path))

        if custom_template:
            if os.path.isabs(custom_template):
                template_file = custom_template
            else:
                template_file = os.path.join(skill_dir, custom_template)
        elif os.path.exists(os.path.join(skill_dir, 'templates', f'{vertical}_prompt.txt')):
            template_file = os.path.join(skill_dir, 'templates', f'{vertical}_prompt.txt')
        else:
            template_file = os.path.join(skill_dir, 'templates', 'content_prompt.txt')

    # 渲染并输出
    if os.path.exists(template_file):
        result = render_template(template_file, vertical_config_section, persona_section, topic, vertical, search_instruction)
        print(result)
    else:
        print(f"错误: 模板文件不存在: {template_file}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
