"""
Session 管理测试
"""

import json
import tempfile
import shutil
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from scripts.xhs_cli.config import Config
from scripts.xhs_cli.core.session import Session, SessionManager


class TestSession(unittest.TestCase):
    """测试 Session 数据模型"""

    def test_session_creation(self):
        """测试 Session 创建"""
        session = Session(
            id="test_session_123",
            vertical="finance",
            topic="测试话题",
            safe_topic="test_topic",
            created_at="2024-01-01T00:00:00Z"
        )

        self.assertEqual(session.id, "test_session_123")
        self.assertEqual(session.vertical, "finance")
        self.assertEqual(session.topic, "测试话题")
        self.assertEqual(session.status, "initialized")
        self.assertTrue(session.steps["init"])
        self.assertFalse(session.steps["content"])

    def test_session_to_json(self):
        """测试 Session 序列化"""
        session = Session(
            id="test_session",
            vertical="tech",
            topic="AI技术",
            safe_topic="ai_tech",
            created_at="2024-01-01T00:00:00Z"
        )

        json_str = session.to_json()
        data = json.loads(json_str)

        self.assertEqual(data["id"], "test_session")
        self.assertEqual(data["vertical"], "tech")
        self.assertEqual(data["topic"], "AI技术")

    def test_session_from_json(self):
        """测试 Session 反序列化"""
        json_str = '''{
            "id": "test_session",
            "vertical": "beauty",
            "topic": "美妆测评",
            "safe_topic": "beauty_review",
            "created_at": "2024-01-01T00:00:00Z",
            "status": "content_generated"
        }'''

        session = Session.from_json(json_str)

        self.assertEqual(session.id, "test_session")
        self.assertEqual(session.status, "content_generated")

    def test_session_from_json_with_extra_fields(self):
        """测试从包含额外字段的 JSON 反序列化"""
        json_str = '''{
            "id": "test_session",
            "vertical": "finance",
            "topic": "股票分析",
            "safe_topic": "stock_analysis",
            "created_at": "2024-01-01T00:00:00Z",
            "extra_field": "should_be_ignored",
            "config": {"nested": "data"}
        }'''

        session = Session.from_json(json_str)

        # 应该正常创建，额外字段被忽略
        self.assertEqual(session.id, "test_session")
        self.assertFalse(hasattr(session, "extra_field"))

    def test_session_update_step(self):
        """测试更新步骤状态"""
        session = Session(
            id="test",
            vertical="finance",
            topic="测试",
            safe_topic="test",
            created_at="2024-01-01T00:00:00Z"
        )

        session.update_step("content", True)
        self.assertTrue(session.steps["content"])

        session.update_step("cover", True)
        self.assertTrue(session.steps["cover"])

    def test_session_save_and_load(self):
        """测试 Session 保存和加载"""
        temp_dir = tempfile.mkdtemp()
        try:
            session = Session(
                id="test_session",
                vertical="tech",
                topic="Python编程",
                safe_topic="python_coding",
                created_at="2024-01-01T00:00:00Z",
                title="Python入门",
                subtitle="从零开始"
            )

            session.save(Path(temp_dir))

            loaded = Session.load(Path(temp_dir))
            self.assertEqual(loaded.id, session.id)
            self.assertEqual(loaded.title, session.title)
            self.assertEqual(loaded.subtitle, session.subtitle)
        finally:
            shutil.rmtree(temp_dir)


class TestSessionManager(unittest.TestCase):
    """测试 SessionManager"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.workspace = Path(self.temp_dir) / "workspace"
        self.workspace.mkdir()

    def tearDown(self):
        """清理测试环境"""
        shutil.rmtree(self.temp_dir)

    def test_create_session(self):
        """测试创建 Session"""
        with patch('scripts.xhs_cli.config.Config.get_workspace', return_value=self.workspace):
            config = Config()
            manager = SessionManager(config)

            session = manager.create_session("finance", "股票投资")

            self.assertEqual(session.vertical, "finance")
            self.assertEqual(session.topic, "股票投资")
            self.assertEqual(session.status, "initialized")
            self.assertTrue(session.id.startswith("xhs_session_"))

            # 验证目录已创建
            session_dir = self.workspace / session.id
            self.assertTrue(session_dir.exists())
            # 验证 session.json 已创建
            self.assertTrue((session_dir / "session.json").exists())

    def test_create_session_multiple(self):
        """测试创建多个 Session"""
        with patch('scripts.xhs_cli.config.Config.get_workspace', return_value=self.workspace):
            config = Config()
            manager = SessionManager(config)

            session1 = manager.create_session("finance", "话题1")
            session2 = manager.create_session("tech", "话题2")

            self.assertNotEqual(session1.id, session2.id)
            self.assertEqual(session1.vertical, "finance")
            self.assertEqual(session2.vertical, "tech")

    def test_find_session_by_topic(self):
        """测试根据话题查找 Session"""
        with patch('scripts.xhs_cli.config.Config.get_workspace', return_value=self.workspace):
            config = Config()
            manager = SessionManager(config)

            # 创建一个 session
            created = manager.create_session("beauty", "口红测评")

            # 查找
            found = manager.find_session_by_topic("口红测评")

            self.assertIsNotNone(found)
            self.assertEqual(found.id, created.id)
            self.assertEqual(found.vertical, "beauty")

    def test_find_nonexistent_session(self):
        """测试查找不存在的 Session"""
        with patch('scripts.xhs_cli.config.Config.get_workspace', return_value=self.workspace):
            config = Config()
            manager = SessionManager(config)

            found = manager.find_session_by_topic("不存在的话题")
            self.assertIsNone(found)

    def test_load_session(self):
        """测试加载 Session"""
        with patch('scripts.xhs_cli.config.Config.get_workspace', return_value=self.workspace):
            config = Config()
            manager = SessionManager(config)

            # 创建 session
            created = manager.create_session("finance", "测试")

            # 加载
            loaded = manager.load_session(created.id)

            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.id, created.id)
            self.assertEqual(loaded.topic, "测试")

    def test_list_sessions(self):
        """测试列出 Session"""
        with patch('scripts.xhs_cli.config.Config.get_workspace', return_value=self.workspace):
            config = Config()
            manager = SessionManager(config)

            # 创建多个 sessions
            manager.create_session("finance", "话题1")
            manager.create_session("tech", "话题2")
            manager.create_session("beauty", "话题3")

            # 列出
            sessions = manager.list_sessions(limit=10)

            self.assertEqual(len(sessions), 3)

    def test_list_sessions_with_limit(self):
        """测试带限制的列出 Session"""
        with patch('scripts.xhs_cli.config.Config.get_workspace', return_value=self.workspace):
            config = Config()
            manager = SessionManager(config)

            # 创建多个 sessions
            for i in range(5):
                manager.create_session("finance", f"话题{i}")

            # 限制数量
            sessions = manager.list_sessions(limit=3)

            self.assertLessEqual(len(sessions), 3)

    def test_delete_session(self):
        """测试删除 Session"""
        with patch('scripts.xhs_cli.config.Config.get_workspace', return_value=self.workspace):
            config = Config()
            manager = SessionManager(config)

            # 创建 session
            session = manager.create_session("finance", "测试")
            session_dir = self.workspace / session.id
            self.assertTrue(session_dir.exists())

            # 删除
            result = manager.delete_session(session.id)

            self.assertTrue(result)
            self.assertFalse(session_dir.exists())

    def test_sanitize_topic(self):
        """测试话题清理"""
        result = SessionManager._sanitize_topic("测试话题 / 特殊字符")
        # 斜杠被替换为下划线
        self.assertIn("测试话题", result)
        self.assertIn("特殊字符", result)
        self.assertNotIn("/", result)

        # 测试长度限制
        long_topic = "a" * 50
        sanitized = SessionManager._sanitize_topic(long_topic)
        self.assertLessEqual(len(sanitized), 20)


if __name__ == '__main__':
    unittest.main()
