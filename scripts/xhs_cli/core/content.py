"""
内容生成模块
"""

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..config import Config
from ..lib.paths import PathManager
from .session import Session


class ContentGenerator:
    """内容生成器"""

    # 备用内容模板
    FALLBACK_TEMPLATES = {
        "tech": """# {title}

直接说结论。

{topic} 这款产品，定位明确。

处理器、内存、屏幕这些核心参数决定了使用体验。跑分只是参考，实际体验更重要。

流畅度、续航、信号。这些日常使用感受比参数更实在。

和同类产品比，各有优势。看你的使用场景和预算。

值不值，看性价比。同类产品价格差异不大，关键是看需求匹配。

适合数码爱好者，参数党持续分享。

#数码 #科技 #评测
""",
        "beauty": """# {title}

直接说结论。

{topic} 这个产品，品牌靠谱，价格适中。

质地、延展性、上脸感受。这些直接决定使用体验。

实际效果、持妆度、遮瑕力。看真实测评，别光看宣传。

什么肤质适合/不适合。干皮油皮敏感肌，选择不同。

值不值，有平替吗。同类产品很多，对比后再决定。

美妆测评，持续分享每次原创。

#美妆 #护肤 #测评
""",
        "finance": """# {title}

直接说结论。

关于{topic}，数据摆在那。

具体数字、同比环比、时间戳，必须解释数据含义。

贵不贵，跟同类比，历史分位。现在的价格位置决定安全边际。

量化分析，持续分享每次原创。

⚠️ 以上仅供参考，市场有风险，投资需谨慎

#股票 #投资 #量化
""",
        "stock": """# {title}

直接说结论。

关于{topic}，需要从数据和业务两个角度看。

最新财报数据是基础，营收、利润、增长率这些硬指标摆在那。超预期还是不及预期，市场反应不会骗人。

核心业务分析看增长驱动。哪个业务在涨，为什么，护城河够不够深。行业地位决定定价权，龙头才有超额收益。

估值位置决定安全边际。PE/PB 历史分位，和同行比贵不贵。便宜不是买入理由，但好价格需要耐心等。

风险不能不提。行业风险、公司风险、估值风险，实事求是。

操作建议：买入/持有/卖出，给明确判断，不骑墙。

深度个股分析，持续分享，每次原创。

⚠️ 以上分析仅供参考，不构成投资建议

#股票 #个股分析 #财报 #投资
""",
    }

    def __init__(self, config: Config | None = None, path_manager: PathManager | None = None):
        self.config = config or Config()
        self.path_manager = path_manager or PathManager(self.config)

    def generate(self, session: Session) -> tuple[str, str, str]:
        """生成内容

        返回: (main_title, subtitle, content)
        """
        print(f"# === 内容生成 ===", file=sys.stderr)
        print(f"# Topic: {session.topic}", file=sys.stderr)
        print(f"# Vertical: {session.vertical}", file=sys.stderr)

        # 加载垂类配置和人设
        vertical_config = self._load_vertical_config(session.vertical)
        persona = self._load_persona(session.vertical)

        # 构建 prompt
        prompt = self._build_prompt(vertical_config, persona, session.topic, session.vertical)

        # 调用 Claude API
        print("# 正在调用 Claude API 生成内容...", file=sys.stderr)
        content = self._call_claude(prompt)

        # 检查是否需要使用备用模板
        if self._should_use_fallback(content):
            print("# Claude API 调用失败，使用备用模板", file=sys.stderr)
            content = self._get_fallback_content(session)

        # 解析标题和副标题
        main_title, subtitle = self._parse_titles(content)

        if not main_title or not subtitle:
            print(f"# ✗ 错误: 无法解析生成内容中的主标题和副标题", file=sys.stderr)
            raise ValueError("无法解析标题和副标题")

        print(f"# 提取到主标题: {main_title}", file=sys.stderr)
        print(f"# 提取到副标题: {subtitle}", file=sys.stderr)

        # 清理内容中的标题标记
        content = self._clean_content(content)

        # 保存内容文件
        content_file = self.path_manager.get_session_dir(session.id) / "content.md"
        content_file.write_text(content, encoding="utf-8")

        # 更新 session
        session.title = main_title
        session.subtitle = subtitle
        session.content = content
        session.status = "content_generated"
        session.steps["content"] = True
        session.content_updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # 添加 debug 信息
        session.debug = session.debug or {}
        session.debug["content"] = {
            "vertical": session.vertical,
            "topic": session.topic,
            "title": main_title,
            "subtitle": subtitle,
            "content_length": len(content),
            "word_count": len(content.split()),
            "generation_mode": vertical_config.get("generation_mode", "strict")
        }

        session.save(self.path_manager.get_session_dir(session.id))

        print(f"# ✓ 内容已保存到 session/content.md", file=sys.stderr)
        return main_title, subtitle, content

    def _load_vertical_config(self, vertical: str) -> dict:
        """加载垂类配置"""
        config_file = self.path_manager.get_verticals_dir() / f"{vertical}.json"
        if not config_file.exists():
            raise FileNotFoundError(f"垂类配置不存在: {config_file}")

        with open(config_file, encoding="utf-8") as f:
            return json.load(f)

    def _load_persona(self, vertical: str) -> str:
        """加载人设"""
        persona_file = self.path_manager.get_personas_dir() / f"{vertical}.md"
        if persona_file.exists():
            return persona_file.read_text(encoding="utf-8")
        return ""

    def _build_prompt(self, vertical_config: dict, persona: str, topic: str, vertical: str) -> str:
        """构建生成 prompt"""
        # 使用现有的 build_prompt.py 逻辑
        script_dir = self.path_manager.get_skill_dir() / "scripts"
        build_prompt_script = script_dir / "lib" / "build_prompt.py"

        if build_prompt_script.exists():
            # 调用现有的 Python 脚本
            persona_file = self.path_manager.get_personas_dir() / f"{vertical}.md"
            persona_arg = str(persona_file) if persona_file.exists() else "None"
            vertical_config_path = self.path_manager.get_verticals_dir() / f"{vertical}.json"

            try:
                result = subprocess.run(
                    ["python3", str(build_prompt_script),
                     str(vertical_config_path), persona_arg, topic, vertical],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    encoding="utf-8"
                )
                if result.returncode == 0 and result.stdout:
                    return result.stdout
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                pass

        # 回退到简单的 prompt
        return f"""请为小红书写一篇关于"{topic}"的内容。

话题: {topic}
垂类: {vertical}

人设:
{persona if persona else "专业、简洁、直接"}

要求:
1. 直接说结论，不废话
2. 内容要有干货
3. 结尾加上相关标签

输出格式:
【主标题】4-8字的主标题
【副标题】8-15字的副标题
正文内容...
"""

    def _call_claude(self, prompt: str) -> str:
        """调用 Claude CLI"""
        try:
            result = subprocess.run(
                ["claude", "--dangerously-skip-permissions", "-p", prompt],
                capture_output=True,
                text=True,
                timeout=120,
                encoding="utf-8"
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        return ""

    def _should_use_fallback(self, content: str) -> bool:
        """判断是否应该使用备用内容"""
        if not content:
            return True
        # 检查是否是错误响应
        error_indicators = [
            "我注意到你提供的话题是空的",
            "请提供产品名称",
            "I notice you provided an empty topic"
        ]
        return any(indicator in content for indicator in error_indicators)

    def _get_fallback_content(self, session: Session) -> str:
        """获取备用内容"""
        template = self.FALLBACK_TEMPLATES.get(session.vertical)
        if not template:
            # 通用备用模板
            title = f"{session.topic[:10]}分析"
            template = f"""# {title}

直接说结论。

关于{session.topic}，需要结合具体情况分析。

持续分享，每次原创。

#分享 #干货
"""

        # 生成标题
        if session.vertical == "stock":
            title = f"{session.topic[:8]}值得买吗"
        else:
            title = f"{session.topic[:10]}深度解析"

        return template.format(title=title, topic=session.topic)

    def _parse_titles(self, content: str) -> tuple[str, str]:
        """解析主标题和副标题"""
        # 尝试从标记中提取
        main_match = re.search(r"【主标题】(.+)", content)
        sub_match = re.search(r"【副标题】(.+)", content)

        main_title = main_match.group(1).strip() if main_match else ""
        subtitle = sub_match.group(1).strip() if sub_match else ""

        # 如果正则提取失败，从 Markdown 标题提取
        if not main_title or not subtitle:
            # 查找第一个 Markdown 标题（# 开头）
            lines = content.split("\n")
            markdown_headers = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("# ") and not stripped.startswith("## "):
                    # 提取标题文本（去掉 # 前缀）
                    header_text = stripped[2:].strip()
                    # 过滤掉太长的行（可能是正文中的伪标题）
                    if len(header_text) <= 30:
                        markdown_headers.append(header_text)

            # 第一个标题作为主标题，第二个作为副标题
            if len(markdown_headers) >= 1 and not main_title:
                main_title = markdown_headers[0]
            if len(markdown_headers) >= 2 and not subtitle:
                subtitle = markdown_headers[1]

        # 如果还是没找到，尝试从 **加粗** 文本提取（通常是标题）
        if not main_title or not subtitle:
            bold_matches = re.findall(r"\*\*(.+?)\*\*", content)
            # 过滤掉太长的
            bold_titles = [b for b in bold_matches if len(b) <= 30 and len(b) >= 2]
            if len(bold_titles) >= 1 and not main_title:
                main_title = bold_titles[0]
            if len(bold_titles) >= 2 and not subtitle:
                subtitle = bold_titles[1]

        return main_title, subtitle

    def _clean_content(self, content: str) -> str:
        """清理内容，移除标题标记"""
        # 移除【主标题】和【副标题】行
        content = re.sub(r"^【主标题】.+$", "", content, flags=re.MULTILINE)
        content = re.sub(r"^【副标题】.+$", "", content, flags=re.MULTILINE)
        # 移除多余的空行
        content = re.sub(r"\n{3,}", "\n\n", content)
        return content.strip()


# 导入 sys 以便使用 sys.stderr
import sys
