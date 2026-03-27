"""
跨平台配置管理器
解决硬编码路径问题
"""

import json
import os
import platform
from pathlib import Path
from typing import Optional


class Config:
    """跨平台配置管理器

    多级配置策略: 环境变量 > 配置文件 > 默认值
    """

    def __init__(self, config_path: Optional[Path] = None):
        self.system = platform.system()
        self.config_path = config_path or self._find_config()
        self._config = self._load_config()

    def _find_config(self) -> Optional[Path]:
        """查找配置文件"""
        # 1. 环境变量指定
        if env_path := os.environ.get("XHS_CONFIG"):
            return Path(env_path)

        # 2. 项目根目录
        skill_dir = self._get_skill_dir()
        config_file = skill_dir / "config.yaml"
        if config_file.exists():
            return config_file

        # 3. 用户配置目录
        user_config = Path.home() / ".config" / "xiaohongshu-smart-gen" / "config.yaml"
        return user_config if user_config.exists() else None

    def _get_skill_dir(self) -> Path:
        """自动检测技能目录"""
        # 从 __file__ 位置向上查找 SKILL.md
        return Path(__file__).parent.parent.parent

    def _load_config(self) -> dict:
        """加载配置文件"""
        if self.config_path and self.config_path.exists():
            try:
                import yaml
                with open(self.config_path, encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except ImportError:
                # yaml 未安装，返回空配置
                pass
            except Exception:
                pass
        return {}

    def get_openclaw_home(self) -> Path:
        """获取 OpenClaw 主目录"""
        if env := os.environ.get("OPENCLAW_HOME"):
            return Path(env).expanduser()
        return Path.home() / ".openclaw"

    def get_workspace(self) -> Path:
        """获取工作区目录"""
        if env := os.environ.get("XHS_WORKSPACE"):
            return Path(env).expanduser()
        return self.get_openclaw_home() / "agents" / "main" / "agent"

    def get_skill_dir(self) -> Path:
        """获取技能目录"""
        return self._get_skill_dir()

    def get_verticals_dir(self) -> Path:
        """获取垂类配置目录"""
        return self.get_skill_dir() / "verticals"

    def get_personas_dir(self) -> Path:
        """获取人设目录"""
        return self.get_skill_dir() / "personas"

    def get_assets_dir(self) -> Path:
        """获取资源目录"""
        return self.get_skill_dir() / "assets"

    def get_logo_dir(self) -> Path:
        """获取 Logo 目录"""
        return self.get_assets_dir() / "logo"

    def get_templates_dir(self) -> Path:
        """获取模板目录"""
        return self.get_skill_dir() / "templates"

    def get_gemini_api_key(self) -> Optional[str]:
        """获取 Gemini API Key (多来源)"""
        # 1. 环境变量
        if key := os.environ.get("GEMINI_API_KEY"):
            return key

        # 2. openclaw.json
        openclaw_json = self.get_openclaw_home() / "openclaw.json"
        if openclaw_json.exists():
            try:
                with open(openclaw_json, encoding="utf-8") as f:
                    config = json.load(f)
                    # 检查 env.GEMINI_API_KEY
                    if key := config.get("env", {}).get("GEMINI_API_KEY"):
                        return key
                    # 检查 skills.entries.nano-banana-pro.apiKey
                    if key := config.get("skills", {}).get("entries", {}) \
                              .get("nano-banana-pro", {}).get("apiKey"):
                        return key
            except (json.JSONDecodeError, IOError):
                pass
        return None

    def get_telegram_bot_token(self) -> Optional[str]:
        """获取 Telegram Bot Token"""
        # 1. 环境变量
        if token := os.environ.get("TELEGRAM_BOT_TOKEN"):
            return token

        # 2. openclaw.json
        openclaw_json = self.get_openclaw_home() / "openclaw.json"
        if openclaw_json.exists():
            try:
                with open(openclaw_json, encoding="utf-8") as f:
                    config = json.load(f)
                    return config.get("channels", {}).get("telegram", {}) \
                              .get("accounts", {}).get("default", {}).get("botToken")
            except (json.JSONDecodeError, IOError):
                pass
        return None

    def get_temp_dir(self) -> Path:
        """获取临时目录 (跨平台)"""
        if self.system == "Windows":
            return Path(os.environ.get("TEMP", "C:/Temp"))
        return Path("/tmp")

    def get_export_dir(self, title: str) -> Path:
        """获取导出目录 (用于发送前整理)"""
        from datetime import datetime

        if self.system == "Windows":
            base = Path.home() / "Desktop"
        elif self.system == "Darwin":
            base = Path.home() / "Desktop"
        else:  # Linux
            base = Path.home() / "Downloads"

        safe_title = self._sanitize_filename(title)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return base / f"Xiaohongshu_Exports/{timestamp}_{safe_title}"

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """清理文件名 (跨平台)"""
        import re
        # 移除或替换非法字符
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
        # 限制长度
        return sanitized[:30]
