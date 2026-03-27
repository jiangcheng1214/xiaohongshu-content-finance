"""
模块入口 - 支持直接运行
python -m scripts.xhs_cli
"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
