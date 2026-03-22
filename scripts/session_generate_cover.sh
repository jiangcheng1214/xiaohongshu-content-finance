#!/bin/bash
# 步骤: 封面生成（写入session目录）
# 用法: ./session_generate_cover.sh <session_dir> [title] [subtitle]

set -e

SESSION_DIR="${1:-}"
TITLE="${2:-}"
SUBTITLE="${3:-}"

if [[ -z "$SESSION_DIR" || ! -d "$SESSION_DIR" ]]; then
    echo "用法: $0 <session_dir> [title] [subtitle]" >&2
    exit 1
fi

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_DIR="$SKILL_DIR/scripts"

# 读取 session.json
VERTICAL=$(python3 -c "import json; print(json.load(open('$SESSION_DIR/session.json'))['vertical'])")

# 如果没有提供 title/subtitle，尝试从 content.md 提取
if [[ -z "$TITLE" ]]; then
    TITLE=$(grep '^# ' "$SESSION_DIR/content.md" | head -1 | sed 's/^# //')
fi
if [[ -z "$TITLE" ]]; then
    TITLE=$(python3 -c "import json; print(json.load(open('$SESSION_DIR/session.json'))['topic'])")
fi

echo "# === 封面生成 ===" >&2
echo "# Title: $TITLE" >&2
echo "# Subtitle: ${SUBTITLE:-}" >&2
echo "# Vertical: $VERTICAL" >&2

# 生成封面到 session 目录
COVER_OUTPUT="$SESSION_DIR/cover.png"

# 直接调用 generate_cover.sh 输出到 session 目录
"$SCRIPT_DIR/generate_cover.sh" "$VERTICAL" "$TITLE" "${SUBTITLE:-}" "$COVER_OUTPUT" >/dev/null 2>&1

# 检查封面是否生成成功
if [[ -f "$COVER_OUTPUT" ]]; then
    # 更新 session.json
    python3 << EOF
import json
with open('$SESSION_DIR/session.json') as f:
    session = json.load(f)
session['status'] = 'cover_generated'
session['steps']['cover'] = True
session['cover_updated_at'] = "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
with open('$SESSION_DIR/session.json', 'w') as f:
    json.dump(session, f, ensure_ascii=False, indent=2)
EOF

    echo "# ✓ 封面已保存到 session/cover.png" >&2
    echo "$COVER_OUTPUT"
else
    echo "# ✗ 封面生成失败" >&2
    exit 1
fi
