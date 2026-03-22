#!/usr/bin/env python3
"""
严格按用户输入生成小红书内容
- 不做AI自动纠正
- 使用用户提供的精确话题
- 如无法理解，使用通用模板
"""
import sys
import json
import re
from datetime import datetime

def generate_content_strict(topic, vertical):
    """
    严格按照用户输入的话题生成内容
    不做任何AI推断或纠正
    """
    # 加载垂类配置
    try:
        with open(f'/Users/jaycee/.openclaw/skills/xiaohongshu-content-generator/verticals/{vertical}.json') as f:
            config = json.load(f)
    except:
        config = {}

    # 加载人设
    try:
        with open(f'/Users/jaycee/.openclaw/skills/xiaohongshu-content-generator/personas/{vertical}.md') as f:
            persona = f.read()
    except:
        persona = ""

    # 获取配置
    default_subtitle = config.get('cover_config', {}).get('default_subtitle', '分析')

    # 根据垂类生成不同风格的通用模板
    if vertical == 'finance':
        content = f"""# {topic}

先别急，看看数据。

这个问题需要从几个角度分析：

**现状分析**
{topic} 这个话题，最近关注度确实在上升。但投资决策不能只看热度，要看基本面。

**关键数据点**
- 关注度：近期讨论增多
- 风险等级：中等
- 建议仓位：控制在不影响整体组合的比例

**操作建议**
1. 先研究清楚基本面
2. 不要追高
3. 设置止损
4. 分批建仓

**风险提示**
以上分析仅供参考，不构成投资建议。市场有风险，投资需谨慎。

数据时间：{datetime.now().strftime('%Y年%m月%d日')}

#{vertical} #投资 #分析 #风险管理"""

    elif vertical == 'beauty':
        content = f"""# {topic}

直接说结论。

**产品分析**
{topic} 这个话题，最近很火。但种草前要先了解自己的需求。

**适用场景**
- 日常：可以
- 重要场合：看具体产品
- 敏感肌：先做测试

**选购建议**
1. 了解自己的肤质/需求
2. 看成分表
3. 查真实测评
4. 先小样试用

**避坑指南**
- 不要盲目跟风
- 价格不等于质量
- 网红款要理性看待

**总结**
按需购买，理性消费。

#{vertical} #美妆 #测评 #种草 #理性消费"""

    elif vertical == 'tech':
        content = f"""# {topic}

技术角度看。

**产品分析**
{topic} 这个话题，值得聊聊。

**核心要点**
- 看参数：不只是看数字
- 看场景：是否符合你的使用需求
- 看价格：性价比如何

**优缺点**
优点：需要具体分析
缺点：需要具体分析

**购买建议**
1. 明确需求
2. 对比同类产品
3. 看长期评测
4. 考虑升级周期

**总结**
按需购买，不追新。

#{vertical} #科技 #测评 #理性消费"""

    else:
        content = f"""# {topic}

关于{topic}的分享。

**核心观点**
这个问题需要具体分析。

**要点**
1. 了解清楚需求
2. 做足功课
3. 理性判断
4. 不盲目跟风

**总结**
具体问题具体分析。

#{vertical} #分享"""

    return content, default_subtitle


def main():
    if len(sys.argv) < 4:
        print(json.dumps({"error": "用法: generate_content_strict.py <topic> <vertical> <output_file>"}))
        sys.exit(1)

    topic = sys.argv[1]
    vertical = sys.argv[2]
    output_file = sys.argv[3]

    # 生成内容
    content, subtitle = generate_content_strict(topic, vertical)

    # 保存
    with open(output_file, 'w') as f:
        f.write(content)

    # 输出结果
    result = {
        "topic": topic,
        "vertical": vertical,
        "subtitle": subtitle,
        "output_file": output_file,
        "content_length": len(content)
    }

    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
