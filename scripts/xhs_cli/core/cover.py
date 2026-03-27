"""
封面生成模块
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..config import Config
from ..lib.paths import PathManager
from .session import Session


class CoverGenerator:
    """封面生成器"""

    def __init__(self, config: Config | None = None, path_manager: PathManager | None = None):
        self.config = config or Config()
        self.path_manager = path_manager or PathManager(self.config)

    def generate(self, session: Session, title: str | None = None, subtitle: str | None = None) -> Path:
        """生成封面图

        返回: 封面文件路径
        """
        # 使用 session 中的标题或传入的标题
        main_title = title or session.title
        main_subtitle = subtitle or session.subtitle

        if not main_title:
            raise ValueError("标题不能为空")

        print(f"# === 封面生成 ===", file=sys.stderr)
        print(f"# Title: {main_title}", file=sys.stderr)
        print(f"# Subtitle: {main_subtitle}", file=sys.stderr)

        # 加载垂类配置
        vertical_config = self._load_vertical_config(session.vertical)
        cover_config = vertical_config.get("cover_config", {})

        # 获取输出路径
        output_path = self.path_manager.get_session_dir(session.id) / "cover.png"

        # 生成背景图
        background = self._generate_background(session, vertical_config, cover_config)

        if background and background.exists():
            # 保存原始背景图副本
            bg_backup = output_path.with_suffix(".bg.png")
            import shutil
            shutil.copy(background, bg_backup)

            # 调用 add_overlay.sh 添加文字叠加（复刻原 shell 脚本逻辑）
            logo_path = self._get_logo_path(session.vertical, cover_config)
            self._add_overlay(background, main_title, main_subtitle, output_path, logo_path, session.vertical)
            print(f"# ✓ 封面生成成功: {output_path}", file=sys.stderr)

            # 清理临时背景
            if background.exists():
                background.unlink()
        else:
            # 如果背景生成失败，创建一个简单的纯色封面
            self._create_fallback_cover(output_path, main_title, main_subtitle, session.vertical)

        # 更新 session
        session.cover_path = str(output_path)
        session.status = "cover_generated"
        session.steps["cover"] = True
        session.cover_updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # 添加 debug 信息
        session.debug = session.debug or {}
        session.debug["cover"] = {
            "vertical": session.vertical,
            "title": main_title,
            "subtitle": main_subtitle,
            "output_path": str(output_path),
            "aspect_ratio": cover_config.get("aspect_ratio", "3:4")
        }

        session.save(self.path_manager.get_session_dir(session.id))

        return output_path

    def _load_vertical_config(self, vertical: str) -> dict:
        """加载垂类配置"""
        config_file = self.path_manager.get_verticals_dir() / f"{vertical}.json"

        # 如果配置不存在，使用 finance 作为默认
        if not config_file.exists():
            print(f"# Warning: Vertical config not found: {config_file}", file=sys.stderr)
            print(f"# Using default finance configuration", file=sys.stderr)
            config_file = self.path_manager.get_verticals_dir() / "finance.json"

        if not config_file.exists():
            # 返回空配置
            return {}

        with open(config_file, encoding="utf-8") as f:
            return json.load(f)

    def _get_logo_path(self, vertical: str, cover_config: dict) -> Path | None:
        """获取 Logo 路径（三级回退）"""
        logo_dir = self.path_manager.get_logo_dir()

        # 1. 尝试配置中的 logo_file
        if logo_file := cover_config.get("logo_file"):
            config_path = logo_dir / logo_file
            if config_path.exists():
                return config_path

        # 2. 尝试 {vertical}.png
        vertical_path = logo_dir / f"{vertical}.png"
        if vertical_path.exists():
            return vertical_path

        # 3. 回退到 default.png
        default_path = logo_dir / "default.png"
        return default_path if default_path.exists() else None

    def _add_overlay(
        self,
        input_path: Path,
        title: str,
        subtitle: str,
        output_path: Path,
        logo_path: Path | None,
        vertical: str
    ) -> None:
        """添加文字叠加

        优先使用 Python 版本 (跨平台)，回退到 shell 脚本
        """
        print(f"# Adding text overlay...", file=sys.stderr)

        # 优先尝试 Python 版本
        script_dir = self.path_manager.get_skill_dir() / "scripts"
        add_overlay_py = script_dir / "lib" / "add_overlay.py"

        if add_overlay_py.exists():
            try:
                cmd = [
                    "python3", str(add_overlay_py),
                    str(input_path),
                    title,
                    subtitle,
                    str(output_path),
                ]
                if logo_path and logo_path.exists():
                    cmd.append(str(logo_path))
                    cmd.append(vertical)

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    encoding="utf-8"
                )

                if result.returncode == 0 and output_path.exists():
                    print(f"# ✓ 文字叠加完成 (Python)", file=sys.stderr)
                    if result.stderr:
                        for line in result.stderr.strip().split("\n"):
                            if line.startswith("#"):
                                print(line, file=sys.stderr)
                    return
                else:
                    print(f"# ⚠️ Python 版本失败，尝试 shell 脚本", file=sys.stderr)
                    if result.stderr:
                        print(f"# 错误: {result.stderr}", file=sys.stderr)

            except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
                print(f"# ⚠️ Python 版本执行失败: {e}", file=sys.stderr)

        # 回退到 shell 脚本
        add_overlay_script = script_dir / "add_overlay.sh"

        if not add_overlay_script.exists():
            print(f"# ⚠️ add_overlay.sh 不存在，跳过文字叠加", file=sys.stderr)
            import shutil
            shutil.copy(input_path, output_path)
            return

        # 构建命令参数
        cmd = [
            str(add_overlay_script),
            str(input_path),
            title,
            subtitle,
            str(output_path),
        ]

        if logo_path and logo_path.exists():
            cmd.append(str(logo_path))
            cmd.append(vertical)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                encoding="utf-8"
            )

            if result.returncode == 0 and output_path.exists():
                print(f"# ✓ 文字叠加完成 (Shell)", file=sys.stderr)
                if result.stderr:
                    for line in result.stderr.strip().split("\n"):
                        if line.startswith("#"):
                            print(line, file=sys.stderr)
            else:
                print(f"# ⚠️ 文字叠加失败，使用纯背景图", file=sys.stderr)
                if result.stderr:
                    print(f"# 错误: {result.stderr}", file=sys.stderr)
                import shutil
                shutil.copy(input_path, output_path)

        except subprocess.TimeoutExpired:
            print(f"# ⚠️ 文字叠加超时，使用纯背景图", file=sys.stderr)
            import shutil
            shutil.copy(input_path, output_path)
        except (FileNotFoundError, OSError) as e:
            print(f"# ⚠️ 文字叠加执行失败: {e}", file=sys.stderr)
            import shutil
            shutil.copy(input_path, output_path)

    def _generate_background(self, session: Session, vertical_config: dict, cover_config: dict) -> Path | None:
        """生成背景图"""
        # 获取 API key
        api_key = self.config.get_gemini_api_key()
        if not api_key:
            print(f"# ⚠️ 警告: 未找到 GEMINI_API_KEY", file=sys.stderr)
            print(f"# 请在 ~/.openclaw/openclaw.json 中配置 env.GEMINI_API_KEY", file=sys.stderr)
            return None

        # 构建 prompt
        prompt = self._get_cover_prompt(session, vertical_config, cover_config)
        print(f"# Prompt: {prompt}", file=sys.stderr)

        # 获取输出参数
        aspect_ratio = cover_config.get("aspect_ratio", "3:4")
        print(f"# Aspect Ratio: {aspect_ratio}", file=sys.stderr)

        # 生成临时输出路径
        temp_output = self.path_manager.get_temp_dir() / f"xhs_cover_bg_{session.id}.png"

        # 调用 nano-banana-pro
        script_dir = self.path_manager.get_skill_dir() / "scripts"
        generate_image_script = script_dir / "lib" / "generate_image.py"

        if not generate_image_script.exists():
            print(f"# ✗ 错误: generate_image.py 不存在于 {generate_image_script}", file=sys.stderr)
            return None

        print(f"# 调用 nano banana pro 生成背景...", file=sys.stderr)

        try:
            cmd = [
                "uv", "run", str(generate_image_script),
                "--prompt", prompt,
                "--filename", str(temp_output),
                "--resolution", "1K"
            ]
            if api_key:
                cmd.extend(["--api-key", api_key])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                encoding="utf-8"
            )

            if result.returncode == 0 and temp_output.exists():
                file_size = temp_output.stat().st_size
                print(f"# ✓ 背景生成成功，大小: {file_size} bytes", file=sys.stderr)
                if file_size < 1000:
                    print(f"# ⚠️ 警告: 生成的图片太小，可能是错误", file=sys.stderr)
                return temp_output
            else:
                print(f"# ✗ 背景生成失败！", file=sys.stderr)
                if result.stderr:
                    print(f"# 错误: {result.stderr}", file=sys.stderr)
                return None

        except subprocess.TimeoutExpired:
            print(f"# ✗ 背景生成超时", file=sys.stderr)
            return None
        except (FileNotFoundError, OSError) as e:
            print(f"# ✗ 执行失败: {e}", file=sys.stderr)
            return None

    def _get_cover_prompt(self, session: Session, vertical_config: dict, cover_config: dict) -> str:
        """获取封面 prompt"""
        # 检查是否有动态变量配置
        prompt_variables = cover_config.get("prompt_variables", {})

        if prompt_variables:
            # 使用动态 prompt 生成器
            print(f"# 检测到 prompt_variables 配置，使用动态生成...", file=sys.stderr)
            return self._build_dynamic_prompt(session, vertical_config, cover_config)

        # 使用静态 prompt 模板
        prompt_template = cover_config.get("background_prompt_template", "")
        if prompt_template:
            print(f"# 使用静态 prompt 模板", file=sys.stderr)
            return prompt_template

        # 回退到默认 prompt
        style_prefix = cover_config.get("style_prefix", "Modern background")
        return f"{style_prefix}, clean modern background, 3:4 portrait, no text"

    def _build_dynamic_prompt(self, session: Session, vertical_config: dict, cover_config: dict) -> str:
        """构建动态 prompt"""
        script_dir = self.path_manager.get_skill_dir() / "scripts"
        build_prompt_script = script_dir / "lib" / "build_dynamic_cover_prompt.py"

        if build_prompt_script.exists():
            try:
                vertical_config_path = self.path_manager.get_verticals_dir() / f"{session.vertical}.json"
                result = subprocess.run(
                    ["python3", str(build_prompt_script),
                     str(vertical_config_path), session.topic, session.vertical],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    encoding="utf-8"
                )
                if result.returncode == 0 and result.stdout:
                    # 过滤掉调试信息，只保留 prompt
                    lines = [line for line in result.stdout.split("\n") if not line.startswith("#")]
                    prompt = "\n".join(lines).strip()
                    if prompt:
                        print(f"# ✓ 动态 prompt 生成成功", file=sys.stderr)
                        return prompt
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                pass

        print(f"# ⚠️ 动态 prompt 生成失败，使用备用模板", file=sys.stderr)
        style_prefix = cover_config.get("style_prefix", "Modern background")
        return f"{style_prefix}, clean modern background, 3:4 portrait, no text"

    def _create_fallback_cover(self, output_path: Path, title: str, subtitle: str, vertical: str):
        """创建备用封面（纯色背景）"""
        try:
            from PIL import Image, ImageDraw, ImageFont

            # 创建 3:4 的图像 (1080x1440)
            img = Image.new("RGB", (1080, 1440), color="#f0f0f0")
            draw = ImageDraw.Draw(img)

            # 尝试加载字体
            from ..lib.fonts import FontManager
            font_mgr = FontManager(self.config)
            font_path = font_mgr.find_font()

            try:
                if font_path:
                    title_font = ImageFont.truetype(str(font_path), 60)
                    subtitle_font = ImageFont.truetype(str(font_path), 40)
                else:
                    title_font = ImageFont.load_default()
                    subtitle_font = ImageFont.load_default()
            except OSError:
                title_font = ImageFont.load_default()
                subtitle_font = ImageFont.load_default()

            # 绘制标题（居中）
            title_bbox = draw.textbbox((0, 0), title, font=title_font)
            title_width = title_bbox[2] - title_bbox[0]
            title_x = (1080 - title_width) // 2
            title_y = 1440 // 2 - 50
            draw.text((title_x, title_y), title, font=title_font, fill="#333333")

            # 绘制副标题
            if subtitle:
                sub_bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
                sub_width = sub_bbox[2] - sub_bbox[0]
                sub_x = (1080 - sub_width) // 2
                sub_y = title_y + 80
                draw.text((sub_x, sub_y), subtitle, font=subtitle_font, fill="#666666")

            # 保存
            img.save(output_path, "PNG")
            print(f"# ✓ 备用封面已创建", file=sys.stderr)

        except ImportError:
            # Pillow 未安装，创建一个最小的 PNG
            print(f"# ⚠️ Pillow 未安装，无法创建备用封面", file=sys.stderr)
            # 创建一个最小的 1x1 PNG 文件
            import struct
            with open(output_path, "wb") as f:
                # PNG 文件头
                f.write(b'\x89PNG\r\n\x1a\n')
                # IHDR chunk (1x1 RGB)
                f.write(struct.pack(">I", 13))
                f.write(b'IHDR')
                f.write(struct.pack(">I", 1))  # width
                f.write(struct.pack(">I", 1))  # height
                f.write(b'\x08\x02\x00\x00\x00')  # bit depth, color type, etc.
                f.write(struct.pack(">I", 0x5c6e63ef))  # CRC
                # IDAT chunk (minimal)
                f.write(struct.pack(">I", 12))
                f.write(b'IDAT')
                f.write(b'\x78\x9c\x62\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4')
                f.write(struct.pack(">I", 0x849ddfe8))  # CRC
                # IEND chunk
                f.write(struct.pack(">I", 0))
                f.write(b'IEND')
                f.write(struct.pack(">I", 0xae426082))  # CRC
