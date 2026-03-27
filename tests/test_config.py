"""
配置管理测试
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, mock_open

from scripts.xhs_cli.config import Config


class TestConfig(unittest.TestCase):
    """测试 Config 类"""

    def setUp(self):
        """每个测试前重置环境"""
        # 清除可能影响测试的环境变量
        for key in ["OPENCLAW_HOME", "XHS_WORKSPACE", "GEMINI_API_KEY"]:
            os.environ.pop(key, None)

    def test_get_openclaw_home_default(self):
        """测试默认 OpenClaw 主目录"""
        config = Config()
        expected = Path.home() / ".openclaw"
        self.assertEqual(config.get_openclaw_home(), expected)

    def test_get_openclaw_home_from_env(self):
        """测试从环境变量获取 OpenClaw 主目录"""
        custom_path = "/custom/openclaw"
        with patch.dict(os.environ, {"OPENCLAW_HOME": custom_path}):
            config = Config()
            self.assertEqual(config.get_openclaw_home(), Path(custom_path))

    def test_get_workspace_default(self):
        """测试默认工作区"""
        config = Config()
        expected = Path.home() / ".openclaw" / "agents" / "main" / "agent"
        self.assertEqual(config.get_workspace(), expected)

    def test_get_workspace_from_env(self):
        """测试从环境变量获取工作区"""
        custom_workspace = "/custom/workspace"
        with patch.dict(os.environ, {"XHS_WORKSPACE": custom_workspace}):
            config = Config()
            self.assertEqual(config.get_workspace(), Path(custom_workspace))

    def test_get_skill_dir(self):
        """测试获取技能目录"""
        config = Config()
        skill_dir = config.get_skill_dir()
        # 验证目录存在
        self.assertTrue(skill_dir.exists())
        # 验证包含 SKILL.md
        self.assertTrue((skill_dir / "SKILL.md").exists())

    def test_get_gemini_api_key_from_env(self):
        """测试从环境变量获取 Gemini API Key"""
        test_key = "test_gemini_key_123"
        with patch.dict(os.environ, {"GEMINI_API_KEY": test_key}):
            config = Config()
            self.assertEqual(config.get_gemini_api_key(), test_key)

    def test_sanitize_filename(self):
        """测试文件名清理"""
        config = Config()
        # 测试非法字符替换
        self.assertEqual(config._sanitize_filename('test/file:name'), 'test_file_name')
        # 测试长度限制
        long_name = "a" * 50
        result = config._sanitize_filename(long_name)
        self.assertLessEqual(len(result), 30)

    def test_get_temp_dir_linux(self):
        """测试 Linux 临时目录"""
        with patch('platform.system', return_value='Linux'):
            config = Config()
            temp_dir = config.get_temp_dir()
            self.assertEqual(temp_dir, Path('/tmp'))

    def test_get_export_dir(self):
        """测试导出目录生成"""
        config = Config()
        title = "测试标题"
        export_dir = config.get_export_dir(title)
        # 验证目录包含时间戳
        self.assertIn("Xiaohongshu_Exports", str(export_dir))


class TestConfigWithMockOpenclawJson(unittest.TestCase):
    """测试使用 mock openclaw.json 的配置"""

    def setUp(self):
        """设置测试"""
        self.temp_dir = tempfile.mkdtemp()
        self.openclaw_dir = Path(self.temp_dir) / ".openclaw"
        self.openclaw_dir.mkdir()

    def tearDown(self):
        """清理测试"""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_get_gemini_api_key_from_openclaw_json(self):
        """测试从 openclaw.json 获取 API Key"""
        # 创建测试配置文件
        config_data = {
            "env": {"GEMINI_API_KEY": "key_from_json"}
        }
        config_file = self.openclaw_dir / "openclaw.json"
        config_file.write_text(json.dumps(config_data))

        # Mock home directory
        with patch('pathlib.Path.home', return_value=self.openclaw_dir.parent):
            config = Config()
            key = config.get_gemini_api_key()
            self.assertEqual(key, "key_from_json")

    def test_get_gemini_api_key_fallback(self):
        """测试 API Key 获取的回退逻辑"""
        # 创建测试配置文件 - env 为空但有 skills 配置
        config_data = {
            "skills": {
                "entries": {
                    "nano-banana-pro": {"apiKey": "key_from_skills"}
                }
            }
        }
        config_file = self.openclaw_dir / "openclaw.json"
        config_file.write_text(json.dumps(config_data))

        with patch('pathlib.Path.home', return_value=self.openclaw_dir.parent):
            config = Config()
            key = config.get_gemini_api_key()
            self.assertEqual(key, "key_from_skills")


if __name__ == '__main__':
    unittest.main()
