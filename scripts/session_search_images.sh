#!/bin/bash
# 步骤: 图片搜索（写入session目录）
# 用法: ./session_search_images.sh <session_dir>

set -e

SESSION_DIR="${1:-}"

if [[ -z "$SESSION_DIR" || ! -d "$SESSION_DIR" ]]; then
    echo "用法: $0 <session_dir>" >&2
    exit 1
fi

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 读取 session.json
TOPIC=$(python3 -c "import json; print(json.load(open('$SESSION_DIR/session.json'))['topic'])")
VERTICAL=$(python3 -c "import json; print(json.load(open('$SESSION_DIR/session.json'))['vertical'])")

echo "# === 图片搜索 ===" >&2
echo "# Topic: $TOPIC" >&2
echo "# Vertical: $VERTICAL" >&2

# 图片目录
IMAGES_DIR="$SESSION_DIR/images"
mkdir -p "$IMAGES_DIR"

# 读取垂类配置获取搜索关键词
VERTICAL_CONFIG="$SKILL_DIR/verticals/$VERTICAL.json"

# 获取搜索关键词
IMAGE_KEYWORDS=$(python3 -c "
import json
try:
    with open('$VERTICAL_CONFIG', 'r') as f:
        config = json.load(f)
        keywords = config.get('keywords', [])[:5]
        print(' '.join(keywords))
except:
    print('')
")

# 构建搜索查询
SEARCH_QUERIES=("$TOPIC" "$TOPIC 评测" "$TOPIC 测评")

# 尝试使用 AI 图片搜索（如果可用）
AI_SEARCH_SCRIPT="/opt/homebrew/lib/node_modules/openclaw/skills/nano-banana-pro/scripts/search_images.py"
IMAGE_COUNT=0

if [[ -f "$AI_SEARCH_SCRIPT" ]]; then
    echo "# 使用AI图片搜索..." >&2

    for query in "${SEARCH_QUERIES[@]}"; do
        if [[ $IMAGE_COUNT -ge 3 ]]; then
            break
        fi

        echo "# 搜索: $query" >&2

        OUTPUT_FILE="$IMAGES_DIR/image_${IMAGE_COUNT}.jpg"

        # 调用AI搜索
        if uv run "$AI_SEARCH_SCRIPT" --query "$query" --output "$OUTPUT_FILE" --count 1 >/dev/null 2>&1; then
            if [[ -f "$OUTPUT_FILE" ]]; then
                IMAGE_COUNT=$((IMAGE_COUNT + 1))
                echo "# ✓ 下载图片: $(basename $OUTPUT_FILE)" >&2
            fi
        fi
    done
fi

# 如果AI搜索失败或不可用，创建占位符
if [[ $IMAGE_COUNT -eq 0 ]]; then
    echo "# AI搜索不可用，创建占位符图片" >&2

    # 使用ImageMagick创建简单占位符
    if command -v magick &> /dev/null || command -v convert &> /dev/null; then
        for i in {0..2}; do
            PLACEHOLDER="$IMAGES_DIR/image_${i}.jpg"

            if command -v magick &> /dev/null; then
                MAGICK="magick"
            else
                MAGICK="convert"
            fi

            # 创建渐变占位符
            "$MAGICK" -size "800x600" gradient:"#302b63-#24243e" \
                -pointsize 48 -fill white -gravity center \
                -annotate 0 "$TOPIC" \
                "$PLACEHOLDER" 2>/dev/null

            if [[ -f "$PLACEHOLDER" ]]; then
                echo "# ✓ 创建占位符: $(basename $PLACEHOLDER)" >&2
            fi
        done
    fi
fi

# 更新 session.json
PYTHONIOENCODING=utf-8 python3 << EOF
# -*- coding: utf-8 -*-
import json
from datetime import datetime

with open('$SESSION_DIR/session.json') as f:
    session = json.load(f)

session['status'] = 'images_searched'
session['steps']['images'] = True
session['images_updated_at'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
session['images_count'] = $IMAGE_COUNT

with open('$SESSION_DIR/session.json', 'w') as f:
    json.dump(session, f, ensure_ascii=False, indent=2)
EOF

echo "# ✓ 图片搜索完成，共 $IMAGE_COUNT 张" >&2
echo "$IMAGES_DIR"
