"""
跨平台字体检测和管理
"""

import platform
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from ..config import Config


class FontManager:
    """跨平台字体管理"""

    # 默认字体回退配置
    FALLBACK_FONTS = {
        "Darwin": ["STHeiti-Medium", "PingFang SC", "Arial"],
        "Linux": ["WenQuanYi Zen Hei", "Noto Sans CJK", "Arial"],
        "Windows": ["Microsoft YaHei", "SimHei", "SimSun", "Arial"]
    }

    # 字体文件扩展名
    FONT_EXTENSIONS = ["ttf", "ttc", "otf"]

    def __init__(self, config: Config):
        self.config = config
        self.system = platform.system()

    def find_font(self, preferred: list[str] | None = None) -> Path | None:
        """查找可用字体

        Args:
            preferred: 优先使用的字体名称列表

        Returns:
            字体文件路径，如果未找到返回 None
        """
        # 1. 优先使用配置中的字体
        config_fonts = self.config.get_font_paths() if hasattr(self.config, 'get_font_paths') else []
        for font_path in config_fonts:
            path = Path(font_path)
            if path.exists():
                return path

        # 2. 使用系统字体查找
        if preferred:
            for font_name in preferred:
                if path := self._find_system_font(font_name):
                    return path

        # 3. 使用回退字体
        for font_name in self.FALLBACK_FONTS.get(self.system, []):
            if path := self._find_system_font(font_name):
                return path

        return None

    def _find_system_font(self, font_name: str) -> Path | None:
        """在系统中查找字体"""
        if self.system == "Darwin":
            return self._find_macos_font(font_name)
        elif self.system == "Linux":
            return self._find_linux_font(font_name)
        elif self.system == "Windows":
            return self._find_windows_font(font_name)
        return None

    def _find_macos_font(self, font_name: str) -> Path | None:
        """macOS 字体查找"""
        search_paths = [
            Path("/System/Library/Fonts"),
            Path("/Library/Fonts"),
            Path.home() / "Library" / "Fonts"
        ]

        for base in search_paths:
            if not base.exists():
                continue
            # 搜索 .ttf, .ttc, .otf
            for ext in self.FONT_EXTENSIONS:
                # 精确匹配
                font_file = base / f"{font_name}.{ext}"
                if font_file.exists():
                    return font_file
            # 模糊匹配 (部分名称)
            for font_file in base.rglob(f"*{font_name}*"):
                if font_file.suffix.lstrip('.').lower() in self.FONT_EXTENSIONS:
                    return font_file
        return None

    def _find_linux_font(self, font_name: str) -> Path | None:
        """Linux 字体查找 (使用 fc-match)"""
        if shutil.which("fc-match"):
            try:
                result = subprocess.run(
                    ["fc-match", "-f", "%{file}", font_name],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    return Path(result.stdout.strip())
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                pass

        # 回退到手动搜索常见路径
        search_paths = [
            Path("/usr/share/fonts"),
            Path("/usr/local/share/fonts"),
            Path.home() / ".fonts",
            Path.home() / ".local/share/fonts"
        ]

        for base in search_paths:
            if not base.exists():
                continue
            for font_file in base.rglob(f"*{font_name}*"):
                if font_file.suffix.lstrip('.').lower() in self.FONT_EXTENSIONS:
                    return font_file
        return None

    def _find_windows_font(self, font_name: str) -> Path | None:
        """Windows 字体查找"""
        fonts_dir = Path("C:/Windows/Fonts")
        if not fonts_dir.exists():
            return None

        # 处理特殊名称映射
        font_map = {
            "Microsoft YaHei": "msyh.ttc",
            "SimHei": "simhei.ttf",
            "SimSun": "simsun.ttc",
            "Arial": "arial.ttf"
        }

        filename = font_map.get(font_name)
        if filename:
            font_path = fonts_dir / filename
            if font_path.exists():
                return font_path

        # 模糊搜索
        for font_file in fonts_dir.glob(f"*{font_name}*"):
            if font_file.suffix.lstrip('.').lower() in self.FONT_EXTENSIONS:
                return font_file

        return None

    def get_font_config(self) -> dict:
        """获取字体配置

        返回格式: {"bold": "字体路径或名称", "light": "字体路径或名称"}
        """
        font_path = self.find_font()
        if not font_path:
            # 返回通用字体名称，让系统自己处理
            return {"bold": "Arial", "light": "Arial"}

        return {
            "bold": str(font_path),
            "light": str(font_path)
        }

    def get_chinese_font(self) -> str:
        """获取中文字体名称 (用于 PIL/Pillow)

        返回字体路径或通用名称
        """
        chinese_fonts = {
            "Darwin": ["STHeiti Medium", "PingFang SC", "Heiti SC"],
            "Linux": ["WenQuanYi Zen Hei", "Noto Sans CJK SC"],
            "Windows": ["Microsoft YaHei", "SimHei", "SimSun"]
        }

        preferred = chinese_fonts.get(self.system, [])
        font_path = self.find_font(preferred)

        if font_path:
            return str(font_path)

        # 回退到系统默认
        return "Arial"
