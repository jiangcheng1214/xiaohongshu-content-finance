#!/usr/bin/env python3
"""
小红书封面文字叠加 - 跨平台 Python 版本

用法:
    python add_overlay.py <input> <title> <subtitle> <output> [logo] [vertical]

参数:
    input     - 背景图路径
    title     - 主标题
    subtitle  - 副标题
    output    - 输出路径
    logo      - Logo 路径 (可选)
    vertical  - 垂类代码 (可选)
"""

import sys
import platform
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except ImportError:
    print("错误: 需要安装 Pillow: pip install Pillow", file=sys.stderr)
    sys.exit(1)


class OverlayRenderer:
    """封面文字叠加渲染器"""

    # 跨平台字体回退
    FONT_FALLBACK = {
        "Darwin": [
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
        ],
        "Linux": [
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ],
        "Windows": [
            "C:/Windows/Fonts/msyh.ttc",  # 微软雅黑
            "C:/Windows/Fonts/simhei.ttf",  # 黑体
            "C:/Windows/Fonts/simsun.ttc",  # 宋体
            "C:/Windows/Fonts/arial.ttf",
        ]
    }

    def __init__(self):
        self.system = platform.system()
        self.bold_font = None
        self.light_font = None

    def find_font(self, size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
        """查找可用字体"""
        font_paths = self.FONT_FALLBACK.get(self.system, [])

        for font_path in font_paths:
            if Path(font_path).exists():
                try:
                    return ImageFont.truetype(font_path, size)
                except OSError:
                    continue

        # 尝试使用 fc-match (Linux)
        if self.system == "Linux":
            try:
                import subprocess
                result = subprocess.run(
                    ["fc-match", "-f", "%{file}", "sans-serif"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    return ImageFont.truetype(result.stdout.strip(), size)
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                pass

        # 回退到默认字体
        try:
            return ImageFont.load_default()
        except AttributeError:
            # Pillow < 10.0
            return ImageFont.load_default()

    def add_text_overlay(
        self,
        input_path: str,
        title: str,
        subtitle: str,
        output_path: str,
        logo_path: str | None = None,
        vertical: str = "finance"
    ) -> bool:
        """添加文字叠加

        复刻原 add_overlay.sh 的视觉效果:
        1. 中央横幅遮罩 (半透明黑色)
        2. 大标题 (白色 + 阴影)
        3. 副标题 (装饰线 + 较小文字)
        4. Logo (左上角)
        """
        try:
            # 加载背景图
            img = Image.open(input_path).convert("RGBA")
            width, height = img.size
            draw = ImageDraw.Draw(img)

            print(f"# 图片尺寸: {width}x{height}", file=sys.stderr)

            # 1. 中央横幅遮罩
            band_height = int(height * 0.18)
            band_y_start = (height - band_height) // 2

            # 创建半透明黑色遮罩
            overlay = Image.new("RGBA", (width, band_height), (0, 0, 0, int(255 * 0.45)))
            img.paste(overlay, (0, band_y_start), overlay)

            print(f"# 横幅遮罩: 高度 {band_height}px, Y偏移 {band_y_start}", file=sys.stderr)

            # 2. 大标题
            title_len = len(title)
            available_width = int(width * 0.75)
            # 动态计算字号: 标题越长，字号越小
            calc_pointsize = min(100, max(40, available_width * 10 // title_len // 5))
            shadow_pointsize = int(calc_pointsize * 1.15)

            print(f"# 标题长度: {title_len} 字, 字号: {calc_pointsize}, 阴影: {shadow_pointsize}", file=sys.stderr)

            title_font = self.find_font(calc_pointsize, bold=True)
            shadow_font = self.find_font(shadow_pointsize, bold=True)

            # 计算标题位置 (居中)
            title_bbox = draw.textbbox((0, 0), title, font=title_font)
            title_width = title_bbox[2] - title_bbox[0]
            title_x = (width - title_width) // 2
            title_y = band_y_start + band_height // 2 - int(calc_pointsize * 0.5)

            # 绘制阴影
            shadow_offset = 3
            draw.text(
                (title_x + shadow_offset, title_y + shadow_offset),
                title,
                font=shadow_font,
                fill=(0, 0, 0, int(255 * 0.55))
            )

            # 绘制主标题
            draw.text(
                (title_x, title_y),
                title,
                font=title_font,
                fill=(255, 255, 255, 255)
            )

            # 3. 副标题
            if subtitle:
                subtitle_font = self.find_font(45, bold=False)

                # 装饰线
                decor_width = 120
                decor_height = 3
                decor_x = (width - decor_width) // 2
                decor_y = title_y + calc_pointsize + 40

                draw.rectangle(
                    [decor_x, decor_y, decor_x + decor_width, decor_y + decor_height],
                    fill=(255, 100, 100, int(255 * 0.8))
                )

                # 副标题文字
                sub_bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
                sub_width = sub_bbox[2] - sub_bbox[0]
                sub_x = (width - sub_width) // 2
                sub_y = decor_y + 30

                draw.text(
                    (sub_x, sub_y),
                    subtitle,
                    font=subtitle_font,
                    fill=(255, 255, 255, int(255 * 0.95))
                )

            # 4. Logo (左上角)
            if logo_path and Path(logo_path).exists():
                try:
                    logo = Image.open(logo_path).convert("RGBA")
                    logo_size = int(width * 0.22)
                    logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

                    logo_x = int(width * 0.05)
                    logo_y = int(height * 0.04)

                    img.paste(logo, (logo_x, logo_y), logo)
                    print(f"# Logo: {Path(logo_path).name}", file=sys.stderr)
                except Exception as e:
                    print(f"# ⚠️ Logo 加载失败: {e}", file=sys.stderr)

            # 保存输出
            img = img.convert("RGB")  # 转为 RGB (去除 alpha 通道)
            img.save(output_path, "PNG", quality=95)

            print(f"# ✓ 封面叠加完成: {output_path}", file=sys.stderr)
            return True

        except Exception as e:
            print(f"# ✗ 错误: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            return False


def main():
    if len(sys.argv) < 5:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    title = sys.argv[2]
    subtitle = sys.argv[3]
    output_path = sys.argv[4]
    logo_path = sys.argv[5] if len(sys.argv) > 5 else None
    vertical = sys.argv[6] if len(sys.argv) > 6 else "finance"

    renderer = OverlayRenderer()
    success = renderer.add_text_overlay(
        input_path,
        title,
        subtitle,
        output_path,
        logo_path,
        vertical
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
