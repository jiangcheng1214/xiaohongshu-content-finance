#!/bin/bash
# 小红书内容生成 - 确定性执行命令
# 用法: xhs-do <垂类> "<精确话题>"
#
# 设计原则:
# 1. 话题必须用引号包裹，防止AI解读
# 2. 不做任何自动纠正或推断
# 3. 使用用户提供的精确输入

# 解析实际脚本路径（处理symlink情况）
SCRIPT_SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SCRIPT_SOURCE" ]; do
    SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_SOURCE")" && pwd)"
    SCRIPT_SOURCE="$(readlink "$SCRIPT_SOURCE")"
    [[ $SCRIPT_SOURCE != /* ]] && SCRIPT_SOURCE="$SCRIPT_DIR/$SCRIPT_SOURCE"
done
SKILL_DIR="$(cd "$(dirname "$SCRIPT_SOURCE")/.." && pwd)"
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

# 提取session目录 - 增强 robustness
SESSION_PATH=$(echo "$SESSION_DIR" | grep -o '/Users/[^[:space:]]*xhs_session_[^/[:space:]]*' | head -1)

if [[ -d "$SESSION_PATH" ]]; then
    # 确保 SESSION_PATH 是绝对路径且已经展开
    SESSION_PATH=$(cd "$SESSION_PATH" && pwd)
    
    echo "" >&2
    echo "# === 生成完成 ===" >&2
    echo "# Session: $SESSION_PATH" >&2
    echo "" >&2

    # 显示生成的标题
    TITLE=$(grep '^# ' "$SESSION_PATH/content.md" | head -1 | sed 's/^# //')
    echo "# 标题: $TITLE" >&2
    echo "" >&2

    # 获取完整正文（不含标题行）用于发送
    # CONTENT_BODY=$(sed '1d' "$SESSION_PATH/content.md")
    CONTENT_FULL=$(cat "$SESSION_PATH/content.md")

    # 自动发送到 Telegram
    echo "# 正在自动发送图文到 Telegram..." >&2
    # 关键修复：确保传递给 send_telegram.sh 的是真实的绝对文件路径
    "$SCRIPT_DIR/send_telegram.sh" "$TITLE" "$CONTENT_FULL" "$SESSION_PATH/cover.png" "$SESSION_PATH/images"

    echo "$SESSION_PATH"
else
    echo "# ✗ 生成失败" >&2
    echo "# 调试输出: $SESSION_DIR" >&2
    exit 1
fi
