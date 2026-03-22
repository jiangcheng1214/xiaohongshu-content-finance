#!/bin/bash
# AI驱动智能配图搜索 - bash 包装脚本
# 用法: ./ai_search_images.sh <垂类> <话题> [数量]

VERTICAL="${1:-finance}"
TOPIC="${2:-}"
COUNT="${3:-3}"

if [[ -z "$TOPIC" ]]; then
    echo "用法: $0 <垂类> <话题> [数量]" >&2
    exit 1
fi

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_DIR="$SKILL_DIR/scripts"
WORKSPACE="$HOME/.openclaw/agents/main/agent"

# 生成目录名
SAFE_TOPIC=$(echo "$TOPIC" | tr ' ' '_' | tr '/' '_' | cut -c1-15)
TIMESTAMP=$(date +%s)
OUTPUT_DIR="$WORKSPACE/xhs_images_${TIMESTAMP}_${SAFE_TOPIC}"

# 调用 Python 脚本
TEMP_JSON=$(mktemp)
python3 "$SCRIPT_DIR/ai_image_search.py" "$VERTICAL" "$TOPIC" "$OUTPUT_DIR" "$COUNT" 2>/dev/null > "$TEMP_JSON"

# 解析结果
PARSED=$(python3 -c "
import json
with open('$TEMP_JSON') as f:
    data = json.load(f)
    if data.get('status') == 'success':
        print(f\"SUCCESS|{data.get('output_dir', '')}|{','.join(data.get('intent', []))}|{data.get('downloaded_count', 0)}\")
    else:
        print('FAIL')
")

rm -f "$TEMP_JSON"

# 检查结果
if [[ "$PARSED" == SUCCESS* ]]; then
    IFS='|' read -r STATUS DIR INTENT COUNT <<< "$PARSED"
    echo "# ✓ 成功下载 $COUNT 张图片" >&2
    echo "# 话题类型: $INTENT" >&2
    echo "# 目录: $DIR" >&2
    echo "$DIR"

    # 显示搜索计划详情
    PLAN_FILE="$DIR/search_plan.json"
    if [[ -f "$PLAN_FILE" ]]; then
        echo "" >&2
        echo "# === 搜索计划详情 ===" >&2
        python3 << EOF
import json
with open('$PLAN_FILE') as f:
    plan = json.load(f)
    print(f"图片需求: {len(plan.get('image_requirements', []))} 种")
    for req in plan.get('image_requirements', []):
        print(f"  - {req['type']}: {req['description']}")
EOF
    fi

    exit 0
else
    echo "# ✗ 自动搜索失败" >&2
    exit 1
fi
