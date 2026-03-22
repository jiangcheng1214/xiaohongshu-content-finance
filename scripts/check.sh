#!/bin/bash
# 依赖检查脚本
# 用法: ./check.sh

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检查结果
CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_WARNING=0

# 打印检查项
print_check() {
    local name="$1"
    local status="$2"
    local hint="$3"

    case $status in
        "OK")
            echo -e "${GREEN}✓${NC} $name"
            ((CHECKS_PASSED++))
            ;;
        "FAIL")
            echo -e "${RED}✗${NC} $name"
            if [[ -n "$hint" ]]; then
                echo -e "  ${YELLOW}提示: $hint${NC}"
            fi
            ((CHECKS_FAILED++))
            ;;
        "WARN")
            echo -e "${YELLOW}⚠${NC} $name"
            if [[ -n "$hint" ]]; then
                echo -e "  ${YELLOW}提示: $hint${NC}"
            fi
            ((CHECKS_WARNING++))
            ;;
    esac
}

# 检查命令是否存在
check_command() {
    local cmd="$1"
    local install_hint="$2"

    if command -v "$cmd" >/dev/null 2>&1; then
        print_check "$cmd" "OK"
        return 0
    else
        print_check "$cmd" "FAIL" "$install_hint"
        return 1
    fi
}

# 检查环境变量
check_env() {
    local var="$1"
    local hint="$2"

    if [[ -n "${!var}" ]]; then
        print_check "$var" "OK"
        return 0
    else
        print_check "$var" "WARN" "$hint"
        return 1
    fi
}

# 检查文件/目录
check_path() {
    local path="$1"
    local type="$2"  # file or dir
    local hint="$3"

    if [[ "$type" == "file" ]]; then
        if [[ -f "$path" ]]; then
            print_check "$path" "OK"
            return 0
        else
            print_check "$path" "FAIL" "$hint"
            return 1
        fi
    else
        if [[ -d "$path" ]]; then
            print_check "$path" "OK"
            return 0
        else
            print_check "$path" "FAIL" "$hint"
            return 1
        fi
    fi
}

# 主检查流程
main() {
    echo -e "${BLUE}"
    echo "========================================"
    echo "  小红书内容生成引擎 - 依赖检查"
    echo "========================================"
    echo -e "${NC}"

    # 1. 检查必需的二进制命令
    echo "=== 检查二进制命令 ==="
    check_command "magick" "brew install imagemagick"
    check_command "python3" "安装 Python 3.10+"
    check_command "uv" "curl -LsSf https://astral.sh/uv/install.sh | sh"

    # 2. 检查环境变量
    echo ""
    echo "=== 检查环境变量 ==="

    # 从配置文件读取 GEMINI_API_KEY
    OPENCLAW_CONFIG="$HOME/.openclaw/openclaw.json"
    if [[ -f "$OPENCLAW_CONFIG" ]]; then
        API_KEY=$(python3 -c "import json; print(json.load(open('$OPENCLAW_CONFIG')).get('GEMINI_API_KEY', ''))" 2>/dev/null || echo "")
        if [[ -n "$API_KEY" ]]; then
            print_check "GEMINI_API_KEY" "OK"
        else
            print_check "GEMINI_API_KEY" "WARN" "在 ~/.openclaw/openclaw.json 中配置"
        fi
    else
        print_check "GEMINI_API_KEY" "WARN" "创建 ~/.openclaw/openclaw.json 并添加 GEMINI_API_KEY"
    fi

    # 3. 检查依赖技能
    echo ""
    echo "=== 检查依赖技能 ==="
    SKILLS_DIR="$HOME/.openclaw/skills"
    check_path "$SKILLS_DIR/nano-banana-pro" "dir" "安装 nano-banana-pro 技能"

    # 4. 检查本技能文件
    echo ""
    echo "=== 检查技能文件 ==="
    SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

    # 检查垂类配置
    for vertical in finance beauty tech; do
        check_path "$SKILL_DIR/verticals/$vertical.json" "file" ""
    done

    # 检查人设文件
    for persona in finance.md beauty.md tech.md; do
        check_path "$SKILL_DIR/personas/$persona" "file" ""
    done

    # 检查核心脚本
    check_path "$SKILL_DIR/scripts/config_parser.py" "file" ""
    check_path "$SKILL_DIR/scripts/persona_applier.py" "file" ""
    check_path "$SKILL_DIR/scripts/generate_content_strict.py" "file" ""
    check_path "$SKILL_DIR/scripts/generate_content_advanced.py" "file" ""
    check_path "$SKILL_DIR/scripts/bootstrap_vertical.py" "file" ""

    # 5. 检查配置有效性
    echo ""
    echo "=== 检查配置有效性 ==="

    for vertical in finance beauty tech; do
        if python3 "$SKILL_DIR/scripts/config_parser.py" "$vertical" validate >/dev/null 2>&1; then
            print_check "$vertical.json" "OK"
        else
            print_check "$vertical.json" "FAIL" "配置格式有误"
        fi
    done

    # 6. 总结
    echo ""
    echo "========================================"
    if [[ $CHECKS_FAILED -eq 0 ]]; then
        echo -e "${GREEN}所有检查通过！${NC}"
    else
        echo -e "${RED}发现 $CHECKS_FAILED 个问题${NC}"
    fi
    if [[ $CHECKS_WARNING -gt 0 ]]; then
        echo -e "${YELLOW}有 $CHECKS_WARNING 个警告${NC}"
    fi
    echo "========================================"

    # 返回状态码
    if [[ $CHECKS_FAILED -gt 0 ]]; then
        exit 1
    else
        exit 0
    fi
}

# 运行主函数
main "$@"
