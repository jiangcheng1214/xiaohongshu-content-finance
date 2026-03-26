#!/bin/bash
# 小红书内容生成 - 主工作流（deterministic session-based）
# 用法: ./xhs_generate.sh <垂类> <话题> [--init|--images|--content|--cover|--info|--all|--send]

set -e

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_DIR="$SKILL_DIR/scripts"
WORKSPACE="$HOME/.openclaw/agents/main/agent"

VERTICAL="${1:-finance}"
TOPIC="${2:-}"
ACTION="${3:---all}"

if [[ -z "$TOPIC" ]]; then
    echo "用法: $0 <垂类> <话题> [action]" >&2
    echo "" >&2
    echo "Actions:" >&2
    echo "  --init    初始化新session" >&2
    echo "  --content 生成文字内容" >&2
    echo "  --cover   生成封面" >&2
    echo "  --info    显示session信息" >&2
    echo "  --all     执行全部步骤 (默认)" >&2
    echo "  --send    发送到Telegram" >&2
    exit 1
fi

# 查找或创建session
SAFE_TOPIC=$(echo "$TOPIC" | tr ' ' '_' | tr '/' '_' | tr -d '[:punct:]' | cut -c1-20)

# 查找现有session
EXISTING_SESSION=$(find "$WORKSPACE" -type d -name "xhs_session_*_${SAFE_TOPIC}" 2>/dev/null | sort -r | head -1)

if [[ -n "$EXISTING_SESSION" && -d "$EXISTING_SESSION" ]]; then
    SESSION_DIR="$EXISTING_SESSION"
    echo "# 使用现有session: $SESSION_DIR" >&2
else
    if [[ "$ACTION" == "--info" ]]; then
        echo "# ✗ 没有找到session" >&2
        exit 1
    fi
    # 创建新session
    SESSION_DIR=$("$SCRIPT_DIR/session_init.sh" "$VERTICAL" "$TOPIC" | tr -d '\n')
    echo "# 创建新session: $SESSION_DIR" >&2
fi

# 执行action
case "$ACTION" in
    --init)
        echo "$SESSION_DIR"
        ;;
    --content)
        "$SCRIPT_DIR/session_generate_content.sh" "$SESSION_DIR"
        "$SCRIPT_DIR/session_info.sh" "$SESSION_DIR"
        ;;
    --cover)
        "$SCRIPT_DIR/session_generate_cover.sh" "$SESSION_DIR"
        "$SCRIPT_DIR/session_info.sh" "$SESSION_DIR"
        ;;
    --info)
        "$SCRIPT_DIR/session_info.sh" "$SESSION_DIR"
        ;;
    --all)
        echo "" >&2
        echo "========================================" >&2
        echo "📱 小红书内容生成" >&2
        echo "========================================" >&2
        echo "" >&2

        # 步骤1: 内容生成
        echo "📝 步骤 1/2: 内容生成" >&2
        "$SCRIPT_DIR/session_generate_content.sh" "$SESSION_DIR"
        echo "" >&2

        # 步骤2: 封面生成
        echo "🎨 步骤 2/2: 封面生成" >&2
        "$SCRIPT_DIR/session_generate_cover.sh" "$SESSION_DIR"
        echo "" >&2

        # 显示结果
        "$SCRIPT_DIR/session_info.sh" "$SESSION_DIR"
        echo ""
        echo "✅ 全部完成！Session: $SESSION_DIR"
        # 输出 SESSION_DIR 供 wrapper 捕获
        echo "$SESSION_DIR"
        ;;
    --send)
        # 读取内容并发送
        CONTENT=$(cat "$SESSION_DIR/content.md")
        COVER="$SESSION_DIR/cover.png"
        IMAGES="$SESSION_DIR/images"

        if [[ ! -f "$COVER" ]]; then
            echo "# ✗ 封面不存在，请先运行 --cover" >&2
            exit 1
        fi

        # 提取标题
        TITLE=$(grep '^# ' "$SESSION_DIR/content.md" | head -1 | sed 's/^# //')

        echo "# 发送到Telegram..." >&2
        "$SCRIPT_DIR/send_telegram.sh" "$TITLE" "$CONTENT" "$COVER" "$IMAGES"

        # 更新session
        PYTHONIOENCODING=utf-8 python3 << EOF
# -*- coding: utf-8 -*-
import json
with open('$SESSION_DIR/session.json') as f:
    s = json.load(f)
s['status'] = 'sent'
s['steps']['sent'] = True
s['sent_at'] = "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
with open('$SESSION_DIR/session.json', 'w') as f:
    json.dump(s, f, ensure_ascii=False, indent=2)
EOF
        ;;
    *)
        echo "# ✗ 未知action: $ACTION" >&2
        exit 1
        ;;
esac
