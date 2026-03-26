#!/bin/bash
# 步骤: 内容生成（写入session目录）
# 用法: ./session_generate_content.sh <session_dir>

set -e

SESSION_DIR="${1:-}"

if [[ -z "$SESSION_DIR" || ! -d "$SESSION_DIR" ]]; then
    echo "用法: $0 <session_dir>" >&2
    exit 1
fi

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_DIR="$SKILL_DIR/scripts"

# 读取 session.json
TOPIC=$(python3 -c "import json; print(json.load(open('$SESSION_DIR/session.json'))['topic'])")
VERTICAL=$(python3 -c "import json; print(json.load(open('$SESSION_DIR/session.json'))['vertical'])")

echo "# === 内容生成 ===" >&2
echo "# Topic: $TOPIC" >&2
echo "# Vertical: $VERTICAL" >&2

# 读取垂类配置和人设
VERTICAL_CONFIG="$SKILL_DIR/verticals/$VERTICAL.json"
PERSONA_FILE="$SKILL_DIR/personas/$VERTICAL.md"

# 检查配置文件是否存在
if [[ ! -f "$VERTICAL_CONFIG" ]]; then
    echo "错误: 垂类配置不存在: $VERTICAL_CONFIG" >&2
    exit 1
fi

if [[ ! -f "$PERSONA_FILE" ]]; then
    echo "警告: 人设文件不存在: $PERSONA_FILE，使用默认人设" >&2
    PERSONA_FILE=""
fi

# 生成内容（调用Claude API）
CONTENT_OUTPUT="$SESSION_DIR/content.md"

# 使用 Python 脚本加载模板并构建 prompt
PROMPT_FILE=$(mktemp)
PERSONA_ARG="${PERSONA_FILE:-None}"
"$SCRIPT_DIR/lib/build_prompt.py" "$VERTICAL_CONFIG" "$PERSONA_ARG" "$TOPIC" "$VERTICAL" > "$PROMPT_FILE"
if [[ $? -ne 0 ]]; then
    echo "错误: Prompt 生成失败" >&2
    exit 1
fi

# 调用Claude API生成内容 - 使用构建好的 prompt
echo "# 正在调用 Claude API 生成内容..." >&2

# 读取构建的 prompt 并调用 Claude
PROMPT_CONTENT=$(cat "$PROMPT_FILE")
CONTENT=$(claude --dangerously-skip-permissions -p "$PROMPT_CONTENT" 2>/dev/null || echo "")

# 清理prompt文件
rm -f "$PROMPT_FILE"

# 如果生成失败或为空，使用备用模板
if [[ -z "$CONTENT" ]] || [[ "$CONTENT" == *"我注意到你提供的话题是空的"* ]] || [[ "$CONTENT" == *"请提供产品名称"* ]]; then
    echo "# Claude API 调用失败，使用备用模板" >&2

    # 生成备用标题（使用话题前缀）
    case "$VERTICAL" in
        stock)
            TITLE="${TOPIC:0:8}值得买吗"
            ;;
        tech|beauty|finance)
            TITLE="${TOPIC:0:10}深度解析"
            ;;
        *)
            TITLE="${TOPIC:0:10}分析"
            ;;
    esac

    # 生成更好的备用内容
    case "$VERTICAL" in
        tech)
            cat > "$CONTENT_OUTPUT" << EOF
# $TITLE

直接说结论。

$TOPIC 这款产品，定位明确。

处理器、内存、屏幕这些核心参数决定了使用体验。跑分只是参考，实际体验更重要。

流畅度、续航、信号。这些日常使用感受比参数更实在。

和同类产品比，各有优势。看你的使用场景和预算。

值不值，看性价比。同类产品价格差异不大，关键是看需求匹配。

适合数码爱好者，参数党持续分享。

#数码 #科技 #评测
EOF
            ;;
        beauty)
            cat > "$CONTENT_OUTPUT" << EOF
# $TITLE

直接说结论。

$TOPIC 这个产品，品牌靠谱，价格适中。

质地、延展性、上脸感受。这些直接决定使用体验。

实际效果、持妆度、遮瑕力。看真实测评，别光看宣传。

什么肤质适合/不适合。干皮油皮敏感肌，选择不同。

值不值，有平替吗。同类产品很多，对比后再决定。

美妆测评，持续分享每次原创。

#美妆 #护肤 #测评
EOF
            ;;
        finance)
            cat > "$CONTENT_OUTPUT" << EOF
# $TITLE

直接说结论。

关于$TOPIC，数据摆在那。

具体数字、同比环比、时间戳，必须解释数据含义。

贵不贵，跟同类比，历史分位。现在的价格位置决定安全边际。

量化分析，持续分享每次原创。

⚠️ 以上仅供参考，市场有风险，投资需谨慎

#股票 #投资 #量化
EOF
            ;;
        stock)
            cat > "$CONTENT_OUTPUT" << EOF
# $TITLE

直接说结论。

关于$TOPIC，需要从数据和业务两个角度看。

最新财报数据是基础，营收、利润、增长率这些硬指标摆在那。超预期还是不及预期，市场反应不会骗人。

核心业务分析看增长驱动。哪个业务在涨，为什么，护城河够不够深。行业地位决定定价权，龙头才有超额收益。

估值位置决定安全边际。PE/PB 历史分位，和同行比贵不贵。便宜不是买入理由，但好价格需要耐心等。

风险不能不提。行业风险、公司风险、估值风险，实事求是。

操作建议：买入/持有/卖出，给明确判断，不骑墙。

深度个股分析，持续分享，每次原创。

⚠️ 以上分析仅供参考，不构成投资建议

#股票 #个股分析 #财报 #投资
EOF
            ;;
        *)
            cat > "$CONTENT_OUTPUT" << EOF
# $TITLE

直接说结论。

关于$TOPIC，需要结合具体情况分析。

持续分享，每次原创。

#分享 #干货
EOF
            ;;
    esac
# $TITLE

直接说结论。

关于$TOPIC，数据摆在那。

需要结合具体情况分析。

$SUBTITLE，持续分享每次原创。

#分享 #干货
EOF
else
    # 保存生成的内容
    echo "$CONTENT" > "$CONTENT_OUTPUT"
fi

# 验证生成的内容包含用户输入的关键词
if ! grep -q "$TOPIC" "$CONTENT_OUTPUT" 2>/dev/null; then
    echo "# ⚠️ 警告: 生成内容可能不包含话题关键词" >&2
fi

# 更新 session.json，添加 debug 信息
CONTENT_LENGTH=$(wc -c < "$CONTENT_OUTPUT" 2>/dev/null || echo "0")
WORD_COUNT=$(wc -w < "$CONTENT_OUTPUT" 2>/dev/null || echo "0")
PERSONA_EXISTS="False"
if [[ -n "$PERSONA_FILE" && -f "$PERSONA_FILE" ]]; then
    PERSONA_EXISTS="True"
fi
GENERATION_MODE=$(python3 -c "import json; c=json.load(open('$VERTICAL_CONFIG')); print(c.get('generation_mode', 'strict'))")

# 【核心】从 LLM 生成的内容中提取主标题和副标题
# LLM 必须按格式输出：
# 【主标题】xxxxx
# 【副标题】xxxxx
# 正文内容...

# 提取主标题和副标题
MAIN_TITLE=$(grep '^【主标题】' "$CONTENT_OUTPUT" | sed 's/^【主标题】//' | head -1)
SUBTITLE=$(grep '^【副标题】' "$CONTENT_OUTPUT" | sed 's/^【副标题】//' | head -1)

# 如果正则提取失败，尝试从前两行直接提取（降级方案）
if [[ -z "$MAIN_TITLE" ]]; then
    MAIN_TITLE=$(head -n 5 "$CONTENT_OUTPUT" | grep -v '^$' | head -n 1 | sed 's/^[#*【 ]*//;s/[#*】 ]*$//')
fi
if [[ -z "$SUBTITLE" ]]; then
    SUBTITLE=$(head -n 5 "$CONTENT_OUTPUT" | grep -v '^$' | sed -n '2p' | sed 's/^[#*【 ]*//;s/[#*】 ]*$//')
fi

# 验证提取结果 - 必须要有标题，否则报错
if [[ -z "$MAIN_TITLE" ]] || [[ -z "$SUBTITLE" ]]; then
    echo "# ✗ 错误: 无法解析生成内容中的主标题和副标题" >&2
    echo "# 请检查生成格式，预期为前两行或包含【主标题】【副标题】" >&2
    exit 1
fi

echo "# 提取到主标题: $MAIN_TITLE" >&2
echo "# 提取到副标题: $SUBTITLE" >&2

# 清理内容中的标题标记，只保留正文
# 移除【主标题】和【副标题】行，保留正文内容
TEMP_CONTENT=$(mktemp)
grep -v '^【主标题】' "$CONTENT_OUTPUT" | grep -v '^【副标题】' > "$TEMP_CONTENT"
mv "$TEMP_CONTENT" "$CONTENT_OUTPUT"

# 从 content.md 提取第一行作为参考（用于调试）
FULL_TITLE=$(grep '^# ' "$CONTENT_OUTPUT" | head -1 | sed 's/^# //' || echo "$MAIN_TITLE")

# 使用 Python 更新 session.json，确保正确转义
python3 - "$SESSION_DIR" "$VERTICAL" "$TOPIC" "$FULL_TITLE" "$MAIN_TITLE" "$SUBTITLE" "$PERSONA_FILE" "$CONTENT_OUTPUT" "$CONTENT_LENGTH" "$WORD_COUNT" "$GENERATION_MODE" << 'PYEOF'
import json
import sys
from datetime import datetime, timezone

SESSION_DIR = sys.argv[1]
VERTICAL = sys.argv[2]
TOPIC = sys.argv[3]
FULL_TITLE = sys.argv[4]
MAIN_TITLE = sys.argv[5]
SUBTITLE = sys.argv[6]
PERSONA_FILE = sys.argv[7] if len(sys.argv) > 7 else ""
CONTENT_OUTPUT = sys.argv[8] if len(sys.argv) > 8 else ""
CONTENT_LENGTH = int(sys.argv[9]) if len(sys.argv) > 9 else 0
WORD_COUNT = int(sys.argv[10]) if len(sys.argv) > 10 else 0
GENERATION_MODE = sys.argv[11] if len(sys.argv) > 11 else "strict"

with open(f'{SESSION_DIR}/session.json') as f:
    session = json.load(f)

session['status'] = 'content_generated'
session['steps']['content'] = True
session['content_updated_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

# 【核心】存储标题和副标题到 session.json 顶层字段
# 这是封面生成的唯一数据源
session['title'] = MAIN_TITLE
session['subtitle'] = SUBTITLE

# 添加 debug 信息
session['debug'] = session.get('debug', {})
session['debug']['content'] = {
    'vertical': VERTICAL,
    'topic': TOPIC,
    'full_title': FULL_TITLE,
    'title': MAIN_TITLE,
    'subtitle': SUBTITLE,
    'persona_file': PERSONA_FILE,
    'persona_exists': bool(PERSONA_FILE),
    'output_file': CONTENT_OUTPUT,
    'content_length': CONTENT_LENGTH,
    'word_count': WORD_COUNT,
    'generation_mode': GENERATION_MODE
}

with open(f'{SESSION_DIR}/session.json', 'w') as f:
    json.dump(session, f, ensure_ascii=False, indent=2)
PYEOF

echo "# ✓ 内容已保存到 session/content.md" >&2
echo "$CONTENT_OUTPUT"
