#!/bin/bash
# 显示session信息
# 用法: ./session_info.sh <session_dir>

SESSION_DIR="${1:-}"

if [[ -z "$SESSION_DIR" || ! -d "$SESSION_DIR" ]]; then
    echo "用法: $0 <session_dir>" >&2
    exit 1
fi

SESSION_JSON="$SESSION_DIR/session.json"

if [[ ! -f "$SESSION_JSON" ]]; then
    echo "# ✗ session.json 不存在" >&2
    exit 1
fi

echo "========================================"
echo "📁 Session 信息"
echo "========================================"
echo ""

python3 << EOF
import json
import os

with open('$SESSION_JSON') as f:
    s = json.load(f)

print(f"📌 话题: {s.get('topic', 'N/A')}")
print(f"📂 垂类: {s.get('vertical', 'N/A')}")
print(f"🕐 创建时间: {s.get('created_at', 'N/A')}")
print(f"📊 状态: {s.get('status', 'N/A')}")
print("")

# 步骤状态
steps = s.get('steps', {})
print("📝 步骤:")
for step, done in steps.items():
    status = "✅" if done else "⬜"
    print(f"  {status} {step}")
print("")

# 文件统计
print("📄 文件:")
if os.path.exists(f'{s.get("topic", "")}'):
    pass

session_dir = '$SESSION_DIR'
if os.path.exists(f'{session_dir}/content.md'):
    size = os.path.getsize(f'{session_dir}/content.md')
    print(f"  📝 content.md ({size} bytes)")
if os.path.exists(f'{session_dir}/cover.png'):
    size = os.path.getsize(f'{session_dir}/cover.png')
    print(f"  🎨 cover.png ({size} bytes)")
if os.path.exists(f'{session_dir}/images'):
    images = [f for f in os.listdir(f'{session_dir}/images') if f.endswith(('.jpg', '.png', '.jpeg'))]
    print(f"  📸 images/ ({len(images)} 张图片)")
EOF

echo ""
echo "📂 目录: $SESSION_DIR"
echo "========================================"
