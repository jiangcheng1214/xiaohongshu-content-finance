#!/bin/bash
# 生成小红书封面图（3:4 竖版）- 底层脚本
#
# 【重要】此脚本只能接受标准4参数格式
# 用法: ./generate_cover.sh <vertical> <title> <subtitle> <output_path>
#
# 调用规范：
#   - 外部调用必须通过 session_generate_cover.sh
#   - 不要直接调用此脚本
#   - 参数必须完整：vertical title subtitle output

set -e

# 参数验证
if [[ $# -ne 4 ]]; then
    echo "错误: generate_cover.sh 需要4个参数" >&2
    echo "用法: $0 <vertical> <title> <subtitle> <output_path>" >&2
    echo "" >&2
    echo "调用规范:" >&2
    echo "  请使用 session_generate_cover.sh 作为入口" >&2
    echo "  或确保传递4个参数: vertical title subtitle output_path" >&2
    exit 1
fi

VERTICAL="$1"
TITLE="$2"
SUBTITLE="$3"
OUTPUT="$4"

# 参数非空验证
if [[ -z "$VERTICAL" ]] || [[ -z "$TITLE" ]] || [[ -z "$OUTPUT" ]]; then
    echo "错误: vertical, title, output_path 不能为空" >&2
    exit 1
fi

# 技能目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMP_BG="/tmp/xhs_cover_bg_$(date +%s).png"
NANO_BANANA_SCRIPT="$SCRIPT_DIR/lib/generate_image.py"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# 加载垂类配置
VERTICAL_CONFIG="$SKILL_DIR/verticals/$VERTICAL.json"

# 检查垂类配置是否存在
if [[ ! -f "$VERTICAL_CONFIG" ]]; then
    echo "Warning: Vertical config not found: $VERTICAL_CONFIG" >&2
    echo "Using default finance configuration" >&2
    VERTICAL_CONFIG="$SKILL_DIR/verticals/finance.json"
fi

# 获取 Logo 路径（带三级回退逻辑）
get_logo_path() {
    local config="$1"
    local skill_dir="$2"

    # 1. 尝试配置中的 logo_file
    local logo_file=$(python3 -c "import json; c=json.load(open('$config')); print(c['cover_config'].get('logo_file', ''))" 2>/dev/null || echo "")
    if [[ -n "$logo_file" ]]; then
        local config_path="$skill_dir/assets/logo/$logo_file"
        if [[ -f "$config_path" ]]; then
            echo "$config_path"
            return 0
        fi
    fi

    # 2. 尝试 {vertical}.png
    local vertical_path="$skill_dir/assets/logo/$VERTICAL.png"
    if [[ -f "$vertical_path" ]]; then
        echo "$vertical_path"
        return 0
    fi

    # 3. 回退到 default.png
    echo "$skill_dir/assets/logo/default.png"
    return 0
}

LOGO_PATH=$(get_logo_path "$VERTICAL_CONFIG" "$SKILL_DIR")

# 提取其他配置
DEFAULT_SUBTITLE=$(python3 -c "import json; c=json.load(open('$VERTICAL_CONFIG')); print(c['cover_config'].get('default_subtitle'))" 2>/dev/null || echo "分享")
STYLE_PREFIX=$(python3 -c "import json; c=json.load(open('$VERTICAL_CONFIG')); print(c['cover_config'].get('style_prefix', 'Modern background'))" 2>/dev/null || echo "Modern background")

# 如果没有提供副标题，使用垂类默认值
if [[ -z "$SUBTITLE" ]]; then
    SUBTITLE="$DEFAULT_SUBTITLE"
fi

# 从 openclaw.json 读取 GEMINI_API_KEY
CONFIG_FILE="$HOME/.openclaw/openclaw.json"
API_KEY=""
if [[ -f "$CONFIG_FILE" ]]; then
    API_KEY=$(cat "$CONFIG_FILE" | python3 -c "
import json, sys
d = json.load(sys.stdin)
key = d.get('env', {}).get('GEMINI_API_KEY', '')
if not key:
    key = d.get('skills', {}).get('entries', {}).get('nano-banana-pro', {}).get('apiKey', '')
if key:
    print(key, end='')
" 2>/dev/null)
fi

# 如果还是没有，尝试环境变量
if [[ -z "$API_KEY" ]]; then
    API_KEY="${GEMINI_API_KEY:-}"
fi

# 检查 API key
if [[ -z "$API_KEY" ]]; then
    echo "# ⚠️ 警告: 未找到 GEMINI_API_KEY" >&2
    echo "# 请在 ~/.openclaw/openclaw.json 中配置 env.GEMINI_API_KEY" >&2
    echo "# 或设置 skills.entries.nano-banana-pro.apiKey" >&2
fi


# 第一步：生成背景图
echo "# Generating background for vertical: $VERTICAL..." >&2

# 检查是否有动态变量配置
HAS_VARIABLES=$(python3 -c "import json; c=json.load(open('$VERTICAL_CONFIG')); vars = c.get('cover_config', {}).get('prompt_variables', {}); print('yes' if vars else 'no')" 2>/dev/null || echo "no")

TEMP_PROMPT=$(mktemp)

# 从 session.json 读取 topic
TOPIC=""
SESSION_JSON=$(dirname "$OUTPUT")/session.json
if [[ -f "$SESSION_JSON" ]]; then
    TOPIC=$(python3 -c "import json; print(json.load(open('$SESSION_JSON')).get('topic', ''))" 2>/dev/null || echo "")
fi

if [[ "$HAS_VARIABLES" == "yes" ]]; then
    # 使用动态 prompt 生成器
    echo "# 检测到 prompt_variables 配置，使用动态生成..." >&2
    python3 "$SCRIPT_DIR/lib/build_dynamic_cover_prompt.py" "$VERTICAL_CONFIG" "$TOPIC" "$VERTICAL" > "$TEMP_PROMPT" 2>&1
    # 移除 stderr 输出的调试信息，只保留 prompt 内容
    grep -v "^#" "$TEMP_PROMPT" > "${TEMP_PROMPT}.tmp" 2>/dev/null || true
    if [[ -f "${TEMP_PROMPT}.tmp" && -s "${TEMP_PROMPT}.tmp" ]]; then
        mv "${TEMP_PROMPT}.tmp" "$TEMP_PROMPT"
        echo "# ✓ 动态 prompt 生成成功" >&2
    else
        echo "# ⚠️ 动态 prompt 生成失败，使用备用模板" >&2
        get_fallback_prompt
    fi
else
    # 使用静态 prompt 模板
    PROMPT_TEMPLATE=$(python3 -c "import json; c=json.load(open('$VERTICAL_CONFIG')); print(c['cover_config'].get('background_prompt_template', ''))" 2>/dev/null || echo "")

    if [[ -n "$PROMPT_TEMPLATE" ]]; then
        echo "$PROMPT_TEMPLATE" > "$TEMP_PROMPT"
        echo "# 使用静态 prompt 模板" >&2
    else
        get_fallback_prompt
    fi
fi

# 备用 prompt 函数
get_fallback_prompt() {
    echo "$STYLE_PREFIX, clean modern background, 3:4 portrait, no text" > "$TEMP_PROMPT"
    echo "# 使用默认 prompt" >&2
}

echo "# Prompt: $(cat $TEMP_PROMPT)" >&2
echo "# Logo: $(basename $LOGO_PATH)" >&2
echo "# Subtitle: ${SUBTITLE}" >&2

# 尝试生成背景图 - 使用 nano banana pro
echo "# 调用 nano banana pro 生成背景..." >&2

# 获取 aspect_ratio，默认 3:4
ASPECT_RATIO=$(python3 -c "import json; c=json.load(open('$VERTICAL_CONFIG')); print(c.get('cover_config', {}).get('aspect_ratio', '3:4'))" 2>/dev/null || echo "3:4")
echo "# Aspect Ratio: $ASPECT_RATIO" >&2

# 构建并执行 API 命令 - 使用 Python 避免 shell 引号问题
echo "# 执行 nano banana pro 生图..." >&2
python3 - "$NANO_BANANA_SCRIPT" "$TEMP_PROMPT" "$TEMP_BG" "$ASPECT_RATIO" "$API_KEY" << 'PYEOF'
import subprocess, sys

script = sys.argv[1]
prompt_file = sys.argv[2]
output_file = sys.argv[3]
aspect_ratio = sys.argv[4]
api_key = sys.argv[5] if len(sys.argv) > 5 else ""

with open(prompt_file) as f:
    prompt = f.read().strip()

cmd = ["uv", "run", script, "--prompt", prompt, "--filename", output_file, "--resolution", "1K"]
if api_key:
    cmd.extend(["--api-key", api_key])

result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
with open("/tmp/cover_gen_output.txt", "w") as f:
    f.write(result.stdout + "\n" + result.stderr)
sys.exit(result.returncode)
PYEOF
API_EXIT_CODE=$?

echo "# API 退出码: $API_EXIT_CODE" >&2

# 检查是否成功
if [[ -f "$TEMP_BG" ]]; then
    FILE_SIZE=$(stat -f%z "$TEMP_BG" 2>/dev/null || stat -c%s "$TEMP_BG" 2>/dev/null || echo "0")
    echo "# ✓ 背景生成成功，大小: ${FILE_SIZE} bytes" >&2

    # 检查文件大小，如果太小可能是错误图片
    if [[ $FILE_SIZE -lt 1000 ]]; then
        echo "# ⚠️ 警告: 生成的图片太小，可能是错误" >&2
        cat /tmp/cover_gen_output.txt >&2
    fi
else
    echo "# ✗ 背景生成失败！" >&2
    echo "# 输出:" >&2
    cat /tmp/cover_gen_output.txt >&2
    echo "" >&2
    echo "# 提示: 请检查 nano banana pro 是否正确安装" >&2
    echo "# 脚本路径: $NANO_BANANA_SCRIPT" >&2
    rm -f /tmp/cover_gen_output.txt
    exit 1
fi

rm -f /tmp/cover_gen_output.txt

# 直接使用背景图作为最终输出（不再添加文字叠加）
mv "$TEMP_BG" "$OUTPUT"

# 清理临时文件
rm -f "$TEMP_PROMPT"

# 输出封面路径
echo "$OUTPUT"
