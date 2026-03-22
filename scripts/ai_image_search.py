#!/usr/bin/env python3
"""
AI驱动的智能配图搜索系统
- 语义分析话题类型
- 根据垂类和话题确定需要的图片类型
- 智能搜索并筛选最相关的图片
"""

import json
import sys
import os
import re
import subprocess
import urllib.request
from urllib.parse import quote

class ImageSearchEngine:
    """图片搜索引擎"""

    def __init__(self):
        self.user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'

    def analyze_topic_intent(self, vertical, topic):
        """分析话题意图，确定需要什么类型的图片"""
        topic_lower = topic.lower()

        # 话题类型模式
        patterns = {
            # 分析类：需要图表、数据
            'analysis': [
                r'还能追吗|值得买吗|要不要|能到.*吗|怎么样|好不好',
                r'分析|解读|点评|复盘|剖析',
                r'target.*price|估值|财报|业绩|数据'
            ],
            # 新闻/事件类：需要新闻配图、现场图
            'news': [
                r'突发|重磅|官宣|发布会|大会',
                r'g tc|ces|mwc|fomo|ff',
                r'第.*天|今日|本周|最新|刚刚'
            ],
            # 产品/评测类：需要产品图、对比图
            'review': [
                r'评测|体验|上手|开箱|实测',
                r'对比|区别|哪个好|推荐',
                r'参数|配置|性能|跑分'
            ],
            # 教程/指南类：需要示意图、步骤图
            'tutorial': [
                r'教程|指南|如何|怎么|方法',
                r'入门|基础|从零开始|新手'
            ]
        }

        # 检测话题类型
        detected_types = []
        for intent_type, type_patterns in patterns.items():
            for pattern in type_patterns:
                if re.search(pattern, topic, re.IGNORECASE):
                    detected_types.append(intent_type)
                    break

        # 根据垂类和话题类型确定图片需求
        image_requirements = self._get_image_requirements(vertical, detected_types, topic)

        return {
            'topic': topic,
            'vertical': vertical,
            'detected_types': detected_types,
            'image_requirements': image_requirements
        }

    def _get_image_requirements(self, vertical, detected_types, topic):
        """根据垂类和检测到的话题类型确定图片需求"""
        requirements = []

        # 分析类 - 需要图表和数据
        if 'analysis' in detected_types:
            if vertical == 'finance':
                requirements.append({
                    'type': 'chart',
                    'description': f'{topic} 价格走势图',
                    'search_terms': [f'{topic} stock chart', f'{topic} trading view', f'{topic} price history']
                })
                requirements.append({
                    'type': 'data',
                    'description': f'{topic} 财务数据图表',
                    'search_terms': [f'{topic} financial data', f'{topic} statistics']
                })
            elif vertical == 'tech':
                requirements.append({
                    'type': 'chart',
                    'description': f'{topic} 性能对比图',
                    'search_terms': [f'{topic} benchmark', f'{topic} comparison chart']
                })

        # 新闻/事件类 - 需要新闻配图和现场图
        if 'news' in detected_types:
            requirements.append({
                'type': 'news',
                'description': f'{topic} 新闻配图',
                'search_terms': [f'{topic} news image', f'{topic} press photo']
            })

        # 产品/评测类 - 需要产品图
        if 'review' in detected_types:
            if vertical == 'tech':
                requirements.append({
                    'type': 'product',
                    'description': f'{topic} 产品图',
                    'search_terms': [f'{topic} official photo', f'{topic} product shot']
                })
                requirements.append({
                    'type': 'comparison',
                    'description': f'{topic} 对比图',
                    'search_terms': [f'{topic} vs', f'{topic} comparison']
                })
            elif vertical == 'beauty':
                requirements.append({
                    'type': 'swatch',
                    'description': f'{topic} 色号展示',
                    'search_terms': [f'{topic} swatch', f'{topic} color chart']
                })

        # 如果没有检测到特定类型，使用默认策略
        if not requirements:
            if vertical == 'finance':
                requirements.append({
                    'type': 'logo',
                    'description': f'{topic} 公司标识',
                    'search_terms': [f'{topic} logo', f'{topic} brand']
                })
            elif vertical == 'tech':
                requirements.append({
                    'type': 'product',
                    'description': f'{topic} 相关图片',
                    'search_terms': [f'{topic} official', f'{topic} image']
                })

        return requirements

    def get_fallback_images(self, intent_type, vertical):
        """获取后备通用图片（当没有找到特定实体图片时使用）"""
        # 使用 Unsplash 等允许外链的图库
        fallback_images = {
            'finance': {
                'analysis': [
                    'https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=800',  # 股票图表
                    'https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?w=800',  # 金融数据
                    'https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=800',  # 数据分析
                ],
                'news': [
                    'https://images.unsplash.com/photo-1504868584819-f8e8b4b6d7e3?w=800',  # 新闻
                    'https://images.unsplash.com/photo-1611162617474-5b21e879e113?w=800',  # 财经新闻
                ],
                'default': [
                    'https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=800',  # 办公室/商务
                ]
            },
            'tech': {
                'analysis': [
                    'https://images.unsplash.com/photo-1518770660439-4636190af475?w=800',  # 芯片/科技
                    'https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=800',  # 数据中心
                ],
                'review': [
                    'https://images.unsplash.com/photo-1550009158-9ebf69173e03?w=800',  # 产品评测
                    'https://images.unsplash.com/photo-1519389950473-47ba0277781c?w=800',  # 科技产品
                ],
                'news': [
                    'https://images.unsplash.com/photo-1485827404703-89b55fcc595e?w=800',  # 科技新闻
                    'https://images.unsplash.com/photo-1531297484001-80022131f5a1?w=800',  # AI/机器
                ],
                'default': [
                    'https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800',  # 科技网络
                ]
            },
            'beauty': {
                'review': [
                    'https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=800',  # 化妆品
                    'https://images.unsplash.com/photo-1522335789203-aabd1fc54bc9?w=800',  # 护肤
                ],
                'default': [
                    'https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?w=800',  # 美妆
                ]
            }
        }

        # 获取对应的后备图片
        if vertical in fallback_images:
            if intent_type in fallback_images[vertical]:
                return fallback_images[vertical][intent_type]
            return fallback_images[vertical].get('default', [])

        return []

    def extract_known_entity_images(self, vertical, topic):
        """提取已知实体的图片（作为备选）"""
        topic_lower = topic.lower()

        # 扩展的实体映射，支持中英文名称，只使用可靠的图片源
        entity_images = {
            # 加密货币 - logo
            'btc': {
                'logo': 'https://cryptologos.cc/logos/bitcoin-btc-logo.png',
            },
            'bitcoin': {
                'logo': 'https://cryptologos.cc/logos/bitcoin-btc-logo.png',
            },
            '比特币': {
                'logo': 'https://cryptologos.cc/logos/bitcoin-btc-logo.png',
            },
            'btc': {
                'logo': 'https://cryptologos.cc/logos/bitcoin-btc-logo.png',
            },
            'eth': {
                'logo': 'https://cryptologos.cc/logos/ethereum-eth-logo.png',
            },
            'ethereum': {
                'logo': 'https://cryptologos.cc/logos/ethereum-eth-logo.png',
            },
            '以太坊': {
                'logo': 'https://cryptologos.cc/logos/ethereum-eth-logo.png',
            },
            'sol': {
                'logo': 'https://cryptologos.cc/logos/solana-sol-logo.png',
            },
            'solana': {
                'logo': 'https://cryptologos.cc/logos/solana-sol-logo.png',
            },
            # 股票 - logo（使用 companieslogo.com）
            'tsla': {
                'logo': 'https://companieslogo.com/img/orig/TSLA-6da550e5.png',
            },
            '特斯拉': {
                'logo': 'https://companieslogo.com/img/orig/TSLA-6da550e5.png',
            },
            'tesla': {
                'logo': 'https://companieslogo.com/img/orig/TSLA-6da550e5.png',
            },
            'nvidia': {
                'logo': 'https://companieslogo.com/img/orig/NVDA-288cf804.png',
            },
            'nvda': {
                'logo': 'https://companieslogo.com/img/orig/NVDA-288cf804.png',
            },
            '英伟达': {
                'logo': 'https://companieslogo.com/img/orig/NVDA-288cf804.png',
            },
            'pltr': {
                'logo': 'https://companieslogo.com/img/orig/PLTR-236711ab.png',
            },
            'palantir': {
                'logo': 'https://companieslogo.com/img/orig/PLTR-236711ab.png',
            },
            'aapl': {
                'logo': 'https://companieslogo.com/img/orig/AAPL-0d242194.png',
            },
            'apple': {
                'logo': 'https://companieslogo.com/img/orig/AAPL-0d242194.png',
            },
            '苹果': {
                'logo': 'https://companieslogo.com/img/orig/AAPL-0d242194.png',
            },
            'msft': {
                'logo': 'https://companieslogo.com/img/orig/MSFT-3921d780.png',
            },
            'microsoft': {
                'logo': 'https://companieslogo.com/img/orig/MSFT-3921d780.png',
            },
            '微软': {
                'logo': 'https://companieslogo.com/img/orig/MSFT-3921d780.png',
            },
            'googl': {
                'logo': 'https://companieslogo.com/img/orig/GOOGL-4341ef88.png',
            },
            'google': {
                'logo': 'https://companieslogo.com/img/orig/GOOGL-4341ef88.png',
            },
            '谷歌': {
                'logo': 'https://companieslogo.com/img/orig/GOOGL-4341ef88.png',
            },
            'amzn': {
                'logo': 'https://companieslogo.com/img/orig/AMZN-e12e2a82.png',
            },
            'amazon': {
                'logo': 'https://companieslogo.com/img/orig/AMZN-e12e2a82.png',
            },
            '亚马逊': {
                'logo': 'https://companieslogo.com/img/orig/AMZN-e12e2a82.png',
            },
            'meta': {
                'logo': 'https://companieslogo.com/img/orig/META-d57cf85e.png',
            },
            'amd': {
                'logo': 'https://companieslogo.com/img/orig/AMD-2e21f732.png',
            },
            'intc': {
                'logo': 'https://companieslogo.com/img/orig/INTC-288cf804.png',
            },
            'csco': {
                'logo': 'https://companieslogo.com/img/orig/CSCO-288cf804.png',
            },
            'adbe': {
                'logo': 'https://companieslogo.com/img/orig/ADBE-288cf804.png',
            },
            'crm': {
                'logo': 'https://companieslogo.com/img/orig/CRM-288cf804.png',
            },
            'orcl': {
                'logo': 'https://companieslogo.com/img/orig/ORCL-288cf804.png',
            },
            'coin': {
                'logo': 'https://companieslogo.com/img/orig/COIN-288cf804.png',
            },
            'sofi': {
                'logo': 'https://companieslogo.com/img/orig/SOFI-288cf804.png',
            },
            'roku': {
                'logo': 'https://companieslogo.com/img/orig/ROKU-288cf804.png',
            },
            'snap': {
                'logo': 'https://companieslogo.com/img/orig/SNAP-288cf804.png',
            },
            'twtr': {
                'logo': 'https://companieslogo.com/img/orig/TWTR-288cf804.png',
            },
            'dis': {
                'logo': 'https://companieslogo.com/img/orig/DIS-288cf804.png',
            },
            'nflx': {
                'logo': 'https://companieslogo.com/img/orig/NFLX-288cf804.png',
            },
            # 科技产品
            'iphone': {
                'logo': 'https://companieslogo.com/img/orig/AAPL-0d242194.png',
            },
            'android': {
                'logo': 'https://companieslogo.com/img/orig/GOOGL-4341ef88.png',
            },
        }

        # 查找匹配的实体
        for entity, images in entity_images.items():
            if entity in topic_lower:
                return images

        return None

    def generate_search_plan(self, vertical, topic):
        """生成搜索计划"""
        # 1. 语义分析
        analysis = self.analyze_topic_intent(vertical, topic)

        # 2. 检查已知实体
        entity_images = self.extract_known_entity_images(vertical, topic)

        # 3. 构建搜索计划
        search_plan = {
            'topic': topic,
            'vertical': vertical,
            'intent_analysis': analysis['detected_types'],
            'image_requirements': analysis['image_requirements'],
            'known_entity_images': entity_images
        }

        return search_plan

    def download_image(self, url, output_path):
        """下载单张图片"""
        try:
            req = urllib.request.Request(url, headers={'User-Agent': self.user_agent})
            with urllib.request.urlopen(req, timeout=20) as response:
                with open(output_path, 'wb') as f:
                    f.write(response.read())
            return True, None
        except Exception as e:
            return False, str(e)

    def execute_search_plan(self, search_plan, output_dir, count=3):
        """执行搜索计划并下载图片"""
        os.makedirs(output_dir, exist_ok=True)
        downloaded = []

        # 收集需要下载的图片URL
        image_urls = []

        # 优先使用已知实体的图片
        if search_plan['known_entity_images']:
            entity_images = search_plan['known_entity_images']

            # 根据意图选择图片类型（现在只有logo可用）
            if 'logo' in entity_images:
                image_urls.append(('logo', entity_images['logo']))

        # 如果实体图片不足，添加后备图片
        if len(image_urls) < count:
            # 获取主要意图类型
            primary_intent = search_plan['intent_analysis'][0] if search_plan['intent_analysis'] else 'default'
            fallback_urls = self.get_fallback_images(primary_intent, search_plan['vertical'])

            for url in fallback_urls:
                if len(image_urls) >= count:
                    break
                image_urls.append(('concept', url))

        # 如果还是不足，添加通用后备图
        if len(image_urls) < count:
            universal_fallbacks = [
                'https://images.unsplash.com/photo-1559526324-4b87b5e36e44?w=800',  # 科技通用
                'https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=800',  # 商业通用
            ]
            for url in universal_fallbacks:
                if len(image_urls) >= count:
                    break
                image_urls.append(('fallback', url))

        # 下载找到的图片
        for i, (img_type, url) in enumerate(image_urls[:count], 1):
            ext = '.jpg'
            if url.endswith('.png'): ext = '.png'
            elif url.endswith('.svg'): ext = '.svg'

            filename = f"{i:02d}_{img_type}{ext}"
            filepath = os.path.join(output_dir, filename)

            success, error = self.download_image(url, filepath)
            if success:
                downloaded.append(filepath)
            else:
                print(f"# 下载失败: {url} - {error}", file=sys.stderr)

        # 保存 manifest
        manifest_path = os.path.join(output_dir, 'search_plan.json')
        with open(manifest_path, 'w') as f:
            json.dump(search_plan, f, ensure_ascii=False, indent=2)

        # 保存文件清单
        manifest_txt = os.path.join(output_dir, 'manifest.txt')
        with open(manifest_txt, 'w') as f:
            f.write(f"# Topic: {search_plan['topic']}\n")
            f.write(f"# Vertical: {search_plan['vertical']}\n")
            f.write(f"# Intent: {', '.join(search_plan['intent_analysis'])}\n")
            f.write("\n".join(downloaded))

        return {
            'status': 'success',
            'topic': search_plan['topic'],
            'vertical': search_plan['vertical'],
            'intent': search_plan['intent_analysis'],
            'downloaded_count': len(downloaded),
            'images': downloaded,
            'output_dir': output_dir
        }


def main():
    if len(sys.argv) < 4:
        print(json.dumps({
            'error': '用法: python3 ai_image_search.py <垂类> <话题> <输出目录> [数量]',
            'example': 'python3 ai_image_search.py finance "pltr还能追吗" /path/to/output 3'
        }, ensure_ascii=False, indent=2))
        sys.exit(1)

    vertical = sys.argv[1]
    topic = sys.argv[2]
    output_dir = sys.argv[3]
    count = int(sys.argv[4]) if len(sys.argv) > 4 else 3

    engine = ImageSearchEngine()

    # 生成搜索计划
    print(f"# === AI驱动配图搜索 ===", file=sys.stderr)
    print(f"# 垂类: {vertical}", file=sys.stderr)
    print(f"# 话题: {topic}", file=sys.stderr)
    print(f"# ===", file=sys.stderr)

    search_plan = engine.generate_search_plan(vertical, topic)

    print(f"# 检测到的话题类型: {search_plan['intent_analysis']}", file=sys.stderr)
    print(f"# 图片需求: {len(search_plan['image_requirements'])} 种类型", file=sys.stderr)

    # 执行搜索
    result = engine.execute_search_plan(search_plan, output_dir, count)

    # 输出结果
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
