#!/usr/bin/env python3
"""
人设规范应用器
负责加载人设文件并将人设规范应用到生成的内容中
"""
import os
import re
from typing import Dict, List, Optional, Set


class PersonaApplier:
    """人设规范应用器"""

    # AI 痕迹词库（需要移除的表达）
    AI_PATTERNS = [
        r'值得注意的是[，,]?',
        r'值得关注的是[，,]?',
        r'综上所述[，,]?',
        r'总而言之[，,]?',
        r'然而[，,]?',
        r'此外[，,]?',
        r'另外[，,]?',
        r'随着[^，。]+的发展[，,]?',
        r'在[^，。]+的背景下[，,]?',
        r'一方面[^。]+。[^。]+另一方面[^。]+。',
    ]

    def __init__(self, vertical: str, skill_dir: Optional[str] = None):
        """
        初始化人设应用器

        Args:
            vertical: 垂类代码
            skill_dir: 技能目录路径
        """
        self.vertical = vertical
        if skill_dir is None:
            skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self.persona_path = os.path.join(skill_dir, 'personas', f'{vertical}.md')
        self.persona_text = self._load_persona()
        self._parse_persona()

    def _load_persona(self) -> str:
        """加载人设文件"""
        try:
            with open(self.persona_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def _parse_persona(self):
        """解析人设文件，提取关键信息"""
        self.reusable_phrases: Dict[str, List[str]] = {
            'opening': [],
            'analysis': [],
            'judgment': [],
            'risk': [],
            'question': []
        }

        self.forbidden_phrases: Set[str] = set()

        # 解析可复用句式
        current_section = None
        for line in self.persona_text.split('\n'):
            line = line.strip()
            if not line:
                continue

            # 检测章节
            if line.startswith('### 开头'):
                current_section = 'opening'
            elif line.startswith('### 分析') or line.startswith('### 判断'):
                current_section = 'analysis' if '分析' in line else 'judgment'
            elif line.startswith('### 风险'):
                current_section = 'risk'
            elif line.startswith('### 反问'):
                current_section = 'question'
            elif line.startswith('- "'):
                # 提取句式
                phrase = line.split('"')[1] if '"' in line else ''
                if phrase and current_section:
                    self.reusable_phrases[current_section].append(phrase)

        # 解析禁止使用的表达
        for line in self.persona_text.split('\n'):
            if line.strip().startswith('- ❌'):
                # 提取禁止词
                forbidden = line.split('❌')[1].strip().split('：')[0].strip()
                if forbidden:
                    self.forbidden_phrases.add(forbidden)

    def remove_ai_patterns(self, text: str) -> str:
        """
        移除 AI 痕迹表达

        Args:
            text: 原始文本

        Returns:
            移除 AI 痕迹后的文本
        """
        result = text
        for pattern in self.AI_PATTERNS:
            result = re.sub(pattern, '', result)
        return result

    def apply_sentence_style(self, text: str) -> str:
        """
        应用句式特点

        Args:
            text: 原始文本

        Returns:
            应用句式后的文本
        """
        # 移除过度的关联词
        text = re.sub(r'([，。])不仅([^，。]+)，而且\2', r'\1\2', text)
        text = re.sub(r'([，。])虽然([^，。]+)，但是\2', r'\1\2，不过\2', text)

        # 简化表达
        text = text.replace('能够', '能')
        text = text.replace('需要进行', '要')
        text = text.replace('进行', '')

        return text

    def ensure_output_format(self, text: str) -> str:
        """
        确保输出格式符合小红书要求

        Args:
            text: 原始文本

        Returns:
            格式化后的文本
        """
        # 移除 Markdown 加粗
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)

        # 移除 HTML 标签
        text = re.sub(r'<[^>]+>', '', text)

        # 清理多余空行
        text = re.sub(r'\n{3,}', '\n\n', text)

        # 确保话题标签格式正确
        text = re.sub(r'#(\S+)', r'#\1', text)

        return text.strip()

    def get_reusable_phrase(self, category: str) -> Optional[str]:
        """
        获取可复用句式

        Args:
            category: 句式类别 (opening, analysis, judgment, risk, question)

        Returns:
            随机返回一个句式，如果没有则返回 None
        """
        import random
        phrases = self.reusable_phrases.get(category, [])
        return random.choice(phrases) if phrases else None

    def apply_tone(self, text: str) -> str:
        """
        应用语气转换

        Args:
            text: 原始文本

        Returns:
            应用语气后的文本
        """
        # 根据不同垂类应用不同的语气调整
        if self.vertical == 'finance':
            # 金融：直接、坚定
            text = text.replace('可能', '')
            text = text.replace('或许', '')
            text = text.replace('大概', '')
            text = text.replace('我认为', '')
        elif self.vertical == 'beauty':
            # 美妆：亲切、真实
            text = text.replace('因此', '所以')
            text = text.replace('此外', '而且')
        elif self.vertical == 'tech':
            # 科技：专业、客观
            pass

        return text

    def apply_all(self, text: str) -> str:
        """
        应用所有人设转换

        Args:
            text: 原始文本

        Returns:
            转换后的文本
        """
        # 按顺序应用各项转换
        result = text
        result = self.remove_ai_patterns(result)
        result = self.apply_tone(result)
        result = self.apply_sentence_style(result)
        result = self.ensure_output_format(result)

        return result

    def get_content_requirements(self) -> Dict[str, any]:
        """
        获取内容要求

        Returns:
            内容要求字典
        """
        requirements = {
            'requires_risk_warning': False,
            'requires_data_timestamp': False,
            'requires_sources': False,
            'max_title_length': 20,
            'tag_count': '5-8'
        }

        # 从人设文件中提取要求
        if '输出格式要求' in self.persona_text:
            # 解析格式要求
            if '纯文本' in self.persona_text:
                requirements['plain_text_only'] = True

        return requirements


def main():
    """命令行接口"""
    import sys

    if len(sys.argv) < 2:
        print("用法: persona_applier.py <vertical> [text]")
        sys.exit(1)

    vertical = sys.argv[1]
    text = sys.argv[2] if len(sys.argv) > 2 else "这是一个测试文本，值得注意的是，这种表达很AI。综上所述，需要改进。"

    applier = PersonaApplier(vertical)

    print(f"=== 人设应用器: {vertical} ===")
    print(f"\n原始文本:")
    print(text)

    result = applier.apply_all(text)

    print(f"\n处理后文本:")
    print(result)

    print(f"\n可复用句式:")
    for category, phrases in applier.reusable_phrases.items():
        if phrases:
            print(f"  {category}: {', '.join(phrases[:3])}")


if __name__ == '__main__':
    main()
