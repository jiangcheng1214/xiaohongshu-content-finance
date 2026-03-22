#!/bin/bash
# Telegram Hook Handler - 确定性模式
# 防止AI过度解读用户输入

MESSAGE="${1:-}"
CHAT_ID="${2:-}"

if [[ -z "$MESSAGE" ]]; then
    echo "用法: $0 <message_content> [chat_id]" >&2
    exit 1
fi

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_DIR="$SKILL_DIR/scripts"

# 默认垂类
VERTICAL="finance"
TOPIC=""

# 解析消息 - 更严格的规则
infer_vertical_and_topic() {
    local msg="$1"

    # 只处理明确的垂类前缀格式
    if [[ "$msg" =~ ^(finance|金融|beauty|美妆|tech|科技):[[:space:]]+(.+)$ ]]; then
        # 提取垂类
        prefix="${BASH_REMATCH[1]}"
        case "$prefix" in
            finance|金融) VERTICAL="finance" ;;
            beauty|美妆) VERTICAL="beauty" ;;
            tech|科技) VERTICAL="tech" ;;
        esac
        TOPIC="${BASH_REMATCH[2]}"
    else
        # 没有明确垂类前缀，使用默认但保持原样
        VERTICAL="finance"
        TOPIC="$msg"
    fi
}

infer_vertical_and_topic "$MESSAGE"

echo "# === Telegram Hook（确定性模式）===" >&2
echo "# 原始消息: $MESSAGE" >&2
echo "# 垂类: $VERTICAL" >&2
echo "# 话题: $TOPIC" >&2
echo "# ⚠️ 使用精确输入，不做AI纠正" >&2

# 发送开始消息
if [[ -n "$CHAT_ID" ]]; then
    openclaw message send --channel telegram --message "📱 开始生成（确定性模式）
📌 话题: $TOPIC
📂 垂类: $VERTICAL
⚠️ 使用精确输入" --target "$CHAT_ID" 2>/dev/null || true
fi

# 调用确定性工作流
SESSION_DIR=$("$SCRIPT_DIR/xhs_generate.sh" "$VERTICAL" "$TOPIC" --all 2>&1)

# 提取session目录
SESSION_PATH=$(echo "$SESSION_DIR" | grep -o '/Users/[^[:space:]]*xhs_session_[^[:space:]]*' | head -1)

# 发送结果
if [[ -n "$CHAT_ID" && -d "$SESSION_PATH" ]]; then
    CONTENT=$(cat "$SESSION_PATH/content.md" 2>/dev/null || echo "内容生成失败")
    COVER="$SESSION_PATH/cover.png"
    IMAGES="$SESSION_PATH/images"
    TITLE=$(grep '^# ' "$SESSION_PATH/content.md" | head -1 | sed 's/^# //')

    # 验证标题匹配
    if [[ ! "$TITLE" == *"$TOPIC"* ]]; then
        echo "# ⚠️ 警告: 生成标题与输入不匹配" >&2
        echo "# 输入: $TOPIC" >&2
        echo "# 标题: $TITLE" >&2
    fi

    # 发送到Telegram
    "$SCRIPT_DIR/send_telegram.sh" "$TITLE" "$CONTENT" "$COVER" "$IMAGES"

    # 更新session
    python3 << EOF
import json
with open('$SESSION_PATH/session.json') as f:
    s = json.load(f)
s['status'] = 'sent'
s['steps']['sent'] = True
s['sent_at'] = "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
s['triggered_by'] = 'telegram'
s['original_message'] = '$MESSAGE'
s['mode'] = 'strict'
with open('$SESSION_PATH/session.json', 'w') as f:
    json.dump(s, f, ensure_ascii=False, indent=2)
EOF
fi

echo "$SESSION_PATH"
