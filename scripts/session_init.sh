#!/bin/bash
# 步骤: Session初始化
# 用法: ./session_init.sh <vertical> <topic>

set -e

VERTICAL="${1:-finance}"
TOPIC="${2:-}"

if [[ -z "$TOPIC" ]]; then
    echo "用法: $0 <vertical> <topic>" >&2
    exit 1
fi

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE="$HOME/.openclaw/agents/main/agent"

# 创建工作目录（如果不存在）
mkdir -p "$WORKSPACE"

# 生成安全的文件名
SAFE_TOPIC=$(echo "$TOPIC" | tr ' ' '_' | tr '/' '_' | tr -d '[:punct:]' | cut -c1-20)
TIMESTAMP=$(date +%s)
SESSION_DIR="$WORKSPACE/xhs_session_${TIMESTAMP}_${SAFE_TOPIC}"

# 检查垂类配置是否存在
VERTICAL_CONFIG="$SKILL_DIR/verticals/$VERTICAL.json"
if [[ ! -f "$VERTICAL_CONFIG" ]]; then
    echo "错误: 垂类配置不存在: $VERTICAL_CONFIG" >&2
    exit 1
fi

# 创建session目录
mkdir -p "$SESSION_DIR"

# 生成session.json
python3 << EOF
import json
from datetime import datetime, timezone

session = {
    "id": "xhs_session_${TIMESTAMP}_${SAFE_TOPIC}",
    "vertical": "$VERTICAL",
    "topic": "$TOPIC",
    "safe_topic": "$SAFE_TOPIC",
    "created_at": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    "status": "initialized",
    "steps": {
        "init": True,
        "content": False,
        "cover": False,
        "sent": False
    },
    "debug": {},
    "config": {
        "vertical": "$VERTICAL"
    }
}

with open('$SESSION_DIR/session.json', 'w') as f:
    json.dump(session, f, ensure_ascii=False, indent=2)
EOF

echo "# Session已创建: $SESSION_DIR" >&2
echo "$SESSION_DIR"
