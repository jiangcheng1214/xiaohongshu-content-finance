"""
命令行接口
"""

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import Config
from .core.session import Session, SessionManager
from .core.content import ContentGenerator
from .core.cover import CoverGenerator
from .lib.paths import PathManager


def cmd_init(vertical: str, topic: str, config: Config, session_mgr: SessionManager) -> int:
    """初始化新 Session"""
    session = session_mgr.create_session(vertical, topic)
    session_dir = session_mgr.get_session_dir(session)
    print(session_dir)
    return 0


def cmd_info(topic: str, config: Config, session_mgr: SessionManager) -> int:
    """显示 Session 信息"""
    session = session_mgr.find_session_by_topic(topic)
    if not session:
        print(f"# ✗ 没有找到session: {topic}", file=sys.stderr)
        return 1

    session_dir = session_mgr.get_session_dir(session)
    print(f"Session ID: {session.id}")
    print(f"垂类: {session.vertical}")
    print(f"话题: {session.topic}")
    print(f"状态: {session.status}")
    print(f"步骤: {session.steps}")
    print(f"目录: {session_dir}")

    if session.title:
        print(f"标题: {session.title}")
    if session.subtitle:
        print(f"副标题: {session.subtitle}")
    if session.cover_path:
        print(f"封面: {session.cover_path}")

    return 0


def cmd_content(topic: str, config: Config, session_mgr: SessionManager) -> int:
    """生成内容"""
    session = session_mgr.find_session_by_topic(topic)
    if not session:
        print(f"# ✗ 没有找到session: {topic}", file=sys.stderr)
        return 1

    generator = ContentGenerator(config, PathManager(config))
    try:
        main_title, subtitle, content = generator.generate(session)
        print(f"# ✓ 内容生成完成", file=sys.stderr)
        print(f"# 主标题: {main_title}", file=sys.stderr)
        print(f"# 副标题: {subtitle}", file=sys.stderr)
        return 0
    except Exception as e:
        print(f"# ✗ 内容生成失败: {e}", file=sys.stderr)
        return 1


def cmd_cover(topic: str, config: Config, session_mgr: SessionManager) -> int:
    """生成封面"""
    session = session_mgr.find_session_by_topic(topic)
    if not session:
        print(f"# ✗ 没有找到session: {topic}", file=sys.stderr)
        return 1

    generator = CoverGenerator(config, PathManager(config))
    try:
        cover_path = generator.generate(session)
        print(f"# ✓ 封面生成完成: {cover_path}", file=sys.stderr)
        return 0
    except Exception as e:
        print(f"# ✗ 封面生成失败: {e}", file=sys.stderr)
        return 1


def cmd_all(vertical: str, topic: str, config: Config, session_mgr: SessionManager) -> int:
    """执行全部步骤"""
    print("", file=sys.stderr)
    print("========================================", file=sys.stderr)
    print("📱 小红书内容生成", file=sys.stderr)
    print("========================================", file=sys.stderr)
    print("", file=sys.stderr)

    # 查找或创建 session
    session = session_mgr.find_session_by_topic(topic)
    if not session:
        print(f"# 创建新session...", file=sys.stderr)
        session = session_mgr.create_session(vertical, topic)
        session_dir = session_mgr.get_session_dir(session)
    else:
        session_dir = session_mgr.get_session_dir(session)
        print(f"# 使用现有session: {session_dir}", file=sys.stderr)

    # 步骤1: 内容生成
    print("", file=sys.stderr)
    print("📝 步骤 1/2: 内容生成", file=sys.stderr)
    content_gen = ContentGenerator(config, PathManager(config))
    try:
        main_title, subtitle, content = content_gen.generate(session)
    except Exception as e:
        print(f"# ✗ 内容生成失败: {e}", file=sys.stderr)
        return 1

    # 步骤2: 封面生成
    print("", file=sys.stderr)
    print("🎨 步骤 2/2: 封面生成", file=sys.stderr)
    cover_gen = CoverGenerator(config, PathManager(config))
    try:
        cover_path = cover_gen.generate(session)
    except Exception as e:
        print(f"# ✗ 封面生成失败: {e}", file=sys.stderr)
        return 1

    # 显示结果
    print("", file=sys.stderr)
    print("========================================", file=sys.stderr)
    print("✅ 全部完成！", file=sys.stderr)
    print("========================================", file=sys.stderr)
    print("", file=sys.stderr)

    # 重新加载 session 以获取最新状态
    session = session_mgr.load_session(session.id)
    print(f"Session ID: {session.id}")
    print(f"垂类: {session.vertical}")
    print(f"话题: {session.topic}")
    print(f"主标题: {session.title}")
    print(f"副标题: {session.subtitle}")
    print(f"状态: {session.status}")
    print(f"目录: {session_dir}")
    print(f"内容文件: {session_dir}/content.md")
    print(f"封面文件: {session_dir}/cover.png")

    print("", file=sys.stderr)
    print(f"✅ Session: {session_dir}", file=sys.stderr)
    print(session_dir)

    return 0


def cmd_check_config(config: Config) -> int:
    """检查配置"""
    print(f"# OpenClaw Home: {config.get_openclaw_home()}")
    print(f"# Workspace: {config.get_workspace()}")
    print(f"# Skill Dir: {config.get_skill_dir()}")

    api_key = config.get_gemini_api_key()
    if api_key:
        print(f"# Gemini API Key: {'*' * 20}{api_key[-4:]}")
    else:
        print(f"# Gemini API Key: 未配置")

    bot_token = config.get_telegram_bot_token()
    if bot_token:
        print(f"# Telegram Bot Token: {'*' * 20}{bot_token[-4:]}")
    else:
        print(f"# Telegram Bot Token: 未配置")

    # 检查外部命令
    import shutil
    commands = {
        "claude": "Claude CLI",
        "uv": "uv package manager",
    }
    print("\n# 外部命令:")
    for cmd, name in commands.items():
        if shutil.which(cmd):
            print(f"  ✓ {name} ({cmd})")
        else:
            print(f"  ✗ {name} ({cmd}) 未找到")

    return 0


def cmd_list(args, config: Config, session_mgr: SessionManager) -> int:
    """列出 Session"""
    sessions = session_mgr.list_sessions(args.limit)

    if not sessions:
        print("# 没有找到session")
        return 0

    print(f"# 共 {len(sessions)} 个session:")
    print()
    for s in sessions:
        status_emoji = {
            "initialized": "🔵",
            "content_generated": "🟡",
            "cover_generated": "🟢",
            "sent": "✅"
        }.get(s.status, "⚪")

        title = s.title or s.topic
        print(f"{status_emoji} {title[:40]} ({s.vertical})")
        print(f"   ID: {s.id}")
        print(f"   状态: {s.status}")
        print()

    return 0


def main() -> int:
    """主入口"""
    # 检查是否使用旧接口 (xhs-gen <vertical> <topic> [action])
    if len(sys.argv) >= 3 and not sys.argv[1].startswith("-"):
        # 可能是旧接口模式
        potential_action = sys.argv[3] if len(sys.argv) > 3 else None

        # 验证是否是新命令
        new_commands = ["init", "info", "list", "check-config", "--help", "--version", "-h", "-v"]
        if sys.argv[1] not in new_commands:
            # 使用旧接口
            vertical = sys.argv[1]
            topic = sys.argv[2]
            action = potential_action or "--all"

            config = Config()
            session_mgr = SessionManager(config)

            if action == "--init":
                return cmd_init(vertical, topic, config, session_mgr)
            elif action == "--info":
                return cmd_info(topic, config, session_mgr)
            elif action == "--content":
                return cmd_content(topic, config, session_mgr)
            elif action == "--cover":
                return cmd_cover(topic, config, session_mgr)
            elif action == "--all":
                return cmd_all(vertical, topic, config, session_mgr)
            else:
                print(f"# 暂未实现的action: {action}", file=sys.stderr)
                return 1

    # 新接口模式
    parser = argparse.ArgumentParser(
        prog="xhs-gen",
        description="小红书多垂类内容智能生成工具"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # init 命令
    init_parser = subparsers.add_parser("init", help="初始化新session")
    init_parser.add_argument("vertical", help="垂类 (如: finance, beauty, tech)")
    init_parser.add_argument("topic", help="话题")

    # info 命令
    info_parser = subparsers.add_parser("info", help="显示session信息")
    info_parser.add_argument("topic", help="话题")

    # list 命令
    list_parser = subparsers.add_parser("list", help="列出session")
    list_parser.add_argument("--limit", type=int, default=20, help="显示数量")

    # check-config 命令
    subparsers.add_parser("check-config", help="检查配置")

    args = parser.parse_args()
    config = Config()
    session_mgr = SessionManager(config)

    if args.command == "init":
        return cmd_init(args.vertical, args.topic, config, session_mgr)
    elif args.command == "info":
        return cmd_info(args.topic, config, session_mgr)
    elif args.command == "check-config":
        return cmd_check_config(config)
    elif args.command == "list":
        return cmd_list(args, config, session_mgr)
    else:
        parser.print_help()
        return 0


def main_do() -> int:
    """xhs-do 入口 - 确定性执行命令"""
    parser = argparse.ArgumentParser(
        prog="xhs-do",
        description="小红书内容生成 - 确定性执行"
    )
    parser.add_argument("vertical", help="垂类")
    parser.add_argument("topic", help="话题")
    parser.add_argument("action", nargs="?", default="--all",
                        choices=["--init", "--content", "--cover", "--info", "--all", "--send"],
                        help="执行的动作")

    args = parser.parse_args()
    config = Config()
    session_mgr = SessionManager(config)

    if args.action == "--init":
        return cmd_init(args.vertical, args.topic, config, session_mgr)
    elif args.action == "--info":
        return cmd_info(args.topic, config, session_mgr)
    elif args.action == "--content":
        return cmd_content(args.topic, config, session_mgr)
    elif args.action == "--cover":
        return cmd_cover(args.topic, config, session_mgr)
    elif args.action == "--all":
        return cmd_all(args.vertical, args.topic, config, session_mgr)
    elif args.action == "--send":
        print(f"# 暂未实现的action: --send", file=sys.stderr)
        print(f"# 提示: 使用 'xhs-gen check-config' 检查配置", file=sys.stderr)
        return 1
    else:
        print(f"# 暂未实现的action: {args.action}", file=sys.stderr)
        print(f"# 提示: 使用 'xhs-gen check-config' 检查配置", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
