"""
Session 模型和管理器
"""

import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..config import Config
from ..lib.paths import PathManager


@dataclass
class Session:
    """Session 数据模型"""

    id: str
    vertical: str
    topic: str
    safe_topic: str
    created_at: str
    status: str = "initialized"
    steps: dict | None = None
    title: str | None = None
    subtitle: str | None = None
    content: str | None = None
    cover_path: str | None = None
    images_dir: str | None = None
    debug: dict | None = None

    def __post_init__(self):
        if self.steps is None:
            self.steps = {"init": True, "content": False, "cover": False, "sent": False}
        if self.debug is None:
            self.debug = {}

    def to_json(self) -> str:
        """序列化为 JSON"""
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "Session":
        """从 JSON 反序列化"""
        data = json.loads(json_str)
        # 只保留类中定义的字段，过滤掉额外的字段
        # 使用 __annotations__ 获取字段名
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            field_names = set(cls.__annotations__.keys())
        filtered_data = {k: v for k, v in data.items() if k in field_names}
        return cls(**filtered_data)

    @classmethod
    def load(cls, session_dir: Path) -> "Session":
        """从目录加载 Session"""
        session_file = session_dir / "session.json"
        with open(session_file, encoding="utf-8") as f:
            return cls.from_json(f.read())

    def save(self, session_dir: Path):
        """保存 Session 到目录"""
        session_file = session_dir / "session.json"
        with open(session_file, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    def update_step(self, step: str, completed: bool = True):
        """更新步骤状态"""
        if step in self.steps:
            self.steps[step] = completed

    def set_status(self, status: str):
        """设置状态"""
        self.status = status


class SessionManager:
    """Session 管理器"""

    def __init__(self, config: Config | None = None, path_manager: PathManager | None = None):
        self.config = config or Config()
        self.path_manager = path_manager or PathManager(self.config)

    def create_session(self, vertical: str, topic: str) -> Session:
        """创建新 Session"""
        # 生成安全话题名
        safe_topic = self._sanitize_topic(topic)
        timestamp = int(datetime.now().timestamp())
        session_id = f"xhs_session_{timestamp}_{safe_topic}"

        # 创建目录
        session_dir = self.path_manager.get_session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)

        # 创建 Session 对象
        session = Session(
            id=session_id,
            vertical=vertical,
            topic=topic,
            safe_topic=safe_topic,
            created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        )

        # 保存
        session.save(session_dir)
        return session

    def load_session(self, session_id: str) -> Session | None:
        """加载 Session"""
        session_dir = self.path_manager.get_session_dir(session_id)
        if not session_dir.exists():
            return None

        session_file = session_dir / "session.json"
        if not session_file.exists():
            return None

        return Session.load(session_dir)

    def find_session_by_topic(self, topic: str) -> Session | None:
        """根据话题查找现有 Session"""
        safe_topic = self._sanitize_topic(topic)
        workspace = self.config.get_workspace()

        if not workspace.exists():
            return None

        # 查找匹配的 session 目录
        for session_dir in workspace.glob("xhs_session_*"):
            if session_dir.name.endswith(f"_{safe_topic}"):
                try:
                    return Session.load(session_dir)
                except (json.JSONDecodeError, IOError):
                    continue
        return None

    def list_sessions(self, limit: int = 20) -> list[Session]:
        """列出最近的 Session"""
        workspace = self.config.get_workspace()

        if not workspace.exists():
            return []

        sessions = []
        for session_dir in sorted(workspace.glob("xhs_session_*"), reverse=True)[:limit]:
            try:
                session = Session.load(session_dir)
                sessions.append(session)
            except (json.JSONDecodeError, IOError):
                continue

        return sessions

    def get_session_dir(self, session: Session) -> Path:
        """获取 Session 目录"""
        return self.path_manager.get_session_dir(session.id)

    @staticmethod
    def _sanitize_topic(topic: str) -> str:
        """清理话题字符串用于文件名"""
        # 替换空格和斜杠
        safe = topic.replace(" ", "_").replace("/", "_").replace("\\", "_")
        # 移除标点 (保留中文)
        safe = re.sub(r"[^\w\u4e00-\u9fff]", "", safe)
        # 限制长度
        return safe[:20]

    def delete_session(self, session_id: str) -> bool:
        """删除 Session 目录"""
        session_dir = self.path_manager.get_session_dir(session_id)
        if not session_dir.exists():
            return False

        import shutil
        try:
            shutil.rmtree(session_dir)
            return True
        except OSError:
            return False
