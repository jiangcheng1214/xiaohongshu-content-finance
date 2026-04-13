#!/usr/bin/env python3
"""
图片生成模块

支持多个生图提供商：
- 智谱 AI (zhipu) - 默认，便宜，中文支持好
- Nano Banana Pro (Gemini) - 备选
- image-gen-multi - 多提供商支持
"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional


# ─── 配置 ───────────────────────────────────────────────────────────────────────

# 默认生图提供商
DEFAULT_IMAGE_PROVIDER = os.environ.get("IMAGE_PROVIDER", "zhipu")  # zhipu, nano-banana, multi

# ─── 技能自动安装 ─────────────────────────────────────────────────────────────

def _ensure_skill_installed(skill_name: str = "image-gen-multi") -> Path:
    """
    确保 skill 已安装到全局目录
    如果不存在，从沙箱自动复制

    Args:
        skill_name: 技能名称

    Returns:
        技能安装目录
    """
    global_skills_dir = Path.home() / ".openclaw" / "skills"
    skill_dir = global_skills_dir / skill_name

    # 如果已安装，直接返回
    if skill_dir.exists():
        return skill_dir

    # 尝试从沙箱复制
    sandboxes_dir = Path.home() / ".openclaw" / "sandboxes"
    source_skill = None

    if sandboxes_dir.exists():
        for sandbox in sandboxes_dir.glob("agent-main-*"):
            candidate = sandbox / "skills" / skill_name
            if candidate.exists():
                source_skill = candidate
                break

    if not source_skill:
        raise FileNotFoundError(
            f"Cannot install {skill_name}: not found in any sandbox. "
            f"Please install it manually to ~/.openclaw/skills/{skill_name}/"
        )

    # 创建目标目录并复制
    skill_dir.mkdir(parents=True, exist_ok=True)

    # 复制所有文件和目录
    for item in source_skill.iterdir():
        dest = skill_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)

    print(f"✓ Installed {skill_name} to {skill_dir}")
    return skill_dir


# ─── 图片生成 ───────────────────────────────────────────────────────────────────

# 宽高比到 prompt 指令的映射
_ASPECT_RATIO_PROMPTS = {
    "1:1": "Create a SQUARE image with exactly 1:1 aspect ratio (equal width and height).",
    "3:4": "Create a PORTRAIT image with exactly 3:4 aspect ratio (taller than wide).",
    "4:3": "Create a LANDSCAPE image with exactly 4:3 aspect ratio (slightly wider than tall).",
    "9:16": "Create a VERTICAL PORTRAIT image with exactly 9:16 aspect ratio (phone screen format).",
    "16:9": "Create a WIDE LANDSCAPE image with exactly 16:9 aspect ratio (cinematic format).",
}


def generate_image(prompt: str, output_path: Path,
                  api_key: str = "", resolution: str = "1K",
                  reference_image: Optional[Path] = None,
                  aspect_ratio: str = "1:1",
                  provider: str = None,
                  auto_fallback: bool = True) -> bool:
    """
    生成图片（支持自动重试和切换提供商）

    Args:
        prompt: 图片生成提示词
        output_path: 输出文件路径
        api_key: API key (可选，会从配置自动读取)
        resolution: 分辨率 (1K, 2K, 4K) - 仅用于 nano-banana
        reference_image: 参考图片路径（用于保持一致性）
        aspect_ratio: 宽高比 (1:1, 3:4, 16:9 等)
        provider: 生图提供商 (zhipu, nano-banana, multi)，默认使用 DEFAULT_IMAGE_PROVIDER
        auto_fallback: 是否在失败时自动切换到备选提供商

    Returns:
        bool: 是否成功
    """
    # 确定使用的提供商
    provider = provider or DEFAULT_IMAGE_PROVIDER

    # 提供商重试顺序
    fallback_order = {
        "zhipu": ["zhipu", "nano-banana"],      # 智谱失败时用 Gemini
        "nano-banana": ["nano-banana", "zhipu"], # Gemini 失败时用智谱
        "multi": ["zhipu", "nano-banana"],       # multi 先用智谱
    }

    providers_to_try = [provider] if not auto_fallback else fallback_order.get(provider, [provider])

    last_error = None
    for try_provider in providers_to_try:
        try:
            if try_provider == "zhipu":
                result = _generate_with_zhipu(prompt, output_path, api_key, aspect_ratio)
            elif try_provider == "nano-banana":
                result = _generate_with_nano_banana(prompt, output_path, api_key, resolution, reference_image, aspect_ratio)
            elif try_provider == "multi":
                result = _generate_with_multi(prompt, output_path, api_key, aspect_ratio)
            else:
                raise ValueError(f"Unknown provider: {try_provider}")

            if result:
                return True

        except Exception as e:
            last_error = e
            error_msg = str(e)
            # 智谱内容过滤错误，尝试下一个提供商
            if "1301" in error_msg or "敏感内容" in error_msg or "不安全" in error_msg:
                print(f"⚠️ {try_provider} 内容过滤，尝试备选提供商...")
                continue
            # 其他错误直接抛出
            raise

    # 所有提供商都失败了
    if last_error:
        raise last_error

    return False


def _generate_with_zhipu(prompt: str, output_path: Path,
                         api_key: str = "",
                         aspect_ratio: str = "1:1") -> bool:
    """使用智谱 AI 生成图片"""
    # 计算尺寸
    width, height = _get_dimensions_from_aspect_ratio(aspect_ratio)

    # 确保技能已安装
    skill_dir = _ensure_skill_installed("image-gen-multi")
    script_path = skill_dir / "scripts" / "image_gen.py"

    if not script_path.exists():
        raise FileNotFoundError(f"image_gen.py not found at {script_path}")

    # 构建命令
    cmd = [
        'python3', str(script_path),
        '--provider', 'zhipu',
        '--prompt', prompt,
        '--output', str(output_path),
        '--width', str(width),
        '--height', str(height)
    ]

    if api_key:
        cmd.extend(['--api-key', api_key])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            error_output = (result.stdout + '\n' + result.stderr)[:500]
            raise RuntimeError(f'智谱生图失败: {error_output}')

        if not output_path.exists():
            raise FileNotFoundError('输出文件未创建')

        return True

    except subprocess.TimeoutExpired:
        raise RuntimeError('智谱生图超时')
    except Exception as e:
        raise RuntimeError(f'智谱生图错误: {str(e)}')


def _generate_with_nano_banana(prompt: str, output_path: Path,
                               api_key: str = "", resolution: str = "1K",
                               reference_image: Optional[Path] = None,
                               aspect_ratio: str = "1:1") -> bool:
    """使用 Nano Banana Pro (Gemini) 生成图片"""
    # 在 prompt 开头添加宽高比指令
    ratio_instruction = _ASPECT_RATIO_PROMPTS.get(aspect_ratio, "")
    if ratio_instruction:
        prompt = f"{ratio_instruction}\n\n{prompt}"

    skill_name = "nano-banana-pro"
    script_name = "generate_image.py"

    # 确保技能已安装到全局目录
    skill_dir = _ensure_skill_installed(skill_name)

    # 生成脚本路径（优先级：环境变量 > 全局安装 > 当前项目）
    generate_script = None

    # 1. 环境变量指定
    if env_path := os.environ.get("NANO_BANANA_SCRIPT"):
        candidate = Path(env_path)
        if candidate.exists():
            generate_script = candidate

    # 2. 全局技能目录
    if not generate_script:
        candidate = skill_dir / "scripts" / script_name
        if candidate.exists():
            generate_script = candidate

    # 3. 当前项目 lib 目录（开发模式）
    if not generate_script:
        current_dir = Path(__file__).parent
        candidate = current_dir / skill_name / script_name
        if candidate.exists():
            generate_script = candidate

    if not generate_script:
        raise FileNotFoundError(
            f"{script_name} not found after installation. "
            f"Expected at: {skill_dir / 'scripts' / script_name}"
        )

    # 构建命令
    cmd = ['uv', 'run', str(generate_script),
           '--prompt', prompt,
           '--filename', str(output_path),
           '--resolution', resolution]

    # 添加参考图片
    if reference_image and reference_image.exists():
        cmd.extend(['--input-image', str(reference_image)])

    if api_key:
        cmd.extend(['--api-key', api_key])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            error_output = (result.stdout + '\n' + result.stderr)[:500]
            raise RuntimeError(f'Image generation failed: {error_output}')

        if not output_path.exists():
            raise FileNotFoundError('Output file not created')

        return True

    except subprocess.TimeoutExpired:
        raise RuntimeError('Image generation timed out')
    except Exception as e:
        raise RuntimeError(f'Image generation error: {str(e)}')


def _generate_with_multi(prompt: str, output_path: Path,
                         api_key: str = "",
                         aspect_ratio: str = "1:1") -> bool:
    """使用 image-gen-multi 生成图片 (支持多个提供商)"""
    width, height = _get_dimensions_from_aspect_ratio(aspect_ratio)

    # 确保技能已安装
    skill_dir = _ensure_skill_installed("image-gen-multi")
    script_path = skill_dir / "scripts" / "image_gen.py"

    if not script_path.exists():
        raise FileNotFoundError(f"image_gen.py not found at {script_path}")

    # 构建命令 - 默认使用智谱
    cmd = [
        'python3', str(script_path),
        '--provider', 'zhipu',
        '--prompt', prompt,
        '--output', str(output_path),
        '--width', str(width),
        '--height', str(height)
    ]

    if api_key:
        cmd.extend(['--api-key', api_key])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            error_output = (result.stdout + '\n' + result.stderr)[:500]
            raise RuntimeError(f'生图失败: {error_output}')

        if not output_path.exists():
            raise FileNotFoundError('输出文件未创建')

        return True

    except subprocess.TimeoutExpired:
        raise RuntimeError('生图超时')
    except Exception as e:
        raise RuntimeError(f'生图错误: {str(e)}')


def _get_dimensions_from_aspect_ratio(aspect_ratio: str) -> tuple[int, int]:
    """将宽高比转换为实际尺寸"""
    dimensions = {
        "1:1": (1024, 1024),
        "3:4": (768, 1024),
        "4:3": (1024, 768),
        "9:16": (576, 1024),
        "16:9": (1024, 576),
    }
    return dimensions.get(aspect_ratio, (1024, 1024))


def get_api_key(provider: str = None) -> str:
    """
    从配置文件获取 API key

    Args:
        provider: 提供商名称 (zhipu, nano-banana-pro)，默认使用 DEFAULT_IMAGE_PROVIDER

    Returns:
        API key 字符串
    """
    provider = provider or DEFAULT_IMAGE_PROVIDER
    config_file = Path.home() / '.openclaw' / 'openclaw.json'
    if not config_file.exists():
        return ''

    with open(config_file) as f:
        data = json.load(f)

    skills_cfg = data.get('skills', {}).get('entries', {})

    if provider == "zhipu":
        # 从 image-gen-multi 配置获取
        if 'image-gen-multi' in skills_cfg:
            multi_cfg = skills_cfg['image-gen-multi']
            if isinstance(multi_cfg, dict):
                return multi_cfg.get('zhipu', '')
    elif provider == "nano-banana" or provider == "nano-banana-pro":
        # Gemini API key
        api_key = data.get('env', {}).get('GEMINI_API_KEY', '')
        if not api_key:
            api_key = skills_cfg.get('nano-banana-pro', {}).get('apiKey', '')
        return api_key

    return ''
