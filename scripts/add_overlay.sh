#!/bin/bash
# 为已生成的图片添加文字元素和 Logo
# 用法: ./add_overlay.sh "输入图片" "标题" "副标题" "输出路径" [Logo路径] [Vertical]

set -e

INPUT="$1"
TITLE="$2"
SUBTITLE="${3:-}"
OUTPUT="${4:-/tmp/xhs_cover_overlay_$(date +%s).png}"
LOGO_PATH="${5:-}"
VERTICAL="${6:-}"

if [[ -z "$INPUT" || -z "$TITLE" ]]; then
    echo "用法: $0 \"输入图片\" \"标题\" [\"副标题\"] [\"输出路径\"] [\"Logo路径\"] [\"Vertical\"]" >&2
    exit 1
fi

if [[ ! -f "$INPUT" ]]; then
    echo "错误: 输入文件不存在: $INPUT" >&2
    exit 1
fi

# 获取技能目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# 读取垂类的字体风格配置
get_font_style() {
    local vertical="$1"
    local config="$SKILL_DIR/verticals/$vertical.json"

    if [[ ! -f "$config" ]]; then
        echo "default"
        return
    fi

    PYTHONIOENCODING=utf-8 python3 -c "
# -*- coding: utf-8 -*-
import json
try:
    with open('$config') as f:
        c = json.load(f)
        font_style = c.get('cover_config', {}).get('font_style', {})
except:
    print('default')
" 2>/dev/null || echo "default"
}

# 如果没有提供Logo路径，尝试自动获取
if [[ -z "$LOGO_PATH" ]]; then
    LOGO_PATH="$SKILL_DIR/assets/logo/default.png"
fi

# 检查 Logo 文件是否存在
if [[ ! -f "$LOGO_PATH" ]]; then
    echo "警告: Logo 文件不存在: $LOGO_PATH，继续生成不带Logo的封面" >&2
    LOGO_PATH=""
fi

if command -v magick &> /dev/null; then
    MAGICK="magick"
elif command -v convert &> /dev/null; then
    MAGICK="convert"
else
    echo "错误: 未找到 ImageMagick" >&2
    exit 1
fi

# 字体配置
MAGICK_FONT_BOLD="/System/Library/Fonts/STHeiti Medium.ttc"
MAGICK_FONT_LIGHT="/System/Library/Fonts/STHeiti Light.ttc"

# macOS 可用的可爱/网感字体
CUTE_FONTS=(
    "/System/Library/Fonts/PingFang.ttc"
    "/System/Library/Fonts/STHeiti Medium.ttc"
    "/Library/Fonts/Arial Rounded Bold.ttf"
)

[[ ! -f "$MAGICK_FONT_BOLD" ]] && MAGICK_FONT_BOLD="STHeiti-Medium"
[[ ! -f "$MAGICK_FONT_LIGHT" ]] && MAGICK_FONT_LIGHT="STHeiti-Light"

[[ -n "$LOGO_PATH" ]] && echo "# 使用 Logo: $(basename $LOGO_PATH)" >&2

# 获取图片尺寸
DIMENSIONS=$("$MAGICK" "$INPUT" -ping -format "%w %h" info:)
WIDTH=$(echo $DIMENSIONS | cut -d' ' -f1)
HEIGHT=$(echo $DIMENSIONS | cut -d' ' -f2)

# Logo 位置: 左上角
LOGO_X=$((WIDTH * 5 / 100))
LOGO_Y=$((HEIGHT * 4 / 100))

# 横幅遮罩尺寸
BAND_WIDTH=$WIDTH
BAND_HEIGHT=$((HEIGHT * 18 / 100))

TEMP1=$(mktemp).png
cleanup() {
    rm -f "$TEMP1"
}
trap cleanup EXIT

# 第一步：中央横幅遮罩 - 根据垂类调整遮罩颜色和透明度
MASK_COLOR="rgba(0,0,0,0.45)"
MASK_OPACITY="0.45"

"$MAGICK" "$INPUT" \
    \( -size "${BAND_WIDTH}x${BAND_HEIGHT}" \
       xc:"$MASK_COLOR" \
       -gravity center \) \
    -geometry +0-10 \
    -compose over -composite "$TEMP1"

# 第二步：大标题 - 根据垂类风格调整效果
TITLE_LENGTH=${#TITLE}
AVAILABLE_WIDTH=$((WIDTH * 75 / 100))
CALC_POINTSIZE=$((AVAILABLE_WIDTH * 10 / TITLE_LENGTH / 5))

if [[ $CALC_POINTSIZE -gt 100 ]]; then
    CALC_POINTSIZE=100
elif [[ $CALC_POINTSIZE -lt 40 ]]; then
    CALC_POINTSIZE=40
fi

SHADOW_POINTSIZE=$((CALC_POINTSIZE * 115 / 100))

# 选择字体和效果
TITLE_FONT="$MAGICK_FONT_BOLD"
SHADOW_COLOR="rgba(0,0,0,0.55)"
TEXT_COLOR="white"
SHADOW_OFFSET_Y="-12"
TEXT_OFFSET_Y="+10"

echo "# 标题长度: $TITLE_LENGTH 字, 字号: $CALC_POINTSIZE, 阴影: $SHADOW_POINTSIZE" >&2

# 应用标题（阴影 + 主文字）
"$MAGICK" "$TEMP1" \
    -font "$TITLE_FONT" -pointsize $SHADOW_POINTSIZE \
    -fill "$SHADOW_COLOR" \
    -gravity center \
    -annotate +0$SHADOW_OFFSET_Y "$TITLE" \
    -font "$TITLE_FONT" -pointsize $CALC_POINTSIZE \
    -fill "$TEXT_COLOR" \
    -gravity center \
    -annotate +0$TEXT_OFFSET_Y "$TITLE" \
    "$TEMP1"

# 第三步：副标题 - 根据垂类调整装饰线颜色
if [[ -n "$SUBTITLE" ]]; then
    DECOR_COLOR="rgba(255,100,100,0.8)"
    DECOR_OFFSET="+0+140"
    SUBTITLE_OFFSET="+0+180"

    "$MAGICK" "$TEMP1" \
        \( -size "120x3" xc:"$DECOR_COLOR" \) \
        -gravity center -geometry $DECOR_OFFSET -compose over -composite \
        -font "$MAGICK_FONT_LIGHT" -pointsize 45 \
        -fill "rgba(255,255,255,0.95)" \
        -gravity center \
        -annotate $SUBTITLE_OFFSET "$SUBTITLE" \
        "$TEMP1"
fi

# 第四步：Logo（如果存在）
if [[ -n "$LOGO_PATH" && -f "$LOGO_PATH" ]]; then
    LOGO_SIZE=$((WIDTH * 22 / 100))
    TEMP_LOGO=$(mktemp).png
    "$MAGICK" "$LOGO_PATH" -resize "${LOGO_SIZE}x${LOGO_SIZE}" "$TEMP_LOGO"
    "$MAGICK" "$TEMP1" "$TEMP_LOGO" -geometry "+${LOGO_X}+${LOGO_Y}" -compose over -composite "$OUTPUT"
    rm -f "$TEMP_LOGO"
else
    cp "$TEMP1" "$OUTPUT"
fi

echo "完成: $OUTPUT" >&2
echo "$OUTPUT"
