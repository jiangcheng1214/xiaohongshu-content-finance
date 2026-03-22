#!/bin/bash
# 发送到 Telegram（自动检测图片）
# 用法: ./send_telegram.sh "标题" "正文内容" "封面图路径"

TITLE="$1"
BODY="$2"
COVER="${3:-}"
RESEARCH_IMAGES_DIR="${4:-}"
ACCOUNT="${TELEGRAM_ACCOUNT:-default}"
# 优先使用 TELEGRAM_TARGET，其次使用 TELEGRAM_CHAT_ID，最后从配置读取
TARGET="${TELEGRAM_TARGET:-${TELEGRAM_CHAT_ID:-}}"
if [[ -z "$TARGET" ]]; then
    # 尝试从 openclaw 配置读取默认 chat_id
    TARGET=$(grep TELEGRAM_CHAT_ID ~/.openclaw/.env 2>/dev/null | cut -d'=' -f2)
fi
WORKSPACE="$HOME/.openclaw/agents/main/agent"

echo "# send_telegram.sh 开始" >&2
echo "# TITLE=$TITLE" >&2
echo "# COVER=$COVER" >&2

# ============ 自动查找图片目录 ============
if [[ -z "$RESEARCH_IMAGES_DIR" ]]; then
    # 自动查找最新的图片目录
    RESEARCH_IMAGES_DIR=$(find "$WORKSPACE" -type d -name "xhs_images_*" 2>/dev/null | sort -r | head -1)
    if [[ -n "$RESEARCH_IMAGES_DIR" && -d "$RESEARCH_IMAGES_DIR" ]]; then
        # 尝试读取 manifest.txt 中的 topic 信息
        if [[ -f "$RESEARCH_IMAGES_DIR/manifest.txt" ]]; then
            DIR_TOPIC=$(grep "# Topic:" "$RESEARCH_IMAGES_DIR/manifest.txt" 2>/dev/null | cut -d':' -f2- | sed 's/^[[:space:]]*//')
            if [[ -n "$DIR_TOPIC" ]]; then
                echo "# 自动找到图片目录: $RESEARCH_IMAGES_DIR" >&2
                echo "# 图片目录 Topic: $DIR_TOPIC" >&2
                echo "# 当前生成 Topic: $TITLE" >&2
                # 如果 topic 不匹配，发出警告
                if [[ "$DIR_TOPIC" != *"$TITLE"* && "$TITLE" != *"$DIR_TOPIC"* ]]; then
                    echo "# ⚠️ 警告: 图片目录与当前标题不匹配！" >&2
                    echo "#   请为新 topic 重新搜索配图" >&2
                fi
            else
                echo "# 自动找到图片目录: $RESEARCH_IMAGES_DIR" >&2
            fi
        else
            echo "# 自动找到图片目录: $RESEARCH_IMAGES_DIR" >&2
        fi
    fi
fi

# ============ 发送产品图片 ============
if [[ -n "$RESEARCH_IMAGES_DIR" && -d "$RESEARCH_IMAGES_DIR" ]]; then
    IMAGE_FILES=$(find "$RESEARCH_IMAGES_DIR" -type f \( -name "*.jpg" -o -name "*.png" -o -name "*.jpeg" \) 2>/dev/null | head -5)

    if [[ -n "$IMAGE_FILES" ]]; then
        echo "# 找到 $(echo "$IMAGE_FILES" | grep -c .) 张产品图片" >&2

        FIRST=true
        while IFS= read -r img; do
            [[ -z "$img" || ! -f "$img" ]] && continue

            if [[ "$FIRST" == "true" ]]; then
                MSG="📸 产品图片

话题：$TITLE"
                FIRST=false
            else
                MSG=""
            fi

            if [[ -n "$TARGET" ]]; then
                openclaw message send --channel telegram --account "$ACCOUNT" --target "$TARGET" --message "$MSG" --media "$img" 2>&1 | grep -v "^#" || true
            else
                openclaw message send --channel telegram --account "$ACCOUNT" --message "$MSG" --media "$img" 2>&1 | grep -v "^#" || true
            fi
            sleep 0.3
        done <<< "$IMAGE_FILES"
        echo "# 产品图片已发送" >&2
    fi
fi

# ============ 发送封面和内容 ============
MESSAGE="📱 $TITLE

$BODY

---
生成时间: $(date '+%Y-%m-%d %H:%M')"

if [[ -n "$COVER" && -f "$COVER" ]]; then
    echo "# 发送封面和内容" >&2
    if [[ -n "$TARGET" ]]; then
        openclaw message send --channel telegram --account "$ACCOUNT" --target "$TARGET" --message "$MESSAGE" --media "$COVER"
    else
        openclaw message send --channel telegram --account "$ACCOUNT" --message "$MESSAGE" --media "$COVER"
    fi
else
    if [[ -n "$TARGET" ]]; then
        openclaw message send --channel telegram --account "$ACCOUNT" --target "$TARGET" --message "$MESSAGE"
    else
        openclaw message send --channel telegram --account "$ACCOUNT" --message "$MESSAGE"
    fi
fi

echo "# 发送完成" >&2
