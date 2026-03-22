#!/bin/bash
# 步骤: 内容生成（写入session目录）- 严格模式
# 用法: ./session_generate_content.sh <session_dir>

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
GENERATION_MODE=$(python3 -c "import json; print(json.load(open('$SESSION_DIR/session.json')).get('generation_mode', 'strict'))")

echo "# === 内容生成 ===" >&2
echo "# Topic: $TOPIC" >&2
echo "# Vertical: $VERTICAL" >&2
echo "# Mode: $GENERATION_MODE" >&2

# 根据生成模式选择生成器
if [ "$GENERATION_MODE" = "advanced" ]; then
    echo "# 使用高级模式（配置驱动）" >&2
    python3 "$SCRIPT_DIR/generate_content_advanced.py" "$TOPIC" "$VERTICAL" "$SESSION_DIR/content.md" 2>/dev/null
else
    echo "# 使用严格模式（保持兼容）" >&2
    python3 "$SCRIPT_DIR/generate_content_strict.py" "$TOPIC" "$VERTICAL" "$SESSION_DIR/content.md" 2>/dev/null
fi

# 验证生成的内容包含用户输入的关键词
if ! grep -q "$TOPIC" "$SESSION_DIR/content.md" 2>/dev/null; then
    echo "# ⚠️ 警告: 生成内容可能不包含话题关键词" >&2
fi

# 更新 session.json
python3 << EOF
import json
with open('$SESSION_DIR/session.json') as f:
    session = json.load(f)
session['status'] = 'content_generated'
session['steps']['content'] = True
session['content_updated_at'] = "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
session['content_mode'] = session.get('generation_mode', 'strict')
with open('$SESSION_DIR/session.json', 'w') as f:
    json.dump(session, f, ensure_ascii=False, indent=2)
EOF

echo "# ✓ 内容已保存到 session/content.md" >&2
echo "$SESSION_DIR/content.md"
