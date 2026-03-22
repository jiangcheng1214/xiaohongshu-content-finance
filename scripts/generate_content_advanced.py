#!/usr/bin/env python3
"""
高级内容生成器 - 使用完整配置
基于垂类配置和人设规范生成精细化的内容
"""
import sys
import json
import os
import random
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# 导入配置解析器和人设应用器
from config_parser import VerticalConfig
from persona_applier import PersonaApplier


class AdvancedContentGenerator:
    """高级内容生成器"""

    def __init__(self, vertical: str, skill_dir: Optional[str] = None):
        """
        初始化生成器

        Args:
            vertical: 垂类代码
            skill_dir: 技能目录路径
        """
        self.vertical = vertical
        if skill_dir is None:
            skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self.skill_dir = skill_dir
        self.config = VerticalConfig.load(vertical, skill_dir)
        self.persona = PersonaApplier(vertical, skill_dir)

    def generate_title(self, topic: str) -> str:
        """
        生成标题

        Args:
            topic: 用户话题

        Returns:
            生成的标题
        """
        templates = self.config.get_title_templates()

        if not templates:
            # 默认模板
            return topic[:self.config.get_title_max_length()]

        # 选择一个模板
        template = random.choice(templates)

        # 替换占位符
        title = template.replace('{topic}', topic)
        title = title.replace('{ticker}', topic.split()[0] if topic.split() else topic)

        # 尝试提取核心观点（简单处理）
        if '{核心观点}' in title or '{关键词}' in title:
            # 简单提取关键词
            keywords = topic.split()
            if keywords:
                title = title.replace('{核心观点}', keywords[0])
                title = title.replace('{关键词}', keywords[0])

        if '{类比对象}' in title:
            title = title.replace('{类比对象}', '下一个机会')

        if '{产品}' in title:
            title = title.replace('{产品}', topic)

        if '{天数}' in title:
            title = title.replace('{天数}', str(random.randint(3, 30)))

        if '说人话：' in title:
            title = title.replace('说人话：', '')

        # 截断到最大长度
        max_len = self.config.get_title_max_length()
        if len(title) > max_len:
            title = title[:max_len - 1] + '…'

        return title

    def generate_paragraph(self, paragraph_config: Dict, topic: str) -> str:
        """
        生成单个段落

        Args:
            paragraph_config: 段落配置
            topic: 用户话题

        Returns:
            生成的段落文本
        """
        p_type = paragraph_config.get('type', 'body')
        name = paragraph_config.get('name', '')
        instruction = paragraph_config.get('instruction', '')
        length = paragraph_config.get('length', '')

        # 根据段落类型和指令生成内容
        if p_type == 'hook':
            return self._generate_hook(topic, instruction)
        elif p_type == 'cta':
            return self._generate_cta(instruction)
        elif p_type == 'tags':
            return self._generate_tags()
        else:
            return self._generate_body(topic, name, instruction, length)

    def _generate_hook(self, topic: str, instruction: str) -> str:
        """生成开篇钩子"""
        # 尝试使用人设中的开头句式
        phrase = self.persona.get_reusable_phrase('opening')
        if phrase:
            return phrase

        # 默认钩子
        hooks = [
            f"先别急，看看数据。",
            f"直接说结论。",
            f"数据摆在那。",
            f"这事儿没那么简单。",
        ]
        return random.choice(hooks)

    def _generate_cta(self, instruction: str) -> str:
        """生成关注引导"""
        ctas = [
            "跟我一起提高深度思考能力",
            "摒弃财富密码思维，多数人知道的密码就不是密码了",
            "一起学习进化，赶上AI迭代的速度",
            "关注我，持续分享干货",
        ]
        return random.choice(ctas)

    def _generate_tags(self) -> str:
        """生成话题标签"""
        # 使用配置中的关键词
        keywords = self.config.keywords[:8]
        tags = [f"#{kw}" for kw in keywords]

        # 添加通用标签
        common_tags = ["#分享", "#干货"]
        tags.extend(common_tags)

        # 随机选择 5-8 个
        count = random.randint(5, 8)
        selected = random.sample(tags[:10], min(count, len(tags)))

        return ' '.join(selected)

    def _generate_body(self, topic: str, name: str, instruction: str, length: str) -> str:
        """生成正文段落"""
        # 根据垂类和段落名称生成内容
        if self.vertical == 'finance':
            return self._generate_finance_body(topic, name, instruction)
        elif self.vertical == 'tech':
            return self._generate_tech_body(topic, name, instruction)
        elif self.vertical == 'beauty':
            return self._generate_beauty_body(topic, name, instruction)
        else:
            return self._generate_generic_body(topic, name, instruction)

    def _generate_finance_body(self, topic: str, name: str, instruction: str) -> str:
        """生成金融类正文段落"""
        content_map = {
            "核心观点": f"{topic} 这个话题，最近关注度确实在上升。但投资决策不能只看热度，要看基本面。",
            "财务数据": f"关键数据点：营收增速、EPS、同比增长率。这些指标直接反映公司健康状况。",
            "业务拆解": f"哪个业务在涨，为什么，占比多少。这是理解公司价值的关键。",
            "估值分析": f"贵不贵，跟同类比，历史分位。现在的价格位置决定安全边际。",
            "催化剂风险": f"什么会推动/拖累股价。利好利空都要考虑，时间节点很重要。",
            "实战建议": f"这对交易意味着什么。什么时候买卖，仓位多少，止损位置在哪。",
        }
        return content_map.get(name, f"{name}需要结合{topic}的具体情况分析。")

    def _generate_tech_body(self, topic: str, name: str, instruction: str) -> str:
        """生成科技类正文段落"""
        content_map = {
            "产品定位": f"{topic} 这个产品，定位明确，价格适中。",
            "核心参数": f"处理器、内存、屏幕这些核心参数决定了使用体验。跑分只是参考，实际体验更重要。",
            "实际体验": f"流畅度、续航、信号。这些日常使用感受比参数更实在。",
            "竞品对比": f"和同类产品比，各有优势。看你的使用场景和预算。",
            "价格分析": f"值不值，看性价比。同类产品价格差异不大，关键是看需求匹配。",
            "购买建议": f"适合谁，什么时候买。不追新，等降价或者等评测。",
        }
        return content_map.get(name, f"{name}需要看{topic}的具体表现。")

    def _generate_beauty_body(self, topic: str, name: str, instruction: str) -> str:
        """生成美妆类正文段落"""
        content_map = {
            "产品定位": f"{topic} 这个产品，品牌靠谱，价格适中。",
            "质地体验": f"质地、延展性、上脸感受。这些直接决定使用体验。",
            "效果表现": f"实际效果、持妆度、遮瑕力。看真实测评，别光看宣传。",
            "肤质适配": f"什么肤质适合/不适合。干皮油皮敏感肌，选择不同。",
            "性价比": f"值不值，有平替吗。同类产品很多，对比后再决定。",
            "购买建议": f"推荐/不推荐，适合谁。先小样试用，再决定正装。",
        }
        return content_map.get(name, f"{name}要看{topic}的具体情况。")

    def _generate_generic_body(self, topic: str, name: str, instruction: str) -> str:
        """生成通用正文段落"""
        return f"{name}：关于{topic}，需要具体分析。"

    def fill_dimensions(self, topic: str) -> List[str]:
        """
        填充研究维度

        Args:
            topic: 用户话题

        Returns:
            维度内容列表
        """
        dimensions = self.config.get_research_dimensions()
        filled = []

        for dim in dimensions:
            name = dim.get('name', '')
            fields = dim.get('fields', [])

            if fields:
                # 有具体字段的维度
                field_list = '、'.join(fields[:3])
                filled.append(f"**{name}**\n{field_list}等指标需要关注。")
            else:
                # 无具体字段的维度
                filled.append(f"**{name}**\n需要结合{topic}具体分析。")

        return filled

    def apply_requirements(self, content: str) -> str:
        """
        添加特殊要求（风险提示、时间戳等）

        Args:
            content: 原始内容

        Returns:
            添加要求后的内容
        """
        additions = []

        if self.config.requires_risk_warning():
            additions.append("\n**风险提示**\n以上分析仅供参考，市场有风险，投资需谨慎。")

        if self.config.requires_data_timestamp():
            additions.append(f"\n数据时间：{datetime.now().strftime('%Y年%m月%d日')}")

        if self.config.requires_sources():
            additions.append("\n数据来源：公开资料整理")

        return content + ''.join(additions)

    def generate(self, topic: str) -> Tuple[str, str]:
        """
        生成完整内容

        Args:
            topic: 用户话题

        Returns:
            (内容文本, 副标题)
        """
        # 生成标题
        title = self.generate_title(topic)

        # 获取段落配置
        paragraphs_config = self.config.get_paragraphs()

        # 按顺序生成段落
        content_parts = [f"# {title}\n"]

        for p_config in sorted(paragraphs_config, key=lambda x: x.get('order', 0)):
            paragraph = self.generate_paragraph(p_config, topic)
            if paragraph:
                content_parts.append(paragraph)

        # 合并内容
        content = '\n\n'.join(content_parts)

        # 应用特殊要求
        content = self.apply_requirements(content)

        # 应用人设规范
        content = self.persona.apply_all(content)

        # 获取副标题
        subtitle = self.config.get_default_subtitle()

        return content, subtitle


def generate_content_advanced(topic: str, vertical: str) -> Tuple[str, str]:
    """
    高级内容生成入口函数

    Args:
        topic: 用户话题
        vertical: 垂类代码

    Returns:
        (内容文本, 副标题)
    """
    generator = AdvancedContentGenerator(vertical)
    return generator.generate(topic)


def main():
    """命令行接口"""
    if len(sys.argv) < 4:
        print(json.dumps({"error": "用法: generate_content_advanced.py <topic> <vertical> <output_file>"}))
        sys.exit(1)

    topic = sys.argv[1]
    vertical = sys.argv[2]
    output_file = sys.argv[3]

    # 生成内容
    try:
        content, subtitle = generate_content_advanced(topic, vertical)

        # 保存
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)

        # 输出结果
        result = {
            "topic": topic,
            "vertical": vertical,
            "subtitle": subtitle,
            "output_file": output_file,
            "content_length": len(content),
            "mode": "advanced"
        }

        print(json.dumps(result, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
