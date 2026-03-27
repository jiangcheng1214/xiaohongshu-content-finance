"""
跨平台路径管理
"""

import os
import platform
from pathlib import Path
from typing import Union

from ..config import Config


class PathManager:
    """跨平台路径管理"""

    def __init__(self, config: Config):
        self.config = config
        self.system = platform.system()

    @staticmethod
    def normalize(path: Union[str, Path]) -> Path:
        """规范化路径，处理 ~ 和相对路径"""
        return Path(path).expanduser().absolute()

    def get_skill_dir(self) -> Path:
        """获取技能目录"""
        return Path(__file__).parent.parent.parent.parent

    def get_session_dir(self, session_id: str) -> Path:
        """获取 Session 目录"""
        workspace = self.config.get_workspace()
        return workspace / session_id

    def get_temp_dir(self) -> Path:
        """获取临时目录 (跨平台)"""
        return self.config.get_temp_dir()

    def get_export_dir(self, title: str) -> Path:
        """获取导出目录"""
        return self.config.get_export_dir(title)

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

    @staticmethod
    def sanitize_filename(name: str) -> str:
        """清理文件名 (跨平台)"""
        import re
        # 移除或替换非法字符
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
        # 限制长度
        return sanitized[:30]

    def find_homebrew(self) -> Path | None:
        """查找 Homebrew 安装路径"""
        paths = {
            "Darwin": ["/opt/homebrew", "/usr/local"],
            "Linux": ["/home/linuxbrew/.linuxbrew"],
        }

        for path in paths.get(self.system, []):
            p = Path(path)
            if p.exists():
                return p
        return None

    def find_imagemagick(self) -> str | None:
        """查找 ImageMagick 命令"""
        import shutil

        commands = ["magick", "convert", "magick convert"]
        for cmd in commands:
            if shutil.which(cmd):
                return cmd
        return None
