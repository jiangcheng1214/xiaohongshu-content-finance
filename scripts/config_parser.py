#!/usr/bin/env python3
"""
垂类配置解析器
负责加载和解析垂类配置文件，提供统一的配置访问接口
"""
import json
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class VerticalConfig:
    """垂类配置数据类"""

    # 基础配置
    code: str = ""
    name: str = ""
    generation_mode: str = "strict"  # strict 或 advanced
    persona_id: str = ""
    keywords: List[str] = field(default_factory=list)

    # 搜索策略
    search_strategy: Dict[str, Any] = field(default_factory=dict)

    # 研究维度
    research_dimensions: List[Dict[str, Any]] = field(default_factory=list)

    # 内容结构
    content_structure: Dict[str, Any] = field(default_factory=dict)

    # 标题模板
    title_template: Dict[str, Any] = field(default_factory=dict)

    # 封面配置
    cover_config: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, vertical: str, skill_dir: Optional[str] = None) -> 'VerticalConfig':
        """
        加载垂类配置

        Args:
            vertical: 垂类代码 (如 finance, beauty, tech)
            skill_dir: 技能目录路径，默认自动检测

        Returns:
            VerticalConfig 实例
        """
        if skill_dir is None:
            skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        config_path = os.path.join(skill_dir, 'verticals', f'{vertical}.json')

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            # 返回默认配置
            return cls()
        except json.JSONDecodeError:
            return cls()

        return cls(
            code=data.get('code', vertical),
            name=data.get('name', ''),
            generation_mode=data.get('generation_mode', 'strict'),
            persona_id=data.get('persona_id', ''),
            keywords=data.get('keywords', []),
            search_strategy=data.get('search_strategy', {}),
            research_dimensions=data.get('research_dimensions', []),
            content_structure=data.get('content_structure', {}),
            title_template=data.get('title_template', {}),
            cover_config=data.get('cover_config', {})
        )

    def get_generation_mode(self) -> str:
        """获取生成模式"""
        return self.generation_mode

    def get_content_structure(self) -> Dict[str, Any]:
        """获取内容结构配置"""
        return self.content_structure

    def get_paragraphs(self) -> List[Dict[str, Any]]:
        """获取段落配置列表"""
        return self.content_structure.get('paragraphs', [])

    def get_research_dimensions(self) -> List[Dict[str, Any]]:
        """获取研究维度列表"""
        return self.research_dimensions

    def get_dimension_fields(self, dimension_name: str) -> List[str]:
        """获取指定维度的字段列表"""
        for dim in self.research_dimensions:
            if dim.get('name') == dimension_name:
                return dim.get('fields', [])
        return []

    def get_title_templates(self) -> List[str]:
        """获取标题模板列表"""
        return self.title_template.get('patterns', [])

    def get_title_max_length(self) -> int:
        """获取标题最大长度"""
        return self.title_template.get('max_length', 20)

    def get_title_style(self) -> str:
        """获取标题风格"""
        return self.title_template.get('style', '')

    def get_default_subtitle(self) -> str:
        """获取默认副标题"""
        return self.cover_config.get('default_subtitle', '分享')

    def get_color_schemes(self) -> List[str]:
        """获取配色方案列表"""
        return self.cover_config.get('color_schemes', [])

    def requires_risk_warning(self) -> bool:
        """是否需要风险提示"""
        return self.content_structure.get('requires_risk_warning', False)

    def requires_data_timestamp(self) -> bool:
        """是否需要数据时间戳"""
        return self.content_structure.get('requires_data_timestamp', False)

    def requires_sources(self) -> bool:
        """是否需要数据来源"""
        return self.content_structure.get('requires_sources', False)

    def get_min_length(self) -> int:
        """获取内容最小长度"""
        return self.content_structure.get('min_length', 300)

    def get_max_length(self) -> int:
        """获取内容最大长度"""
        return self.content_structure.get('max_length', 800)

    def get_search_queries(self, topic: str) -> List[str]:
        """
        根据话题生成搜索查询

        Args:
            topic: 用户输入的话题

        Returns:
            搜索查询列表
        """
        templates = self.search_strategy.get('search_queries_template', [])
        queries = []
        for template in templates:
            queries.append(template.replace('{topic}', topic))
        return queries

    def validate(self) -> tuple[bool, List[str]]:
        """
        验证配置完整性

        Returns:
            (是否有效, 错误信息列表)
        """
        errors = []

        if not self.code:
            errors.append("缺少 code 字段")

        if not self.name:
            errors.append("缺少 name 字段")

        if self.generation_mode not in ('strict', 'advanced'):
            errors.append(f"无效的 generation_mode: {self.generation_mode}")

        if self.generation_mode == 'advanced':
            # 高级模式需要更完整的配置
            if not self.content_structure:
                errors.append("高级模式需要 content_structure 配置")

            if not self.research_dimensions:
                errors.append("高级模式需要 research_dimensions 配置")

            if not self.title_template:
                errors.append("高级模式需要 title_template 配置")

        return len(errors) == 0, errors


def list_verticals(skill_dir: Optional[str] = None) -> List[str]:
    """
    列出所有可用的垂类

    Args:
        skill_dir: 技能目录路径

    Returns:
        垂类代码列表
    """
    if skill_dir is None:
        skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    verticals_dir = os.path.join(skill_dir, 'verticals')

    if not os.path.exists(verticals_dir):
        return []

    verticals = []
    for file in os.listdir(verticals_dir):
        if file.endswith('.json'):
            verticals.append(file[:-5])

    return sorted(verticals)


def main():
    """命令行接口"""
    import sys

    if len(sys.argv) < 2:
        print("用法: config_parser.py <vertical> [action]")
        print("Actions:")
        print("  validate  - 验证配置 (默认)")
        print("  info      - 显示配置信息")
        print("  list      - 列出所有垂类 (无需vertical参数)")
        sys.exit(1)

    # 检查是否是 list 命令
    if sys.argv[1] == 'list':
        verticals = list_verticals()
        print("可用垂类:")
        for v in verticals:
            config = VerticalConfig.load(v)
            mode = config.get_generation_mode()
            print(f"  - {v} ({config.name}) [{mode}]")
        sys.exit(0)

    vertical = sys.argv[1]
    action = sys.argv[2] if len(sys.argv) > 2 else 'validate'

    if action == 'list':
        verticals = list_verticals()
        print("可用垂类:")
        for v in verticals:
            config = VerticalConfig.load(v)
            mode = config.get_generation_mode()
            print(f"  - {v} ({config.name}) [{mode}]")
        sys.exit(0)

    config = VerticalConfig.load(vertical)

    if action == 'info':
        print(f"垂类: {config.code} ({config.name})")
        print(f"生成模式: {config.generation_mode}")
        print(f"人设: {config.persona_id}")
        print(f"关键词: {', '.join(config.keywords)}")
        print(f"研究维度: {len(config.research_dimensions)} 个")
        print(f"段落结构: {len(config.get_paragraphs())} 个")
        print(f"标题模板: {len(config.get_title_templates())} 个")
        print(f"需要风险提示: {config.requires_risk_warning()}")
        print(f"需要时间戳: {config.requires_data_timestamp()}")

    elif action == 'validate':
        is_valid, errors = config.validate()
        if is_valid:
            print(f"✓ {vertical} 配置有效")
            sys.exit(0)
        else:
            print(f"✗ {vertical} 配置有误:")
            for error in errors:
                print(f"  - {error}")
            sys.exit(1)


if __name__ == '__main__':
    main()
