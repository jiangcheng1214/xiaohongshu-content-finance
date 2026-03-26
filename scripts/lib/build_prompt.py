#!/usr/bin/env python3
"""
Prompt 模板加载和变量替换
用法: build_prompt.py <vertical_config> <persona_file> <topic> <vertical> <template_file>
"""

import json
import sys
import os


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


def render_template(template_path, vertical_config_section, persona_content, topic, vertical):
    """渲染模板"""
    with open(template_path, 'r') as f:
        template = f.read()

    # 变量替换
    replacements = {
        '{{VERTICAL_CONFIG}}': vertical_config_section,
        '{{PERSONA_CONTENT}}': persona_content,
        '{{TOPIC}}': topic,
        '{{VERTICAL}}': vertical,
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
        result = render_template(template_file, vertical_config_section, persona_section, topic, vertical)
        print(result)
    else:
        print(f"错误: 模板文件不存在: {template_file}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
