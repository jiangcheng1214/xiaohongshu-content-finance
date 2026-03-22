#!/bin/bash
# 小红书内容生成引擎 - 一键安装脚本
# 用法: ./install.sh

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[OK]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查命令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 主安装流程
main() {
    echo -e "${BLUE}"
    echo "========================================"
    echo "  小红书内容生成引擎 - 安装向导"
    echo "  Xiaohongshu Content Generator"
    echo "========================================"
    echo -e "${NC}"

    # 1. 检查并安装 Homebrew
    print_info "检查 Homebrew..."
    if ! command_exists brew; then
        print_warning "Homebrew 未安装，正在安装..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        print_success "Homebrew 安装完成"

        # 提示添加到 PATH
        if [[ -f "/opt/homebrew/bin/brew" ]]; then
            print_info "请将 Homebrew 添加到 PATH："
            echo '  export PATH="/opt/homebrew/bin:$PATH"'
        fi
    else
        print_success "Homebrew 已安装: $(brew --version | head -1)"
    fi

    # 2. 安装 ImageMagick
    print_info "检查 ImageMagick..."
    if ! command_exists magick; then
        print_warning "ImageMagick 未安装，正在安装..."
        brew install imagemagick
        print_success "ImageMagick 安装完成"
    else
        print_success "ImageMagick 已安装"
    fi

    # 3. 检查 Python 3
    print_info "检查 Python 3..."
    if command_exists python3; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        print_success "Python 3 已安装: $PYTHON_VERSION"
    else
        print_error "Python 3 未安装，请先安装 Python 3.10+"
        exit 1
    fi

    # 4. 安装 uv (可选)
    print_info "检查 uv (Python 包管理器)..."
    if ! command_exists uv; then
        print_warning "uv 未安装，正在安装..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        print_success "uv 安装完成"
    else
        print_success "uv 已安装: $(uv --version | head -1)"
    fi

    # 5. 配置 GEMINI_API_KEY
    print_info "检查 GEMINI_API_KEY..."
    OPENCLAW_CONFIG="$HOME/.openclaw/openclaw.json"

    if [[ -f "$OPENCLAW_CONFIG" ]]; then
        if grep -q "GEMINI_API_KEY" "$OPENCLAW_CONFIG"; then
            print_success "GEMINI_API_KEY 已配置"
        else
            print_warning "GEMINI_API_KEY 未配置"
            echo -n "请输入您的 GEMINI_API_KEY: "
            read -r API_KEY
            if [[ -n "$API_KEY" ]]; then
                mkdir -p "$(dirname "$OPENCLAW_CONFIG")"
                echo "{\"GEMINI_API_KEY\": \"$API_KEY\"}" > "$OPENCLAW_CONFIG"
                print_success "GEMINI_API_KEY 已保存"
            else
                print_warning "跳过 GEMINI_API_KEY 配置，稍后可手动配置"
            fi
        fi
    else
        print_warning "OpenClaw 配置文件不存在，创建中..."
        echo -n "请输入您的 GEMINI_API_KEY: "
        read -r API_KEY
        mkdir -p "$(dirname "$OPENCLAW_CONFIG")"
        echo "{\"GEMINI_API_KEY\": \"$API_KEY\"}" > "$OPENCLAW_CONFIG"
        print_success "GEMINI_API_KEY 已保存"
    fi

    # 6. 检查依赖技能
    print_info "检查依赖技能..."
    SKILLS_DIR="$HOME/.openclaw/skills"

    if [[ ! -d "$SKILLS_DIR/nano-banana-pro" ]]; then
        print_warning "nano-banana-pro 技能未安装"
        print_info "请手动安装: git clone https://github.com/yourusername/nano-banana-pro.git $SKILLS_DIR/nano-banana-pro"
    else
        print_success "nano-banana-pro 技能已安装"
    fi

    # 7. 安装 OpenClaw CLI (如果需要)
    print_info "检查 OpenClaw CLI..."
    if ! command_exists xhs-do 2>/dev/null; then
        print_warning "xhs-do 命令未找到"
        print_info "请确保 OpenClaw CLI 已正确安装"
    else
        print_success "OpenClaw CLI 已安装"
    fi

    # 8. 设置脚本权限
    print_info "设置脚本执行权限..."
    SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    find "$SKILL_DIR/scripts" -name "*.sh" -exec chmod +x {} \;
    chmod +x "$SKILL_DIR/scripts"/*.py 2>/dev/null || true
    print_success "脚本权限已设置"

    # 9. 运行检查脚本
    echo ""
    print_info "运行依赖检查..."
    if [[ -f "$SKILL_DIR/scripts/check.sh" ]]; then
        bash "$SKILL_DIR/scripts/check.sh" || true
    fi

    echo ""
    echo -e "${GREEN}========================================"
    echo "  安装完成！"
    echo "========================================${NC}"
    echo ""
    echo "使用方法:"
    echo "  ~/.openclaw/bin/xhs-do finance \"话题\""
    echo ""
    echo "示例:"
    echo "  ~/.openclaw/bin/xhs-do finance \"PLTR还能追吗\""
    echo "  ~/.openclaw/bin/xhs-do beauty \"雅诗兰黛DW值得买吗\""
    echo "  ~/.openclaw/bin/xhs-do tech \"iPhone 16 Pro评测\""
    echo ""
}

# 运行主函数
main "$@"
