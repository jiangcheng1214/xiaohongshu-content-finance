"""
内容生成模块测试
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, call

from scripts.xhs_cli.config import Config
from scripts.xhs_cli.core.session import Session
from scripts.xhs_cli.core.content import ContentGenerator


class TestContentGenerator(unittest.TestCase):
    """测试 ContentGenerator 类"""

    def setUp(self):
        """每个测试前设置环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.workspace = Path(self.temp_dir) / "workspace"
        self.workspace.mkdir()

        # 创建必要的目录结构
        self.skill_dir = Path(self.temp_dir) / "skill"
        self.skill_dir.mkdir()
        self.verticals_dir = self.skill_dir / "verticals"
        self.verticals_dir.mkdir()
        self.personas_dir = self.skill_dir / "personas"
        self.personas_dir.mkdir()

        # 创建测试用的垂类配置
        self.test_config = {
            "name": "测试垂类",
            "generation_mode": "strict",
            "cover_config": {
                "aspect_ratio": "3:4"
            }
        }
        config_file = self.verticals_dir / "test_vertical.json"
        config_file.write_text(json.dumps(self.test_config), encoding="utf-8")

    def tearDown(self):
        """每个测试后清理"""
        shutil.rmtree(self.temp_dir)

    def _create_generator(self):
        """创建测试用的 ContentGenerator"""
        with patch('scripts.xhs_cli.config.Config.get_skill_dir', return_value=self.skill_dir):
            with patch('scripts.xhs_cli.config.Config.get_workspace', return_value=self.workspace):
                return ContentGenerator()

    def test_parse_titles_with_markers(self):
        """测试解析带标记的标题"""
        gen = self._create_generator()
        content = """【主标题】测试标题
【副标题】测试副标题
正文内容"""
        main, sub = gen._parse_titles(content)
        self.assertEqual(main, "测试标题")
        self.assertEqual(sub, "测试副标题")

    def test_parse_titles_fallback(self):
        """测试从前几行提取标题"""
        gen = self._create_generator()
        content = """# 测试标题
## 测试副标题
正文内容"""
        main, sub = gen._parse_titles(content)
        self.assertEqual(main, "测试标题")
        self.assertEqual(sub, "测试副标题")

    def test_parse_titles_empty_content(self):
        """测试空内容处理"""
        gen = self._create_generator()
        main, sub = gen._parse_titles("")
        self.assertEqual(main, "")
        self.assertEqual(sub, "")

    def test_parse_titles_only_main(self):
        """测试只有主标题的情况"""
        gen = self._create_generator()
        content = """# 测试标题
正文内容"""
        main, sub = gen._parse_titles(content)
        self.assertEqual(main, "测试标题")
        self.assertEqual(sub, "")

    def test_clean_content_removes_markers(self):
        """测试移除标题标记"""
        gen = self._create_generator()
        content = """【主标题】标题
【副标题】副标题

正文内容"""
        cleaned = gen._clean_content(content)
        self.assertNotIn("【主标题】", cleaned)
        self.assertNotIn("【副标题】", cleaned)
        self.assertIn("正文内容", cleaned)

    def test_clean_content_removes_extra_newlines(self):
        """测试移除多余的空行"""
        gen = self._create_generator()
        content = "第一行\n\n\n\n第二行"
        cleaned = gen._clean_content(content)
        self.assertEqual(cleaned, "第一行\n\n第二行")

    def test_should_use_fallback_empty(self):
        """测试空内容判断"""
        gen = self._create_generator()
        self.assertTrue(gen._should_use_fallback(""))

    def test_should_use_fallback_error_msg(self):
        """测试错误消息判断"""
        gen = self._create_generator()
        self.assertTrue(gen._should_use_fallback("我注意到你提供的话题是空的"))
        self.assertTrue(gen._should_use_fallback("请提供产品名称"))
        self.assertTrue(gen._should_use_fallback("I notice you provided an empty topic"))

    def test_should_use_fallback_valid_content(self):
        """测试有效内容不使用备用"""
        gen = self._create_generator()
        self.assertFalse(gen._should_use_fallback("这是有效的内容"))

    def test_get_fallback_content_tech(self):
        """测试 tech 垂类备用内容"""
        gen = self._create_generator()
        session = Session(
            id="test_123",
            vertical="tech",
            topic="iPhone 15",
            safe_topic="iphone_15",
            created_at="2024-01-01T00:00:00Z"
        )
        content = gen._get_fallback_content(session)
        self.assertIn("iPhone 15", content)
        self.assertIn("这款产品", content)
        self.assertIn("#数码 #科技", content)

    def test_get_fallback_content_finance(self):
        """测试 finance 垂类备用内容"""
        gen = self._create_generator()
        session = Session(
            id="test_123",
            vertical="finance",
            topic="股票分析",
            safe_topic="stock_analysis",
            created_at="2024-01-01T00:00:00Z"
        )
        content = gen._get_fallback_content(session)
        self.assertIn("股票分析", content)
        self.assertIn("#股票 #投资", content)

    def test_get_fallback_content_stock(self):
        """测试 stock 垂类备用内容"""
        gen = self._create_generator()
        session = Session(
            id="test_123",
            vertical="stock",
            topic="腾讯控股",
            safe_topic="tencent",
            created_at="2024-01-01T00:00:00Z"
        )
        content = gen._get_fallback_content(session)
        self.assertIn("腾讯控股", content)
        self.assertIn("值得买吗", content)

    def test_get_fallback_content_unknown(self):
        """测试未知垂类备用内容"""
        gen = self._create_generator()
        session = Session(
            id="test_123",
            vertical="unknown",
            topic="未知话题",
            safe_topic="unknown",
            created_at="2024-01-01T00:00:00Z"
        )
        content = gen._get_fallback_content(session)
        self.assertIn("未知话题", content)
        self.assertIn("#分享 #干货", content)

    def test_load_vertical_config_missing(self):
        """测试配置不存在时抛异常"""
        gen = self._create_generator()
        with self.assertRaises(FileNotFoundError):
            gen._load_vertical_config("nonexistent")

    def test_load_persona_with_file(self):
        """测试加载人设文件"""
        # 创建人设文件
        persona_file = self.personas_dir / "test_vertical.md"
        persona_file.write_text("这是测试人设", encoding="utf-8")

        gen = self._create_generator()
        # 需要正确 patch get_personas_dir
        with patch.object(gen.path_manager, 'get_personas_dir', return_value=self.personas_dir):
            persona = gen._load_persona("test_vertical")
            self.assertEqual(persona, "这是测试人设")

    def test_load_persona_missing(self):
        """测试人设不存在返回空"""
        gen = self._create_generator()
        persona = gen._load_persona("nonexistent")
        self.assertEqual(persona, "")

    @patch('scripts.xhs_cli.core.content.subprocess.run')
    def test_call_claude_success(self, mock_run):
        """测试 Claude 调用成功"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="这是生成的内容"
        )
        gen = self._create_generator()
        result = gen._call_claude("测试 prompt")
        self.assertEqual(result, "这是生成的内容")

    @patch('scripts.xhs_cli.core.content.subprocess.run')
    def test_call_claude_timeout(self, mock_run):
        """测试 Claude 调用超时"""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("claude", 120)
        gen = self._create_generator()
        result = gen._call_claude("测试 prompt")
        self.assertEqual(result, "")

    @patch('scripts.xhs_cli.core.content.subprocess.run')
    def test_call_claude_not_found(self, mock_run):
        """测试 Claude 命令不存在"""
        mock_run.side_effect = FileNotFoundError()
        gen = self._create_generator()
        result = gen._call_claude("测试 prompt")
        self.assertEqual(result, "")

    @patch('scripts.xhs_cli.core.content.subprocess.run')
    def test_generate_with_mock_claude(self, mock_run):
        """测试完整生成流程（mock Claude）"""
        # Mock Claude 返回
        mock_run.return_value = Mock(
            returncode=0,
            stdout="""【主标题】测试标题
【副标题】测试副标题

这是正文内容。"""
        )

        # 创建 session 目录
        session_dir = self.workspace / "test_session_123"
        session_dir.mkdir()

        session = Session(
            id="test_session_123",
            vertical="test_vertical",
            topic="测试话题",
            safe_topic="test_topic",
            created_at="2024-01-01T00:00:00Z"
        )

        gen = self._create_generator()

        # 需要完全 mock path_manager 以使用 temp 目录
        with patch.object(gen, 'path_manager') as mock_pm:
            mock_pm.get_session_dir.return_value = session_dir
            mock_pm.get_verticals_dir.return_value = self.verticals_dir
            mock_pm.get_personas_dir.return_value = self.personas_dir

            main_title, subtitle, content = gen.generate(session)

        self.assertEqual(main_title, "测试标题")
        self.assertEqual(subtitle, "测试副标题")
        self.assertIn("这是正文内容", content)

        # 验证 session 已更新
        self.assertEqual(session.title, "测试标题")
        self.assertEqual(session.subtitle, "测试副标题")
        self.assertEqual(session.status, "content_generated")

        # 验证文件已保存
        content_file = session_dir / "content.md"
        self.assertTrue(content_file.exists())

    @patch('scripts.xhs_cli.core.content.subprocess.run')
    def test_generate_uses_fallback_on_claude_failure(self, mock_run):
        """测试 Claude 失败时使用备用模板"""
        # Mock Claude 返回空
        mock_run.return_value = Mock(returncode=0, stdout="")

        session_dir = self.workspace / "test_session_456"
        session_dir.mkdir()

        session = Session(
            id="test_session_456",
            vertical="test_vertical",  # 使用已配置的垂类
            topic="财经新闻",
            safe_topic="finance_news",
            created_at="2024-01-01T00:00:00Z"
        )

        gen = self._create_generator()

        # 完全 mock path_manager
        with patch.object(gen, 'path_manager') as mock_pm:
            mock_pm.get_session_dir.return_value = session_dir
            mock_pm.get_verticals_dir.return_value = self.verticals_dir
            mock_pm.get_personas_dir.return_value = self.personas_dir

            main_title, subtitle, content = gen.generate(session)

        # 应该使用备用模板
        self.assertIn("财经新闻", main_title)
        # test_vertical 的备用模板格式
        self.assertTrue(main_title)  # 只要有标题即可


if __name__ == '__main__':
    unittest.main()
