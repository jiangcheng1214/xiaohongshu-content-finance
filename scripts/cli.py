#!/usr/bin/env python3
"""
小红书智能内容生成 - 统一 CLI 入口

参考 xiaohongshu-skills 的架构设计，提供结构化的子命令和 JSON 输出。

Usage:
    python scripts/cli.py generate finance "PLTR还能追吗"
    python scripts/cli.py content finance "PLTR" --max-retries 3
    python scripts/cli.py cover finance "PLTR"
    python scripts/cli.py info <session_dir>
    python scripts/cli.py list

Exit Codes:
    0 = 成功
    1 = 部分失败（如内容生成成功但封面失败）
    2 = 完全失败
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

# 添加 lib 目录到路径
SCRIPT_DIR = Path(__file__).parent.absolute()
LIB_DIR = SCRIPT_DIR / "lib"
SKILL_DIR = SCRIPT_DIR.parent  # skill 根目录
sys.path.insert(0, str(LIB_DIR))

# Windows 控制台默认编码（如 cp1252）不支持中文，强制 UTF-8
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("xhs-gen-cli")

# 常量
DEFAULT_WORKSPACE = Path.home() / ".openclaw" / "agents" / "main" / "agent"

# 支持的垂类列表
SUPPORTED_VERTICALS = [
    "finance",  # 金融投资
    "stock",    # 股票
    "tech",     # 数码科技
    "beauty",   # 美妆护肤
    "wallpaper",  # 壁纸
]


# ─── 输出工具 ────────────────────────────────────────────────────────────────

def _output(data: dict[str, Any], exit_code: int = 0) -> None:
    """输出 JSON 结果并退出"""
    print(json.dumps(data, ensure_ascii=False, indent=2))
    sys.exit(exit_code)


def _error(message: str, exit_code: int = 2, **extra: Any) -> None:
    """输出错误信息并退出"""
    result = {"success": False, "error": message, **extra}
    _output(result, exit_code)


# ─── Pipeline 初始化 ─────────────────────────────────────────────────────────

def _get_pipeline():
    """获取 Pipeline 实例"""
    from pipeline import Pipeline

    workspace = Path(os.environ.get("XHS_WORKSPACE", DEFAULT_WORKSPACE))
    workspace.mkdir(parents=True, exist_ok=True)

    return Pipeline(skill_dir=SKILL_DIR, workspace=workspace)


def _get_session(pipeline: Pipeline, vertical: str, topic: str,
                 create_if_missing: bool = True):
    """获取或创建 Session"""
    from session import XhsSession

    if create_if_missing:
        return pipeline.get_or_create_session(vertical, topic)

    existing = XhsSession.find_existing(topic, pipeline.workspace)
    if existing:
        session = XhsSession(workspace=pipeline.workspace)
        session.load(existing)
        return session
    return None


# ─── 子命令实现 ─────────────────────────────────────────────────────────────

def cmd_generate(args: argparse.Namespace) -> None:
    """
    完整生成流程：内容 + 封面 + 发送

    这是主要的内容生成命令，执行完整的 7 步流水线。
    """
    if args.vertical not in SUPPORTED_VERTICALS:
        _error(
            f"不支持的垂类: {args.vertical}",
            exit_code=2,
            supported_verticals=SUPPORTED_VERTICALS
        )

    pipeline = _get_pipeline()
    session = _get_session(pipeline, args.vertical, args.topic)

    max_retries = getattr(args, 'max_retries', 2)

    success = pipeline.run_all(session, max_retries=max_retries)

    # 收集输出数据
    result = {
        "success": success,
        "session_id": session.session_id,
        "session_dir": str(session.session_dir),
        "vertical": session.vertical,
        "topic": session.topic,
        "status": session.status,
    }

    # 添加生成的内容信息
    gen_data = session.get_step_data('generate')
    if gen_data:
        result["content"] = {
            "title": gen_data.get('title', ''),
            "subtitle": gen_data.get('subtitle', ''),
            "content_length": gen_data.get('content_length', 0),
        }

    # 添加封面信息
    if session.file_exists('cover.png'):
        result["cover"] = str(session.get_file_path('cover.png'))

    # 添加内容文件路径
    if session.file_exists('content.md'):
        result["content_file"] = str(session.get_file_path('content.md'))

    exit_code = 0 if success else 1
    _output(result, exit_code)


def cmd_content(args: argparse.Namespace) -> None:
    """
    仅生成内容（步骤 1-3）

    执行研究、生成、验证三个步骤，不生成封面。
    """
    if args.vertical not in SUPPORTED_VERTICALS:
        _error(
            f"不支持的垂类: {args.vertical}",
            exit_code=2,
            supported_verticals=SUPPORTED_VERTICALS
        )

    pipeline = _get_pipeline()
    session = _get_session(pipeline, args.vertical, args.topic)

    max_retries = getattr(args, 'max_retries', 2)
    success = pipeline.run_content_pipeline(session, max_retries=max_retries)

    gen_data = session.get_step_data('generate')
    result = {
        "success": success,
        "session_id": session.session_id,
        "session_dir": str(session.session_dir),
        "content": {
            "title": gen_data.get('title', '') if gen_data else '',
            "subtitle": gen_data.get('subtitle', '') if gen_data else '',
            "content_length": gen_data.get('content_length', 0) if gen_data else 0,
        } if gen_data else {},
    }

    if session.file_exists('content.md'):
        result["content_file"] = str(session.get_file_path('content.md'))

    exit_code = 0 if success else 2
    _output(result, exit_code)


def cmd_cover(args: argparse.Namespace) -> None:
    """
    仅生成封面（步骤 4-6）

    基于已生成的内容，执行封面变量收集、图片生成、Logo 叠加。
    需要先执行 content 命令生成内容。
    """
    if args.vertical not in SUPPORTED_VERTICALS:
        _error(
            f"不支持的垂类: {args.vertical}",
            exit_code=2,
            supported_verticals=SUPPORTED_VERTICALS
        )

    pipeline = _get_pipeline()
    session = _get_session(pipeline, args.vertical, args.topic, create_if_missing=False)

    if not session:
        _error(f"未找到 session，请先运行 content 命令生成内容")

    success = pipeline.run_cover_pipeline(session)

    result = {
        "success": success,
        "session_id": session.session_id,
        "session_dir": str(session.session_dir),
    }

    if success and session.file_exists('cover.png'):
        result["cover_file"] = str(session.get_file_path('cover.png'))

    exit_code = 0 if success else 2
    _output(result, exit_code)


def cmd_info(args: argparse.Namespace) -> None:
    """
    显示 Session 信息

    查看指定 session 的详细状态、生成的内容、文件等信息。
    """
    from session import XhsSession

    session_dir = Path(args.session_dir)
    if not session_dir.exists():
        _error(f"Session 目录不存在: {session_dir}")

    session = XhsSession(workspace=session_dir.parent)
    session.load(session_dir)

    result = {
        "success": True,
        "session": {
            "id": session.session_id,
            "vertical": session.vertical,
            "topic": session.topic,
            "status": session.status,
            "session_dir": str(session.session_dir),
            "created_at": session._data.get('created_at'),
            "updated_at": session._data.get('updated_at'),
        },
        "steps": session._data.get('steps', {}),
    }

    # 添加生成的内容信息
    gen_data = session.get_step_data('generate')
    if gen_data:
        result["content"] = {
            "title": gen_data.get('title', ''),
            "subtitle": gen_data.get('subtitle', ''),
            "content_length": gen_data.get('content_length', 0),
        }

    # 添加文件信息
    files = {}
    if session.file_exists('content.md'):
        files["content"] = str(session.get_file_path('content.md'))
    if session.file_exists('cover.png'):
        files["cover"] = str(session.get_file_path('cover.png'))
    if files:
        result["files"] = files

    _output(result, 0)


def cmd_init(args: argparse.Namespace) -> None:
    """
    初始化新的 Session

    创建一个新的内容生成 session，不执行任何生成步骤。
    """
    if args.vertical not in SUPPORTED_VERTICALS:
        _error(
            f"不支持的垂类: {args.vertical}",
            exit_code=2,
            supported_verticals=SUPPORTED_VERTICALS
        )

    pipeline = _get_pipeline()
    session = pipeline.create_session(args.vertical, args.topic)

    result = {
        "success": True,
        "session_id": session.session_id,
        "session_dir": str(session.session_dir),
        "vertical": session.vertical,
        "topic": session.topic,
    }
    _output(result, 0)


def cmd_list(args: argparse.Namespace) -> None:
    """
    列出所有 Sessions

    显示工作区中所有的内容生成 sessions。
    """
    workspace = Path(os.environ.get("XHS_WORKSPACE", DEFAULT_WORKSPACE))

    if not workspace.exists():
        _output({"success": True, "sessions": []}, 0)

    sessions = []
    for session_dir in sorted(workspace.glob("xhs_session_*"), key=lambda p: p.stat().st_mtime, reverse=True):
        session_file = session_dir / "session.json"
        if session_file.exists():
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                sessions.append({
                    "id": data.get('id', session_dir.name),
                    "vertical": data.get('vertical', ''),
                    "topic": data.get('topic', ''),
                    "status": data.get('status', 'unknown'),
                    "session_dir": str(session_dir),
                    "created_at": data.get('created_at'),
                    "updated_at": data.get('updated_at'),
                })
            except Exception as e:
                logger.debug(f"无法读取 session {session_dir}: {e}")

    result = {
        "success": True,
        "count": len(sessions),
        "sessions": sessions,
    }
    _output(result, 0)


def cmd_send(args: argparse.Namespace) -> None:
    """
    发送到 Telegram

    将已生成的内容发送到 Telegram。
    如果有封面图，一起发送。
    """
    from session import XhsSession

    session_dir = Path(args.session_dir)
    if not session_dir.exists():
        _error(f"Session 目录不存在: {session_dir}")

    pipeline = _get_pipeline()
    session = XhsSession(workspace=pipeline.workspace)
    session.load(session_dir)

    success = pipeline.run_delivery(session)

    result = {
        "success": success,
        "session_id": session.session_id,
        "message": "发送成功" if success else "发送失败",
    }
    exit_code = 0 if success else 1
    _output(result, exit_code)


def cmd_verticals(args: argparse.Namespace) -> None:
    """
    列出支持的垂类

    显示所有可用的垂类及其说明。
    """
    VERTICAL_INFO = {
        "finance": {
            "name": "金融投资",
            "description": "量化交易员人设，数据驱动，风险提示",
            "persona": "finance",
        },
        "stock": {
            "name": "股票",
            "description": "股票分析，实时行情，数据驱动",
            "persona": "finance",
        },
        "tech": {
            "name": "数码科技",
            "description": "专业测评人，参数分析，购买建议",
            "persona": "tech",
        },
        "beauty": {
            "name": "美妆护肤",
            "description": "资深博主，真实测评，避坑指南",
            "persona": "beauty",
        },
        "wallpaper": {
            "name": "壁纸",
            "description": "高清壁纸分享",
            "persona": "wallpaper",
        },
    }

    verticals = []
    for code in SUPPORTED_VERTICALS:
        info = VERTICAL_INFO.get(code, {})
        verticals.append({
            "code": code,
            "name": info.get("name", code),
            "description": info.get("description", ""),
            "persona": info.get("persona", ""),
        })

    result = {
        "success": True,
        "verticals": verticals,
    }
    _output(result, 0)


# ─── 参数解析 ─────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    """构建 CLI 参数解析器"""
    parser = argparse.ArgumentParser(
        prog="xhs-gen",
        description="小红书智能内容生成 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 完整生成流程
  %(prog)s generate finance "PLTR还能追吗"

  # 分步执行
  %(prog)s content finance "PLTR" --max-retries 3
  %(prog)s cover finance "PLTR"
  %(prog)s send <session_dir>

  # 查看信息
  %(prog)s info <session_dir>
  %(prog)s list
  %(prog)s verticals

环境变量:
  XHS_WORKSPACE    工作目录 (默认: ~/.openclaw/agents/main/agent)
  XHS_TEST_MODE    测试模式，使用 mock 数据 (true/false)
        """
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # generate - 完整生成流程
    sub = subparsers.add_parser("generate", help="完整生成流程（内容+封面+发送）")
    sub.add_argument("vertical", help=f"垂类 ({', '.join(SUPPORTED_VERTICALS)})")
    sub.add_argument("topic", help="话题/主题")
    sub.add_argument("--max-retries", type=int, default=2,
                     help="内容生成最大重试次数 (默认: 2)")
    sub.set_defaults(func=cmd_generate)

    # content - 仅生成内容
    sub = subparsers.add_parser("content", help="仅生成内容（步骤 1-3）")
    sub.add_argument("vertical", help=f"垂类 ({', '.join(SUPPORTED_VERTICALS)})")
    sub.add_argument("topic", help="话题/主题")
    sub.add_argument("--max-retries", type=int, default=2,
                     help="内容生成最大重试次数 (默认: 2)")
    sub.set_defaults(func=cmd_content)

    # cover - 仅生成封面
    sub = subparsers.add_parser("cover", help="仅生成封面（步骤 4-6）")
    sub.add_argument("vertical", help=f"垂类 ({', '.join(SUPPORTED_VERTICALS)})")
    sub.add_argument("topic", help="话题/主题")
    sub.set_defaults(func=cmd_cover)

    # info - 显示 session 信息
    sub = subparsers.add_parser("info", help="显示 Session 信息")
    sub.add_argument("session_dir", help="Session 目录路径")
    sub.set_defaults(func=cmd_info)

    # init - 初始化 session
    sub = subparsers.add_parser("init", help="初始化新的 Session")
    sub.add_argument("vertical", help=f"垂类 ({', '.join(SUPPORTED_VERTICALS)})")
    sub.add_argument("topic", help="话题/主题")
    sub.set_defaults(func=cmd_init)

    # list - 列出所有 sessions
    sub = subparsers.add_parser("list", help="列出所有 Sessions")
    sub.set_defaults(func=cmd_list)

    # send - 发送到 Telegram
    sub = subparsers.add_parser("send", help="发送到 Telegram")
    sub.add_argument("session_dir", help="Session 目录路径")
    sub.set_defaults(func=cmd_send)

    # verticals - 列出支持的垂类
    sub = subparsers.add_parser("verticals", help="列出支持的垂类")
    sub.set_defaults(func=cmd_verticals)

    return parser


def main() -> None:
    """主入口函数"""
    parser = build_parser()
    args = parser.parse_args()

    try:
        args.func(args)
    except KeyboardInterrupt:
        _output({"success": False, "error": "用户中断"}, 130)
    except Exception as e:
        logger.error("执行失败: %s", e, exc_info=True)
        _error(str(e), exit_code=2)


if __name__ == "__main__":
    main()
