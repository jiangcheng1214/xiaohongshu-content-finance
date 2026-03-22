#!/bin/bash
# 初始化小红书生成会话
# 用法: ./session_init.sh <垂类> <话题>
# 输出: 会话目录路径

set -e

VERTICAL="${1:-finance}"
TOPIC="${2:-}"

if [[ -z "$TOPIC" ]]; then
    echo "用法: $0 <垂类> <话题>" >&2
    exit 1
fi

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE="$HOME/.openclaw/agents/main/agent"

# 读取垂类配置中的 generation_mode
GENERATION_MODE=$(python3 -c "import json; print(json.load(open('$SKILL_DIR/verticals/$VERTICAL.json')).get('generation_mode', 'strict'))" 2>/dev/null || echo "strict")

# 生成安全的目录名
SAFE_TOPIC=$(echo "$TOPIC" | tr ' ' '_' | tr '/' '_' | tr '\\' '_' | tr -d '[:punct:]' | cut -c1-20)
TIMESTAMP=$(date +%s)
SESSION_DIR="$WORKSPACE/xhs_session_${TIMESTAMP}_${SAFE_TOPIC}"

# 创建会话目录结构
mkdir -p "$SESSION_DIR/images"

# 创建 session.json
cat > "$SESSION_DIR/session.json" << EOF
{
  "topic": "$TOPIC",
  "vertical": "$VERTICAL",
  "safe_topic": "$SAFE_TOPIC",
  "timestamp": $TIMESTAMP,
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "status": "initialized",
  "generation_mode": "$GENERATION_MODE",
  "steps": {
    "research": false,
    "images": false,
    "content": false,
    "cover": false,
    "sent": false
  }
}
EOF

# 创建空的 content.md
cat > "$SESSION_DIR/content.md" << EOF
# $TOPIC

_内容待生成..._
EOF

# 创建空的 manifest
cat > "$SESSION_DIR/images/manifest.txt" << EOF
# Topic: $TOPIC
# Vertical: $VERTICAL
# Session: xhs_session_${TIMESTAMP}_${SAFE_TOPIC}
EOF

echo "# 会话已初始化" >&2
echo "# 目录: $SESSION_DIR" >&2
echo "$SESSION_DIR"
