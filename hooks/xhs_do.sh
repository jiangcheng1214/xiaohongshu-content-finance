#!/bin/bash
# 小红书内容生成 - 确定性执行命令
# 用法: xhs-do <垂类> "<精确话题>"
#
# 设计原则:
# 1. 话题必须用引号包裹，防止AI解读
# 2. 不做任何自动纠正或推断
# 3. 使用用户提供的精确输入

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_DIR="$SKILL_DIR/scripts"

VERTICAL="${1:-finance}"
TOPIC="${2:-}"

if [[ -z "$TOPIC" ]]; then
    echo "用法: xhs-do <垂类> <精确话题>"
    echo ""
    echo "示例:"
    echo "  xhs-do finance \"错过了lite怎么办\""
    echo "  xhs-do tech \"GTC大会总结\""
    echo "  xhs-do beauty \"春季口红推荐\""
    exit 1
fi

echo "# === 小红书内容生成（确定性模式）===" >&2
echo "# 垂类: $VERTICAL" >&2
echo "# 话题: $TOPIC" >&2
echo "# 模式: STRICT - 使用精确输入，不做AI纠正" >&2
echo "" >&2

# 直接调用工作流，不经过AI解读
SESSION_DIR=$("$SCRIPT_DIR/xhs_generate.sh" "$VERTICAL" "$TOPIC" --all 2>&1)

# 提取session目录
SESSION_PATH=$(echo "$SESSION_DIR" | grep -o '/Users/[^[:space:]]*xhs_session_[^[:space:]]*' | head -1)

if [[ -d "$SESSION_PATH" ]]; then
    echo "" >&2
    echo "# === 生成完成 ===" >&2
    echo "# Session: $SESSION_PATH" >&2
    echo "" >&2

    # 显示生成的标题
    TITLE=$(grep '^# ' "$SESSION_PATH/content.md" | head -1 | sed 's/^# //')
    echo "# 标题: $TITLE" >&2
    echo "" >&2

    # 询问是否发送
    echo "要发送到Telegram吗？执行:" >&2
    echo "  \"$SCRIPT_DIR/send_telegram.sh\" \\"
    echo "    \"$TITLE\" \\"
    echo "    \"\$(cat '$SESSION_PATH/content.md')\" \\"
    echo "    \"$SESSION_PATH/cover.png\" \\"
    echo "    \"$SESSION_PATH/images\"" >&2

    echo "$SESSION_PATH"
else
    echo "# ✗ 生成失败" >&2
    exit 1
fi
