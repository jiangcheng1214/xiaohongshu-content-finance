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
SCRIPT_DIR="$SKILL_DIR/scripts"

# 读取 session.json
TOPIC=$(python3 -c "import json; print(json.load(open('$SESSION_DIR/session.json'))['topic'])")
VERTICAL=$(python3 -c "import json; print(json.load(open('$SESSION_DIR/session.json'))['vertical'])")

echo "# === 图片搜索 ===" >&2
echo "# Topic: $TOPIC" >&2
echo "# Vertical: $VERTICAL" >&2

# 调用 AI 图片搜索，输出到 session 的 images 目录
RESULT=$("$SCRIPT_DIR/ai_search_images.sh" "$VERTICAL" "$TOPIC" 2>&1)

# 提取目录路径（查找以 /Users 开头的行）
IMAGE_DIR=$(echo "$RESULT" | grep -E '^/Users' | head -1 | tr -d '\n')

if [[ -d "$IMAGE_DIR" ]]; then
    # 移动图片到 session 目录
    rm -rf "$SESSION_DIR/images"
    cp -R "$IMAGE_DIR" "$SESSION_DIR/images"
    rm -rf "$IMAGE_DIR"

    # 更新 session.json
    python3 << EOF
import json
with open('$SESSION_DIR/session.json') as f:
    session = json.load(f)
session['status'] = 'images_collected'
session['steps']['images'] = True
session['image_count'] = len([f for f in __import__('os').listdir('$SESSION_DIR/images') if f.endswith(('.jpg', '.png', '.jpeg'))])
with open('$SESSION_DIR/session.json', 'w') as f:
    json.dump(session, f, ensure_ascii=False, indent=2)
EOF

    echo "# ✓ 图片已保存到 session/images/" >&2
    echo "$SESSION_DIR/images"
else
    echo "# ✗ 图片搜索失败" >&2
    exit 1
fi
