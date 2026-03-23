#!/bin/bash
# 步骤: 封面生成（写入session目录）
# 用法: ./session_generate_cover.sh <session_dir> [title] [subtitle]

set -e

SESSION_DIR="${1:-}"
TITLE="${2:-}"
SUBTITLE="${3:-}"

if [[ -z "$SESSION_DIR" || ! -d "$SESSION_DIR" ]]; then
    echo "用法: $0 <session_dir> [title] [subtitle]" >&2
    exit 1
fi

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 如果当前目录是 scripts，SKILL_DIR 需要指向父目录
if [[ "$(basename "$SKILL_DIR")" == "scripts" ]]; then
    SKILL_DIR="$(dirname "$SKILL_DIR")"
fi
SCRIPT_DIR="$SKILL_DIR/scripts"

# 读取 session.json
VERTICAL=$(python3 -c "import json; print(json.load(open('$SESSION_DIR/session.json'))['vertical'])")

# 读取垂类配置获取 prompt
VERTICAL_CONFIG="$SKILL_DIR/verticals/$VERTICAL.json"
PROMPT_TEMPLATE=$(python3 -c "import json; c=json.load(open('$VERTICAL_CONFIG')); print(c['cover_config'].get('background_prompt_template', ''))" 2>/dev/null || echo "")

# 【核心逻辑】从 session.json 读取 title 和 subtitle
# 这两个字段由内容生成步骤负责写入
TITLE_SUBTITLE=$(python3 - "$SESSION_DIR" "$TITLE" "$SUBTITLE" << 'PYEOF'
import json
import sys

SESSION_DIR = sys.argv[1]
CMDLINE_TITLE = sys.argv[2] if len(sys.argv) > 2 else None
CMDLINE_SUBTITLE = sys.argv[3] if len(sys.argv) > 3 else None

with open(f'{SESSION_DIR}/session.json') as f:
    session = json.load(f)

# 命令行参数优先（用于手动覆盖）
if CMDLINE_TITLE:
    title = CMDLINE_TITLE
else:
    title = session.get('title')
    if not title:
        print(f"ERROR:NOT_FOUND:title", file=sys.stderr)
        sys.exit(1)

if CMDLINE_SUBTITLE:
    subtitle = CMDLINE_SUBTITLE
else:
    subtitle = session.get('subtitle', '')
    if not subtitle:
        print(f"ERROR:NOT_FOUND:subtitle", file=sys.stderr)
        # 副标题为空不是致命错误，使用空字符串
        subtitle = ""

print(f"{title}|{subtitle}")
PYEOF
)

# 检查是否出错
if [[ "$TITLE_SUBTITLE" == ERROR:* ]]; then
    echo "# ✗ $TITLE_SUBTITLE" >&2
    echo "# 请先运行内容生成步骤，或确保 session.json 包含 title 和 subtitle 字段" >&2
    exit 1
fi

# 解析结果
TITLE=$(echo "$TITLE_SUBTITLE" | cut -d'|' -f1)
SUBTITLE=$(echo "$TITLE_SUBTITLE" | cut -d'|' -f2-)

echo "# === 封面生成 ===" >&2
echo "# Title: $TITLE" >&2
echo "# Subtitle: $SUBTITLE" >&2
echo "# Vertical: $VERTICAL" >&2

# 生成封面到 session 目录
COVER_OUTPUT="$SESSION_DIR/cover.png"

# 捕获 generate_cover.sh 的完整输出
COVER_LOG=$(mktemp)
"$SCRIPT_DIR/generate_cover.sh" "$VERTICAL" "$TITLE" "$SUBTITLE" "$COVER_OUTPUT" > "$COVER_LOG" 2>&1
COVER_EXIT_CODE=$?

# 检查封面是否生成成功
if [[ -f "$COVER_OUTPUT" && $COVER_EXIT_CODE -eq 0 ]]; then
    FILE_SIZE=$(stat -f%z "$COVER_OUTPUT" 2>/dev/null || stat -c%s "$COVER_OUTPUT" 2>/dev/null || echo "0")

    # 更新 session.json，包含 debug 信息
    python3 - "$SESSION_DIR" "$VERTICAL" "$TITLE" "$SUBTITLE" "$PROMPT_TEMPLATE" "$COVER_OUTPUT" "$FILE_SIZE" "$COVER_EXIT_CODE" "$COVER_LOG" << 'PYEOF'
import json
import sys
from datetime import datetime, timezone

SESSION_DIR = sys.argv[1]
VERTICAL = sys.argv[2]
TITLE = sys.argv[3]
SUBTITLE = sys.argv[4]
PROMPT_TEMPLATE = sys.argv[5] if len(sys.argv) > 5 else ""
COVER_OUTPUT = sys.argv[6] if len(sys.argv) > 6 else ""
FILE_SIZE = int(sys.argv[7]) if len(sys.argv) > 7 else 0
COVER_EXIT_CODE = int(sys.argv[8]) if len(sys.argv) > 8 else 0
COVER_LOG = sys.argv[9] if len(sys.argv) > 9 else ""

with open(f'{SESSION_DIR}/session.json') as f:
    session = json.load(f)

session['status'] = 'cover_generated'
session['steps']['cover'] = True
session['cover_updated_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

# 添加 debug 信息
session['debug'] = session.get('debug', {})
session['debug']['cover'] = {
    'vertical': VERTICAL,
    'title': TITLE,
    'subtitle': SUBTITLE,
    'prompt_template': PROMPT_TEMPLATE,
    'output_file': COVER_OUTPUT,
    'file_size': FILE_SIZE,
    'exit_code': COVER_EXIT_CODE,
    'log': open(COVER_LOG).read() if COVER_LOG else ''
}

with open(f'{SESSION_DIR}/session.json', 'w') as f:
    json.dump(session, f, ensure_ascii=False, indent=2)
PYEOF
    rm -f "$COVER_LOG"

    echo "# ✓ 封面已保存到 session/cover.png (${FILE_SIZE} bytes)" >&2
    echo "$COVER_OUTPUT"
else
    # 即使失败也记录 debug 信息
    python3 - "$SESSION_DIR" "$VERTICAL" "$TITLE" "$SUBTITLE" "$PROMPT_TEMPLATE" "" "" "$COVER_EXIT_CODE" "$COVER_LOG" << 'PYEOF'
import json
import sys
from datetime import datetime, timezone

SESSION_DIR = sys.argv[1]
VERTICAL = sys.argv[2]
TITLE = sys.argv[3]
SUBTITLE = sys.argv[4]
PROMPT_TEMPLATE = sys.argv[5] if len(sys.argv) > 5 else ""
COVER_EXIT_CODE = int(sys.argv[7]) if len(sys.argv) > 7 else 0
COVER_LOG = sys.argv[9] if len(sys.argv) > 9 else ""

with open(f'{SESSION_DIR}/session.json') as f:
    session = json.load(f)

session['debug'] = session.get('debug', {})
session['debug']['cover'] = {
    'vertical': VERTICAL,
    'title': TITLE,
    'subtitle': SUBTITLE,
    'prompt_template': PROMPT_TEMPLATE,
    'error': 'Cover generation failed',
    'exit_code': COVER_EXIT_CODE,
    'log': open(COVER_LOG).read() if COVER_LOG else ''
}

with open(f'{SESSION_DIR}/session.json', 'w') as f:
    json.dump(session, f, ensure_ascii=False, indent=2)
PYEOF
    rm -f "$COVER_LOG"
    cat "$COVER_LOG" >&2
    echo "# ✗ 封面生成失败" >&2
    exit 1
fi
