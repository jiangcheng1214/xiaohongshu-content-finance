import sys
#!/usr/bin/env python3
"""
小红书内容生成 - Pipeline 流水线

Pipeline 负责编排内容生成的各个步骤。
"""

from pathlib import Path
from typing import Any

from session import XhsSession
from steps import (
    BaseStep,
    Step1Research,
    Step2Generate,
    Step3Validate,
    Step4PrepareImg,
    Step5GenImg,
    Step6Overlay,
    Step7Deliver,
)


class Pipeline:
    """小红书内容生成流水线"""

    def __init__(self, skill_dir: Path, workspace: Path):
        self.skill_dir = Path(skill_dir)
        self.workspace = Path(workspace)
        self.steps = [
            Step1Research(skill_dir),
            Step2Generate(skill_dir),
            Step3Validate(skill_dir),
            Step4PrepareImg(skill_dir),
            Step5GenImg(skill_dir),
            Step6Overlay(skill_dir),
            Step7Deliver(skill_dir),
        ]

    def get_or_create_session(self, vertical: str, topic: str) -> XhsSession:
        """获取或创建 session"""
        existing = XhsSession.find_existing(topic, self.workspace)
        if existing:
            session = XhsSession(self.workspace)
            session.load(existing)
            return session

        return self.create_session(vertical, topic)

    def create_session(self, vertical: str, topic: str) -> XhsSession:
        """创建新 session"""
        session = XhsSession(self.workspace)
        session.create(vertical, topic)
        return session

    def run_all(self, session: XhsSession, max_retries: int = 2) -> bool:
        """执行完整流程"""
        try:
            # 步骤 1-3: 内容生成
            if not self.run_content_pipeline(session, max_retries):
                return False

            # 步骤 4-6: 封面生成
            if not self.run_cover_pipeline(session):
                return False

            # 步骤 7: 发送
            if not self.run_delivery(session):
                return False

            session.set_status('completed')
            return True

        except Exception as e:
            session.set_status('failed')
            raise


    def run_all_skip_image(self, session: XhsSession, max_retries: int = 2) -> bool:
        """执行完整流程，跳过AI封面，改用md2img文字卡片可视化"""
        try:
            # 步骤 1-3: 内容生成
            if not self.run_content_pipeline(session, max_retries):
                return False

            # 步骤 4-alt: md2img 文字可视化
            if not self.run_md2img(session):
                # fallback: 即使md2img失败也标记内容就绪
                session.set_status('content_ready')
                return True

            session.set_status('completed')
            return True

        except Exception as e:
            session.set_status('failed')
            raise

    def run_md2img(self, session: XhsSession) -> bool:
        """使用 md2img 将内容渲染为单张高清长图"""
        import subprocess
        from pathlib import Path

        content_file = session.get_file_path('content.md')
        if not content_file or not Path(content_file).exists():
            return False

        md2img = Path.home() / ".openclaw" / "skills" / "md2img" / "scripts" / "md2img_long.py"
        if not md2img.exists():
            return False

        output_png = session.session_dir / "long_image.png"

        try:
            r = subprocess.run(
                [sys.executable, str(md2img), "all",
                 "--input", str(content_file),
                 "--output", str(output_png)],
                capture_output=True, text=True, timeout=60
            )
            return output_png.exists()
        except Exception:
            return False

    def run_content_pipeline(self, session: XhsSession, max_retries: int = 2) -> bool:
        """执行内容生成流程（步骤 1-3）"""
        # 步骤 1: 研究
        if not self.steps[0].run(session):
            return False

        # 步骤 2: 生成（带重试）
        retries = 0
        while retries <= max_retries:
            success, feedback = self.steps[1].run(session)
            if success:
                break
            retries += 1
            if retries > max_retries:
                return False

        # 步骤 3: 验证
        if not self.steps[2].run(session):
            return False

        session.set_status('content_ready')
        return True

    def run_cover_pipeline(self, session: XhsSession) -> bool:
        """执行封面生成流程（步骤 4-6）"""
        # 步骤 4: 准备图片变量
        if not self.steps[3].run(session):
            return False

        # 步骤 5: 生成图片
        if not self.steps[4].run(session):
            return False

        # 步骤 6: 叠加 Logo
        if not self.steps[5].run(session):
            return False

        session.set_status('cover_ready')
        return True

    def run_delivery(self, session: XhsSession) -> bool:
        """执行发送流程（步骤 7）"""
        return self.steps[6].run(session)
