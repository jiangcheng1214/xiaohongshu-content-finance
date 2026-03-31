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

VERTICAL="${1:-finance}"
TOPIC="${2:-}"

if [[ -z "$TOPIC" ]]; then
    echo "用法: xhs-do <垂类> <精确话题>" >&2
    echo "" >&2
    echo "垂类: finance, stock, tech, beauty, wallpaper" >&2
    echo "" >&2
    echo "示例:" >&2
    echo "  xhs-do finance \"美联储利率\"" >&2
    echo "  xhs-do stock \"AAPL\"" >&2
    echo "  xhs-do tech \"iPhone 16 Pro\"" >&2
    echo "  xhs-do beauty \"雅诗兰黛小棕瓶\"" >&2
    echo "  xhs-do wallpaper \"风景\"" >&2
    exit 1
fi

echo "# === 小红书内容生成 ===" >&2
echo "# 垂类: $VERTICAL" >&2
echo "# 话题: $TOPIC" >&2
echo "" >&2

# 调用 CLI
python3 "$SKILL_DIR/scripts/cli.py" generate "$VERTICAL" "$TOPIC"
