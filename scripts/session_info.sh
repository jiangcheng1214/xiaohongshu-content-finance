#!/bin/bash
# 步骤: 显示Session信息
# 用法: ./session_info.sh <session_dir>

set -e

SESSION_DIR="${1:-}"

if [[ -z "$SESSION_DIR" || ! -d "$SESSION_DIR" ]]; then
    echo "用法: $0 <session_dir>" >&2
    exit 1
fi

# 读取 session.json
SESSION_JSON="$SESSION_DIR/session.json"

if [[ ! -f "$SESSION_JSON" ]]; then
    echo "错误: session.json 不存在" >&2
    exit 1
fi

PYTHONIOENCODING=utf-8 python3 << EOF
# -*- coding: utf-8 -*-
import json
import os

with open('$SESSION_JSON') as f:
    session = json.load(f)

print("")
print("=" * 50)
print("📱 小红书内容生成 - Session信息")
print("=" * 50)
print("")
print(f"Session ID: {session.get('id', 'N/A')}")
print(f"垂类: {session.get('vertical', 'N/A')}")
print(f"话题: {session.get('topic', 'N/A')}")
print(f"状态: {session.get('status', 'N/A')}")
print(f"创建时间: {session.get('created_at', 'N/A')}")
print("")
print("步骤状态:")
steps = session.get('steps', {})
for step_name, step_status in steps.items():
    status_icon = "✅" if step_status else "⬜"
    print(f"  {status_icon} {step_name}")
print("")
print("文件:")
print(f"  📄 session.json")
if os.path.exists(f'{session.get("id", "$SESSION_DIR")}/content.md'):
    print(f"  📝 content.md")
if os.path.exists(f'{session.get("id", "$SESSION_DIR")}/cover.png'):
    print(f"  🎨 cover.png")
if os.path.exists(f'{session.get("id", "$SESSION_DIR")}/cover_bg.png'):
    print(f"  🖼️  cover_bg.png")
if os.path.exists(f'{session.get("id", "$SESSION_DIR")}/images'):
    image_count = len([f for f in os.listdir(f'{session.get("id", "$SESSION_DIR")}/images') if f.endswith(('.jpg', '.png', '.jpeg'))])
    print(f"  🖼️  images/ ({image_count} 张)")
print("")
print("=" * 50)
EOF

# 如果有content.md，显示标题
if [[ -f "$SESSION_DIR/content.md" ]]; then
    TITLE=$(grep '^# ' "$SESSION_DIR/content.md" | head -1 | sed 's/^# //')
    echo ""
    echo "标题: $TITLE"
    echo ""
fi

echo "$SESSION_DIR"
