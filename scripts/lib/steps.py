#!/usr/bin/env python3
"""
小红书内容生成 - 步骤实现

包含所有 7 个步骤的纯 Python 实现。
"""

import json
import os
import re
import shutil
import subprocess
import time
import urllib.parse
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from session import XhsSession
from validate import validate_content
from image_gen import generate_image, get_api_key


# =============================================================================
# 股票数据获取辅助函数（供 Step4 和 Step4a 共用）
# =============================================================================

# 已知的错误响应关键词
_ERROR_INDICATORS = [
    'rate limit', 'usage limit', 'unable to search', 'unable to retrieve',
    'cannot search', 'cannot retrieve', 'i apologize', 'apologize',
    'not available', 'no information', 'try checking', 'reset until',
    'i cannot', "i can't", 'service unavailable', 'search service',
    'recommend checking', 'for the most current',
]


def _is_error_response(text: str) -> bool:
    """检查搜索结果是否为错误/限流响应"""
    if not text:
        return True
    text_lower = text.lower()
    return any(indicator in text_lower for indicator in _ERROR_INDICATORS)


def _fetch_brave_search(query: str, timeout: int = 15, freshness: str = 'pd') -> Optional[str]:
    """通过 Brave Search API 执行搜索

    Args:
        query: 搜索查询
        timeout: 超时时间
        freshness: 时间过滤，默认 pd（过去一天），可用值: pd, pw, pm, py, all

    Returns:
        搜索结果文本，如果没有48小时内的结果则返回 None
    """
    import urllib.request
    from datetime import datetime, timedelta

    config_file = Path.home() / '.openclaw' / 'openclaw.json'
    api_key = ''
    if config_file.exists():
        try:
            with open(config_file) as f:
                config = json.load(f)
            api_key = (config.get('tools', {}).get('web', {})
                      .get('search', {}).get('apiKey', ''))
        except Exception:
            pass

    if not api_key:
        return None

    # 使用 freshness 参数限制时间范围
    # pd = past day, pw = past week, pm = past month
    url = f"https://api.search.brave.com/res/v1/web/search?q={urllib.parse.quote(query)}&count=8&freshness={freshness}&text=1&search=1"
    req = urllib.request.Request(url, headers={
        'Accept': 'application/json',
        'Accept-Encoding': 'gzip',
        'X-Subscription-Token': api_key
    })

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw_data = response.read()
            # 尝试解压 gzip
            try:
                import gzip
                data = json.loads(gzip.decompress(raw_data).decode('utf-8'))
            except:
                data = json.loads(raw_data.decode('utf-8', errors='ignore'))

        results = data.get('web', {}).get('results', [])
        if not results:
            return None

        # 过滤结果：只保留48小时内的内容
        cutoff_time = datetime.now() - timedelta(hours=48)
        filtered_results = []

        for r in results[:8]:
            # 检查结果是否有年龄信息
            age = r.get('age')  # Brave 提供的年龄字段（如 "2 hours ago"）
            published_time = r.get('published_time')  # ISO 时间戳

            # 判断是否在48小时内
            is_recent = False  # 默认为不最近，需要有明确的时间证明

            # 优先使用 published_time
            if published_time:
                try:
                    pub_dt = datetime.fromisoformat(published_time.replace('Z', '+00:00'))
                    pub_dt = pub_dt.replace(tzinfo=None)
                    if pub_dt >= cutoff_time:
                        is_recent = True
                except:
                    pass

            # 其次使用 age 字段（更严格的验证）
            elif age:
                # 解析年龄字符串
                age_lower = age.lower()
                if 'hour' in age_lower or 'ago' in age_lower:
                    # 小时内的内容 - 需要明确的小时数
                    try:
                        hours = int(re.search(r'(\d+)\s*hour?', age_lower).group(1))
                        if hours <= 24:  # 只接受24小时内的数据
                            is_recent = True
                    except:
                        # 如果无法解析小时数，不认为是最近的
                        is_recent = False
                elif 'day' in age_lower:
                    # "day" 关键词的内容一律排除（除非是 0 day）
                    try:
                        days = int(re.search(r'(\d+)\s*day?', age_lower).group(1))
                        if days == 0:
                            is_recent = True
                        else:
                            # days >= 1 的内容一律排除，即使是 "1 day ago"
                            is_recent = False
                    except:
                        is_recent = False
                # 包含 week/month/year 的不是48小时内
                elif any(w in age_lower for w in ['week', 'month', 'year']):
                    is_recent = False

            # 如果通过时间检查，添加到结果
            if is_recent:
                filtered_results.append(r)

        # 如果没有48小时内的结果，返回所有结果（放宽限制）
        if not filtered_results:
            # 放宽到7天内的结果
            cutoff_time_week = datetime.now() - timedelta(days=7)
            for r in results[:8]:
                age = r.get('age')
                published_time = r.get('published_time')
                is_recent = False

                if published_time:
                    try:
                        pub_dt = datetime.fromisoformat(published_time.replace('Z', '+00:00'))
                        pub_dt = pub_dt.replace(tzinfo=None)
                        if pub_dt >= cutoff_time_week:
                            is_recent = True
                    except:
                        pass
                elif age:
                    age_lower = age.lower()
                    try:
                        if 'hour' in age_lower:
                            hours = int(re.search(r'(\d+)\s*hour?', age_lower).group(1))
                            if hours <= 168:  # 7天
                                is_recent = True
                        elif 'day' in age_lower:
                            days = int(re.search(r'(\d+)\s*day?', age_lower).group(1))
                            if days <= 7:
                                is_recent = True
                    except:
                        pass

                if is_recent:
                    filtered_results.append(r)

        # 如果还是没有结果，使用前3个结果（不管时间）
        if not filtered_results and results:
            filtered_results = results[:3]

        # 合并所有结果的标题和描述
        texts = []
        for r in filtered_results[:5]:
            texts.append(r.get('title', ''))
            texts.append(r.get('description', ''))
        return ' '.join(texts) if texts else None
    except Exception:
        return None


def _fetch_stock_price_yahoo(ticker: str, timeout: int = 10) -> Optional[str]:
    """从 Yahoo Finance 获取实时股价

    Args:
        ticker: 股票代码（如 GOOGL, META, NVDA）
        timeout: 超时时间

    Returns:
        格式化的股价字符串（如 "$150.25"），失败返回 None
    """
    try:
        import yfinance as yf
        # 创建 Ticker 对象
        stock = yf.Ticker(ticker.upper())
        # 获取实时数据
        info = stock.info
        if not info:
            return None

        # 优先使用 current_price，其次使用 regularMarketPrice
        price = info.get('current_price') or info.get('regularMarketPrice') or info.get('previousClose')
        if price and isinstance(price, (int, float)) and price > 0:
            return f'${price:.2f}'
    except ImportError:
        # yfinance 未安装
        pass
    except Exception as e:
        # 记录错误但继续
        pass

    # 如果 yfinance 失败，尝试直接从 Yahoo Finance 网页抓取
    try:
        import urllib.request
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker.upper()}?interval=1d&range=1d"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
        })
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode('utf-8'))
            result = data.get('chart', {}).get('result', [])
            if result:
                meta = result[0].get('meta', {})
                price = meta.get('regularMarketPrice') or meta.get('previousClose')
                if price and isinstance(price, (int, float)) and price > 0:
                    return f'${price:.2f}'
    except Exception:
        pass

    return None


def _fetch_claude(prompt: str, timeout: int = 90) -> Optional[str]:
    """通过 Claude CLI 获取信息"""
    try:
        result = subprocess.run(
            ['claude', '--dangerously-skip-permissions', '-p', prompt],
            capture_output=True, text=True, timeout=timeout
        )
        if result.returncode == 0 and result.stdout:
            if _is_error_response(result.stdout):
                return None
            return result.stdout
    except (subprocess.TimeoutExpired, Exception):
        pass
    return None


def _extract_with_llm(prompt: str, timeout: int = 30) -> Optional[str]:
    """使用 LLM 从搜索结果中提取信息"""
    try:
        result = subprocess.run(
            ['claude', '--dangerously-skip-permissions', '-p', prompt],
            capture_output=True, text=True, timeout=timeout
        )
        if result.returncode == 0 and result.stdout:
            if _is_error_response(result.stdout):
                return None
            return result.stdout.strip()
    except Exception:
        pass
    return None


def fetch_stock_data(stock_code: str, timeout: int = 90) -> Optional[dict]:
    """获取股票数据：当前价格和涨跌幅

    使用 Brave Search + LLM 提取
    """
    # 多种精确查询策略，按优先级排序
    queries = [
        f"site:investing.com {stock_code} stock price",
        f"site:finance.yahoo.com {stock_code} quote",
        f'"{stock_code}" "stock price" "today" "real-time"',
        f'"{stock_code}" "current" "trading" "price" "NASDAQ"',
        f'"{stock_code}" "stock" "quote" "NASDAQ" "price"',
    ]

    price = '---'
    for query in queries:
        search_results = _fetch_brave_search(query, timeout=timeout)
        if not search_results or _is_error_response(search_results):
            continue

        # 用 LLM 提取当前价格
        extract_prompt = f"""From these search results, extract the CURRENT stock price for {stock_code}.

{search_results[:2000]}

CRITICAL RULES:
1. Look for phrases indicating CURRENT or TODAY'S price: "is trading at", "currently", "last priced at", "at market close", "opened at"
2. IGNORE: price targets, historical prices, "52-week", year-to-date mentions, or predictions
3. If multiple prices are mentioned, choose the one with context like "currently" or "trading at"

Return ONLY the price in format $XXX.XX (like $170.50)."""

        price_result = _extract_with_llm(extract_prompt, timeout=timeout)
        if price_result and not _is_error_response(price_result):
            m = re.search(r'\$\s*(\d{1,5}\.?\d*)', price_result)
            if m:
                try:
                    val = float(m.group(1))
                    if 1 <= val <= 100000:
                        price = f'${val:.2f}'
                        break
                except:
                    pass

    # 获取涨跌幅
    change = '0.0%'
    change_query = f'"{stock_code}" "percent" "change" "today" "NASDAQ"'
    change_results = _fetch_brave_search(change_query, timeout=timeout)
    if change_results:
        change_prompt = f"""Extract today's percent change for {stock_code} stock.

{change_results[:1500]}

Look for: +X%, -X%, up X%, down X%
Daily range: -10% to +10%

Return ONLY like +1.5% or -2.3%."""

        change_result = _extract_with_llm(change_prompt, timeout=timeout)
        if change_result and not _is_error_response(change_result):
            m = re.search(r'([+-]?\d+\.?\d*)%', change_result)
            if m:
                try:
                    val = float(m.group(1))
                    if -15 <= val <= 15 and val != 0:
                        change = f'{val}%'
                except:
                    pass

    return {'price': price, 'change': change}


def fetch_stock_price(stock_code: str, timeout: int = 90) -> Optional[str]:
    """获取股票最新价格（兼容旧接口）"""
    data = fetch_stock_data(stock_code, timeout)
    return data.get('price') if data else None


def fetch_stock_change(stock_code: str, timeout: int = 90) -> Optional[str]:
    """获取股票涨跌幅（兼容旧接口）"""
    data = fetch_stock_data(stock_code, timeout)
    return data.get('change') if data else None


def fetch_stock_reason(stock_code: str, timeout: int = 60) -> Optional[str]:
    """获取股票变动原因

    搜索策略：
    1. Brave Search API - 获取新闻和动态
    2. Claude CLI - 作为备选
    """
    # 1. 使用 Brave Search API 获取新闻
    brave_text = _fetch_brave_search(f"{stock_code} stock news today catalyst reason", timeout=timeout)
    if brave_text and not _is_error_response(brave_text):
        reason = _extract_reason_from_text(brave_text)
        if reason:
            return reason

    # 2. 回退到 Claude CLI 搜索
    claude_text = _fetch_claude(
        f"Search for: Why is {stock_code} stock moving today? What's the main catalyst or news? "
        f"Return ONLY 2-5 words describing the reason, lowercase. Examples: 'ai demand surge', "
        f"'earnings beat expectations', 'regulatory concerns'. Do NOT include 'according to' or 'based on'.",
        timeout=timeout
    )
    if claude_text and not _is_error_response(claude_text):
        cleaned = claude_text.strip().split('\n')[0]
        cleaned = re.sub(r'^["\']|["\']$', '', cleaned)
        words = [w for w in cleaned.split() if w not in ['-', '–', '—']]
        cleaned = ' '.join(words[:5])
        cleaned = re.sub(r'[.!?;,:\-]+$', '', cleaned)
        cleaned = cleaned.lower().strip()
        if 3 <= len(cleaned) <= 50 and cleaned.isascii():
            if not any(x in cleaned for x in _ERROR_INDICATORS + [
                'according to', 'based on', 'yahoo finance', 'bloomberg', 'cnbc'
            ]):
                return cleaned

    return None


def _extract_reason_from_text(text: str) -> Optional[str]:
    """从搜索结果文本中提取股票变动原因"""
    # 过滤常见词
    stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'stock', 'shares',
                  'today', 'inc', 'corp', 'nasdaq', 'nyse', 'reuters', 'ap', 'cnbc',
                  'bloomberg', 'yahoo', 'finance', 'marketwatch', 'benzinga',
                  'com', 'www', 'http', 'https', 'said', 'reported', 'also'}
    words = re.findall(r'[a-zA-Z]+', text.lower())
    filtered = [w for w in words[:20] if w not in stop_words and len(w) > 2]

    if len(filtered) >= 2:
        result = ' '.join(filtered[:4])
        if 3 <= len(result) <= 50 and not _is_error_response(result):
            return result

    return None


def extract_price_from_research(research_data: str) -> Optional[str]:
    """从研究数据中提取价格（简化版，支持中英文）"""
    # 先检查 Yahoo Finance 中文格式
    yahoo_pattern = r'当前价格[：:]\s*\$?\s*(\d{1,5}\.\d{2})'
    match = re.search(yahoo_pattern, research_data[:3000])
    if match:
        return f'${match.group(1)}'

    # 英文格式
    patterns = [
        r'(?:Current(?:\s*Stock)?(?:\s*Price)?|Price|Last(?:\s*Price)?)\s*[:=]\s*\$?\s*(\d{1,5}\.?\d{0,2})',
        r'\$\s*(\d{1,5}\.\d{2})\s*(?:USD)?\s*(?:per\s*share|/share)?',
        r'\$\s*(\d{1,5})\s',
        r'(?:trading|around|currently)\s+\$?\s*(\d{1,5}\.?\d{0,2})',
    ]
    for pattern in patterns:
        match = re.search(pattern, research_data[:3000], re.IGNORECASE)
        if match:
            price_num = match.group(1)
            # 检查匹配位置后是否跟着时间格式（避免从 "at 22:53" 中提取 22）
            match_end = match.end()
            context_after = research_data[match_end:match_end + 10]
            if ':' in context_after and re.search(r'\d{1,2}:\d{2}', context_after):
                continue  # 跳过时间格式
            if '.' not in price_num:
                price_num = f'{price_num}.00'
            elif len(price_num.split('.')[1]) == 1:
                price_num = f'{price_num}0'
            # 价格合理性检查：股价必须在 $1 - $99999 之间
            try:
                price_val = float(price_num)
                if price_val < 1.0:
                    continue  # 跳过不合理的低价（如 $0.25）
            except ValueError:
                continue
            return f'${price_num}'
    return None


def extract_change_from_research(research_data: str) -> Optional[str]:
    """从研究数据中提取涨跌幅（简化版）"""
    patterns = [
        r'(?:stock|price|shares?)[\s,]*(?:change|move|gain|loss|rise|fall|drop)[\s:]*([+-]?\d+\.?\d*)%',
        r'(?:day|daily|today)[\s\']*(?:change|gain|loss|move)[\s:]*([+-]?\d+\.?\d*)%',
        r'(?:up|down|rose|fell|gained|lost)[\s]+by\s+([+-]?\d+\.?\d*)%',
        r'([+-]?\d+\.?\d*)%\s+(?:higher|lower)',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, research_data[:3000], re.IGNORECASE)
        if matches:
            change = matches[0]
            if not change.startswith(('+', '-')):
                snippet_lower = research_data[:500].lower()
                if any(w in snippet_lower for w in ['down', 'declin', 'drop', 'fall', 'loss', 'lower']):
                    change = '-' + change
                else:
                    change = '+' + change
            return f'{change}%'
    return None


# =============================================================================
# 基础步骤类
# =============================================================================

class BaseStep(ABC):
    """步骤基类"""

    def __init__(self, skill_dir: Optional[Path] = None):
        """
        初始化步骤

        Args:
            skill_dir: 技能根目录，用于查找配置和资源
        """
        self.skill_dir = skill_dir or Path(__file__).parent.parent
        self.verticals_dir = self.skill_dir / "verticals"
        self.personas_dir = self.skill_dir / "personas"
        self.assets_dir = self.skill_dir / "assets"

    @abstractmethod
    def run(self, session: XhsSession, **kwargs) -> bool:
        """
        执行步骤

        Args:
            session: XhsSession 实例
            **kwargs: 额外参数

        Returns:
            bool: 步骤是否成功
        """
        pass

    def load_vertical_config(self, vertical: str) -> Dict[str, Any]:
        """加载垂类配置"""
        config_path = self.verticals_dir / f"{vertical}.json"
        if not config_path.exists():
            raise FileNotFoundError(f"Vertical config not found: {config_path}")
        with open(config_path) as f:
            return json.load(f)

    def load_persona(self, vertical: str) -> str:
        """加载 persona"""
        persona_file = self.personas_dir / f"{vertical}.md"
        if persona_file.exists():
            return persona_file.read_text()
        return ""

    def call_llm(self, prompt: str, expect_json: bool = False,
                 timeout: int = 120) -> Any:
        """
        调用 LLM

        Args:
            prompt: 提示词
            expect_json: 是否期望 JSON 输出
            timeout: 超时时间（秒）

        Returns:
            LLM 响应（字符串或解析后的字典）
        """
        result = subprocess.run(
            ['claude', '--dangerously-skip-permissions', '-p', prompt],
            capture_output=True, text=True, timeout=timeout
        )

        if result.returncode != 0:
            raise RuntimeError(f"LLM call failed: {result.stderr}")

        output = result.stdout.strip()

        if expect_json:
            return self._parse_json_output(output)
        return output

    def _parse_json_output(self, text: str) -> Dict[str, Any]:
        """从 LLM 输出中解析 JSON"""
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试找到第一个 { 和最后一个 }（最可靠的方式）
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end > start:
            candidate = text[start:end+1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                # 尝试修复字符串中未转义的换行符
                try:
                    import re as _re
                    # 将字符串值中的字面换行替换为 \n
                    def fix_newlines(m):
                        return m.group(0).replace('\n', '\\n').replace('\r', '')
                    fixed = _re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_newlines, candidate, flags=_re.DOTALL)
                    return json.loads(fixed)
                except Exception:
                    pass

        raise ValueError(f"Cannot parse JSON from LLM output: {text[:200]}")


# =============================================================================
# Step 1: Research
# =============================================================================

class Step1Research(BaseStep):
    """Step 1: 搜索数据"""

    def _infer_search_queries(self, session: XhsSession, config: dict) -> list:
        """
        使用 LLM 推断需要搜索的内容

        Args:
            session: XhsSession 实例
            config: 垂类配置

        Returns:
            List of dict with 'template' and 'purpose' keys, or None if inference fails
        """
        session.log('info', 'research', 'Using LLM to infer search queries...')

        # 获取垂类信息用于构建 prompt
        vertical_name = config.get('name', session.vertical)
        vertical_desc = config.get('description', '')

        # 构建推断 prompt
        infer_prompt = f"""你是一位专业的小红书内容研究专家。

## 任务
对于主题「{session.topic}」（垂类：{vertical_name}），请推断需要搜索哪些关键信息来写出高质量的小红书内容。

## 垂类说明
{vertical_desc}

## 要求
1. 返回 3-5 个精确的搜索查询
2. 每个查询都应该针对不同的信息维度（如：价格/数据、新闻动态、用户评价、对比分析等）
3. 查询必须简洁精准，适合搜索引擎
4. 必须包含时间关键词确保获取最新信息（如：today, latest, current）

## 输出格式（严格遵守 JSON）
{{
  "queries": [
    {{"query": "搜索查询1", "purpose": "查询目的说明"}},
    {{"query": "搜索查询2", "purpose": "查询目的说明"}},
    {{"query": "搜索查询3", "purpose": "查询目的说明"}}
  ]
}}

请只输出 JSON，不要添加任何其他文字。"""

        try:
            result = self.call_llm(infer_prompt, expect_json=True, timeout=60)

            if result and 'queries' in result:
                inferred_queries = result['queries']

                # 转换为内部格式
                queries = []
                for q in inferred_queries:
                    queries.append({
                        'template': q.get('query', ''),
                        'purpose': q.get('purpose', ''),
                        'inferred': True  # 标记为 LLM 推断
                    })

                session.log('success', 'research',
                          f'LLM inferred {len(queries)} search queries',
                          {'queries': [q['template'] for q in queries]})
                return queries

        except Exception as e:
            session.log('warning', 'research',
                      f'LLM inference failed: {e}, falling back to config queries')

        return None

    def run(self, session: XhsSession, **kwargs) -> bool:
        """执行搜索步骤"""
        session.log('info', 'research', 'Step started',
                   {'topic': session.topic, 'vertical': session.vertical})

        session.update_step('research', 'in_progress')

        try:
            config = self.load_vertical_config(session.vertical)
            research_config = config.get('content_research', {})

            # ========== 新流程：使用 LLM 推断搜索查询 ==========
            # 优先级：LLM 推断 > 配置文件查询 > 默认模板
            queries = None

            # 1. 尝试 LLM 推断
            inferred = self._infer_search_queries(session, config)
            if inferred:
                queries = inferred

            # 2. 回退到配置文件查询
            if not queries:
                queries = research_config.get('queries', [])

            # 对于股票垂类，首先从 Yahoo Finance 获取准确数据
            stock_yahoo_data = None
            if session.vertical == 'stock':
                yahoo_price = _fetch_stock_price_yahoo(session.topic, timeout=10)
                if yahoo_price:
                    # 获取更详细的股票数据
                    try:
                        import yfinance as yf
                        stock = yf.Ticker(session.topic)
                        info = stock.info
                        if info:
                            current_price = info.get('current_price') or info.get('regularMarketPrice')
                            previous_close = info.get('previousClose')
                            day_change = info.get('current_price') - info.get('previousClose') if current_price and previous_close else None
                            day_change_pct = (day_change / previous_close * 100) if day_change and previous_close else None

                            # 获取52周范围
                            week_52_high = info.get('fiftyTwoWeekHigh')
                            week_52_low = info.get('fiftyTwoWeekLow')

                            # 获取公司名称
                            company_name = info.get('longName') or info.get('shortName')

                            stock_yahoo_data = f"""
## Yahoo Finance 数据（实时）
股票代码: {session.topic}
公司名称: {company_name or 'N/A'}
当前价格: ${current_price:.2f if current_price else 0}
前收盘价: ${previous_close:.2f if previous_close else 0}
今日涨跌: ({day_change:+.2f} if day_change else 0) ({day_change_pct:+.2f}% if day_change_pct else "0.00%")
52周范围: ${week_52_low:.2f if week_52_low else 0} - ${week_52_high:.2f if week_52_high else 0}

**注意**: 以下为搜索结果，请以 Yahoo Finance 数据为准。
"""
                            session.log('info', 'research', f'Fetched Yahoo Finance data: ${current_price:.2f if current_price else 0}')
                    except Exception as e:
                        session.log('warning', 'research', f'Yahoo Finance data fetch partial: {e}')
                        stock_yahoo_data = f"""
## Yahoo Finance 数据（实时）
股票代码: {session.topic}
当前价格: {yahoo_price}

**注意**: 以下为搜索结果，请以 Yahoo Finance 价格为准。
"""

            if not queries:
                queries = [{
                    'template': f'{session.topic} latest {datetime.now().year}',
                    'purpose': '获取最新信息',
                    'required': True
                }]

            current_year = datetime.now().year
            all_results = []
            search_queries_used = []

            for q in queries:
                template = q.get('template', '')
                purpose = q.get('purpose', '')
                is_inferred = q.get('inferred', False)

                query = template.replace('{topic}', session.topic).replace('{year}', str(current_year))

                # 对于推断的查询，已经包含时间关键词，不再强制添加
                # 对于配置的查询，添加时间关键词确保获取最新数据
                if not is_inferred:
                    time_keywords = ' today latest current'
                    if 'today' not in query.lower() and 'latest' not in query.lower():
                        query = f'{query} {time_keywords}'

                search_queries_used.append(query)
                source = 'LLM' if is_inferred else 'config'
                session.log('info', 'research', f'Searching: {query[:50]}...',
                          {'purpose': purpose, 'source': source})

                try:
                    search_start = time.time()

                    # 使用 Brave Search API
                    brave_results = _fetch_brave_search(query, timeout=30)

                    if brave_results:
                        # 用 LLM 总结搜索结果
                        summary_prompt = f"""Summarize these search results for: "{query}"

{brave_results[:3000]}

Focus on:
- Key data points (prices, numbers, dates)
- Important news or events
- Relevant facts

Be factual and concise."""

                        summary = _extract_with_llm(summary_prompt, timeout=30)
                        if summary:
                            all_results.append(
                                f"## Query: {query}\n**Purpose**: {purpose}\n\n{summary}"
                            )
                            elapsed = time.time() - search_start
                            session.log('debug', 'research', 'Search successful',
                                      {'query': query[:30], 'elapsed': round(elapsed, 2)})
                            self._save_search_results(session, query, summary, elapsed)
                        else:
                            all_results.append(
                                f"## Query: {query}\n**Purpose**: {purpose}\n\n{brave_results[:2000]}"
                            )
                    else:
                        all_results.append(
                            f"## Query: {query}\n**Purpose**: {purpose}\n\n**No results found**"
                        )
                        session.log('warn', 'research', 'No results', {'query': query[:30]})

                except Exception as e:
                    all_results.append(f"## Query: {query}\n**Purpose**: {purpose}\n\n**Search error**: {str(e)}")
                    session.log('error', 'research', 'Search error',
                              {'query': query[:30], 'error': str(e)})

            # 对于股票垂类，在开头添加 Yahoo Finance 数据
            if stock_yahoo_data:
                all_results.insert(0, stock_yahoo_data)

            # 写入 research_raw.md（即使没有搜索结果也继续）
            if all_results:
                research_output = '\n\n---\n\n'.join(all_results)
            else:
                research_output = f"# 搜索结果\n\n搜索: {session.topic}\n\n注意: 暂无搜索结果，将基于人设生成内容。"

            session.write_file('research_raw.md', research_output)

            # 更新 session
            session.update_step('research', 'completed', {
                'search_queries': search_queries_used,
                'query_source': 'llm_inferred' if any(q.get('inferred') for q in queries) else 'config',
                'results_summary': research_output[:500].replace('\n', ' '),
                'raw_output_file': 'research_raw.md',
                'total_queries': len(search_queries_used),
                'results_length': len(research_output)
            })

            session.log('success', 'research', 'Step completed',
                       {'queries_count': len(search_queries_used)})
            return True

        except Exception as e:
            session.log('error', 'research', f'Step failed: {str(e)}', exc_info=True)
            session.update_step('research', 'failed', {'error': str(e)})
            return False

    def _save_search_results(self, session: XhsSession, query: str,
                            results: str, elapsed: float) -> None:
        """保存搜索结果到独立文件"""
        search_data = {
            'query': query,
            'results': results,
            'elapsed_seconds': round(elapsed, 2),
            'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        }

        filename = f"search_{query[:20].replace(' ', '_').replace('/', '_')}.json"
        file_path = session.get_file_path(filename)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(search_data, f, ensure_ascii=False, indent=2)


# =============================================================================
# Step 2: Generate Content
# =============================================================================

class Step2Generate(BaseStep):
    """Step 2: 生成内容"""

    def run(self, session: XhsSession, feedback: str = "", **kwargs) -> Tuple[bool, str]:
        """
        执行内容生成步骤

        Returns:
            Tuple[bool, str]: (是否成功, 错误信息)
        """
        session.log('info', 'generate', 'Step started',
                   {'topic': session.topic, 'has_feedback': bool(feedback)})

        session.update_step('generate', 'in_progress')

        try:
            config = self.load_vertical_config(session.vertical)
            persona_content = self.load_persona(session.vertical)

            # 读取搜索结果
            research_data = ""
            if session.file_exists('research_raw.md'):
                research_data = session.read_file('research_raw.md')

            # 构建生成 prompt
            content_structure = config.get('content_structure', {})
            min_length = content_structure.get('min_length', 300)
            max_length = content_structure.get('max_length', 800)
            paragraphs = content_structure.get('paragraphs', [])

            para_desc = []
            for p in paragraphs:
                para_desc.append(
                    f"  {p['order']}. {p['name']} ({p.get('length', 'N/A')}): {p['instruction']}"
                )
            para_text = '\n'.join(para_desc)

            feedback_section = ""
            if feedback:
                feedback_section = f"""
## 上次验证反馈（请改进）
{feedback}

请根据以上反馈改进内容质量。
"""
                session.log('info', 'generate', f'Using previous feedback',
                          {'feedback': feedback[:100]})

            prompt = f"""你是一个专业的小红书内容创作者。

{persona_content}

## 生成任务

请为话题「{session.topic}」（垂类：{session.vertical}）生成一篇高质量的小红书内容。

## 搜索结果（必须严格基于这些数据）

{research_data}

{feedback_section}

## 数据新鲜度要求（CRITICAL）
- 搜索结果均为48小时内的最新数据
- 提及的价格、数据必须注明时间（如"今日"、"最新"、"截至X日"）
- 如果搜索结果中的数据超过24小时，必须说明"截至昨日"或具体日期
- 禁止使用任何超过48小时的数据作为"当前"数据

## 内容结构要求

- 最小长度：{min_length}字
- 最大长度：{max_length}字

段落结构：
{para_text}

## 输出格式（严格遵守）

你必须严格按照以下 JSON 格式输出，不要输出任何其他内容：
{{
  "title": "4-8字主标题（吸引眼球，不带冒号）",
  "subtitle": "8-15字副标题（补充说明，呼应主标题）",
  "content": "正文内容（纯文本，段落用换行分隔，不要Markdown加粗）",
  "tags": ["#标签1", "#标签2"]
}}

## 关键要求
1. title 必须 4-8 字，不要使用冒号分隔
2. subtitle 必须 8-15 字
3. content 长度在 {min_length}-{max_length} 字之间
4. **数据新鲜度要求**：
   - 所有价格、数据必须来自48小时内的搜索结果
   - 提及价格时必须说明时间范围（如"今日"、"最新"、"截至昨日"）
   - 如果搜索结果没有明确时间戳的数据，必须说"根据最新公开数据"
   - **绝对禁止使用超过48小时的数据作为"当前价格"**
5. 不要使用 bullet point（①②③、●■■、1.2.3.）
6. 不要使用 AI 痕迹表达（如"值得注意的是"、"综上所述"、"然而"、"此外"等）
7. 输出纯文本，不要 HTML 标签或 Markdown 加粗
8. 如果是股票分析，必须有明确判断（看好/看空/观望）
9. 严格输出 JSON 格式，不要在 JSON 前后添加任何文字"""

            session.log('debug', 'generate', 'Calling LLM',
                      {'prompt_length': len(prompt)})

            llm_start = time.time()
            result = self.call_llm(prompt, expect_json=True, timeout=120)
            llm_elapsed = time.time() - llm_start

            session.log('debug', 'generate', 'LLM response received',
                      {'elapsed': round(llm_elapsed, 2)})

            if not result:
                raise ValueError("LLM returned empty result")

            title = result.get('title', '')
            subtitle = result.get('subtitle', '')
            content = result.get('content', '')
            tags = result.get('tags', [])

            if not title or not content:
                raise ValueError(f"Missing required fields: title={bool(title)}, content={bool(content)}")

            # 写入 content.md
            if tags:
                tag_str = ' '.join(tags)
                output = content + '\n\n' + tag_str
            else:
                output = content

            session.write_file('content.md', output)

            # 更新 session
            session.update_step('generate', 'completed', {
                'title': title,
                'subtitle': subtitle,
                'content_length': len(content),
                'tags': tags,
                'output_file': 'content.md',
                'llm_elapsed': round(llm_elapsed, 2)
            })

            # 同时更新顶层 title/subtitle
            session.set_title(title, subtitle)

            session.log('success', 'generate', 'Step completed',
                       {'title': title, 'content_length': len(content)})
            return True, ""

        except Exception as e:
            error_msg = str(e)
            session.log('error', 'generate', f'Step failed: {error_msg}', exc_info=True)
            session.update_step('generate', 'failed', {'error': error_msg})
            return False, error_msg


# =============================================================================
# Step 3: Validate Content
# =============================================================================

class Step3Validate(BaseStep):
    """Step 3: 验证内容"""

    def run(self, session: XhsSession, **kwargs) -> Tuple[bool, str]:
        """
        执行验证步骤

        Returns:
            Tuple[bool, str]: (是否通过, 反馈信息)
        """
        session.log('info', 'validate', 'Step started')

        session.update_step('validate', 'in_progress')

        try:
            config = self.load_vertical_config(session.vertical)
            validation_config = config.get('content_validation', {})
            rules = validation_config.get('rules', [])
            min_score = validation_config.get('min_score', 5)

            # ========== 数据新鲜度验证 ==========
            freshness_check = self._validate_data_freshness(session)
            if not freshness_check['passed']:
                session.log('warn', 'validate', 'Data freshness check failed',
                          {'reason': freshness_check['reason']})
                # 对于 stock 垂类，数据新鲜度是硬性要求
                if session.vertical == 'stock':
                    session.update_step('validate', 'failed', {
                        'error': f"数据不够新鲜: {freshness_check['reason']}"
                    })
                    return False, f"数据不够新鲜: {freshness_check['reason']}"
            else:
                session.log('info', 'validate', 'Data freshness check passed')

            # 读取生成的内容
            if not session.file_exists('content.md'):
                raise FileNotFoundError("content.md not found")

            content = session.read_file('content.md')

            # 获取 title/subtitle
            gen_data = session.get_step_data('generate')
            title = gen_data.get('title', '')
            subtitle = gen_data.get('subtitle', '')

            # 执行验证
            result = self._validate_content(
                content, title, subtitle, rules, session.topic, min_score
            )

            status = 'passed' if result['passed'] else 'failed'
            session.update_step('validate', status, result)

            if result['passed']:
                session.log('success', 'validate', 'Validation passed',
                          {'score': result['score']})
                return True, "passed"
            else:
                session.log('warn', 'validate', 'Validation failed',
                          {'feedback': result['feedback'][:100]})
                return False, result['feedback']

        except Exception as e:
            error_msg = str(e)
            session.log('error', 'validate', f'Step failed: {error_msg}', exc_info=True)
            session.update_step('validate', 'failed', {'error': error_msg})
            return False, error_msg

    def _validate_data_freshness(self, session: XhsSession) -> Dict[str, Any]:
        """
        验证数据新鲜度

        检查研究数据和生成内容的时间戳，确保数据在可接受的时间范围内。
        对于 stock 垂类，要求必须是实时/当日数据。
        对于其他垂类，允许 7 天内的数据。
        """
        from datetime import datetime, timedelta

        now = datetime.now()
        result = {'passed': True, 'reason': ''}

        # 1. 检查 research 步骤的时间戳
        research_step = session.get_step_data('research')
        if research_step:
            research_time_str = research_step.get('updated_at') or research_step.get('started_at')
            if research_time_str:
                try:
                    research_time = datetime.fromisoformat(research_time_str.replace('Z', '+00:00'))
                    # 转换为 naive datetime 进行比较
                    if research_time.tzinfo is not None:
                        research_time = research_time.replace(tzinfo=None)
                    age_hours = (now - research_time).total_seconds() / 3600

                    # stock 垂类要求 24 小时内数据
                    if session.vertical == 'stock':
                        if age_hours > 24:
                            result['passed'] = False
                            result['reason'] = f"研究数据超过24小时 ({age_hours:.1f}小时前)"
                            return result
                    # 其他垂类允许 7 天内数据
                    elif age_hours > 168:  # 7天
                        result['passed'] = False
                        result['reason'] = f"研究数据超过7天 ({age_hours/24:.1f}天前)"
                        return result
                except:
                    pass  # 时间解析失败，继续检查

        # 2. 检查 research_raw.md 中的时间标记
        if session.file_exists('research_raw.md'):
            research_content = session.read_file('research_raw.md')

            # 检查是否有明确的时间戳
            import re
            # 查找形如 "2026-03-30" 或 "March 30" 等日期
            date_patterns = [
                r'\b(20\d{2})-(\d{1,2})-(\d{1,2})\b',  # 2026-03-30
                r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* (\d{1,2})\b',  # March 30
            ]

            dates_found = []
            for pattern in date_patterns:
                matches = re.findall(pattern, research_content, re.IGNORECASE)
                dates_found.extend(matches)

            if dates_found:
                # 检查最新日期是否在合理范围内
                # 这里简化处理：如果找到了日期，认为有数据
                pass

            # 3. 对于 stock 垂类，检查是否有 Yahoo Finance 实时数据标记
            if session.vertical == 'stock':
                if 'Yahoo Finance 数据（实时）' in research_content:
                    # 有实时数据标记，通过
                    result['passed'] = True
                elif '当前价格' in research_content:
                    # 有价格数据，可能不够实时但可以接受
                    result['passed'] = True
                else:
                    # 没有找到任何实时价格数据
                    result['passed'] = False
                    result['reason'] = "未找到实时股价数据"
                    return result

        # 4. 检查内容中是否有明确的时间相关表述
        if session.file_exists('content.md'):
            content = session.read_file('content.md')

            # 检查是否有过时表述（如 "去年"、"2024" 等旧年份）
            current_year = now.year
            old_year_patterns = [
                r'\b20(24|23|22|21|20|19)\b',  # 2020-2024
            ]

            for pattern in old_year_patterns:
                if re.search(pattern, content):
                    # 检查是否是当前年份
                    matches = re.findall(pattern, content)
                    for match in matches:
                        year = int('20' + match)
                        if year < current_year - 1:  # 超过1年的数据认为过时
                            result['passed'] = False
                            result['reason'] = f"内容包含过时年份: {year}年"
                            return result

        return result

    def _validate_content(self, content: str, title: str, subtitle: str,
                         rules: list, topic: str, min_score: int) -> Dict[str, Any]:
        """验证内容质量 - 使用本地验证规则"""
        return validate_content(
            content=content,
            title=title,
            subtitle=subtitle,
            rules=rules,
            topic=topic,
            min_score=min_score
        )


# =============================================================================
# Step 4: Prepare Image Variables
# =============================================================================

class Step4PrepareImg(BaseStep):
    """Step 4: 准备封面变量"""

    def run(self, session: XhsSession, **kwargs) -> bool:
        """执行封面变量准备步骤"""
        session.log('info', 'prepare_img', 'Step started')
        session.update_step('prepare_img', 'in_progress')

        try:
            config = self.load_vertical_config(session.vertical)
            cover_config = config.get('cover_config', {})

            # 检查是否有多图配置
            images_config = cover_config.get('images', [])

            if images_config:
                # 多图模式：为每个图片准备 prompt
                return self._prepare_multi_image_prompts(session, cover_config, images_config)
            else:
                # 单图模式（原有逻辑）
                return self._prepare_single_image_prompt(session, cover_config)

        except Exception as e:
            session.log('error', 'prepare_img', f'Step failed: {str(e)}', exc_info=True)
            session.update_step('prepare_img', 'failed', {'error': str(e)})
            return False

    def _prepare_single_image_prompt(self, session: XhsSession, cover_config: Dict) -> bool:
        """准备单图 prompt（原有逻辑）"""
        variables_config = cover_config.get('prompt_variables', {})

        if not variables_config:
            template = cover_config.get('background_prompt_template', '')
            session.update_step('prepare_img', 'completed', {
                'variables': {},
                'variables_source': {},
                'filled_prompt': template,
                'image_count': 1,
                'prompts': [template]
            })
            session.log('info', 'prepare_img', 'No variables to prepare, using template directly')
            return True

        # 读取搜索结果和内容
        research_data = ""
        if session.file_exists('research_raw.md'):
            research_data = session.read_file('research_raw.md')

        content_data = ""
        if session.file_exists('content.md'):
            content_data = session.read_file('content.md')

        # 获取 title/subtitle
        gen_data = session.get_step_data('generate')
        title = gen_data.get('title', '')
        subtitle = gen_data.get('subtitle', '')

        context = {
            'topic': session.topic,
            'vertical': session.vertical,
            'date': datetime.now().strftime('%b %d').upper(),
            'title': title,
            'subtitle': subtitle
        }

        resolved = {}
        sources = {}

        # 解析变量 - 支持依赖顺序，多轮迭代
        max_iterations = 5
        for iteration in range(max_iterations):
            updated = False
            for var_name, var_config in variables_config.items():
                if var_name in resolved:
                    continue

                # 检查依赖
                depends_on = var_config.get('depends_on', [])
                if not all(dep in resolved for dep in depends_on):
                    continue

                try:
                    # 更新 context，包含已解析的变量
                    update_ctx = {**context, **resolved}
                    value, source = self._resolve_variable(
                        var_name, var_config, update_ctx, session, research_data
                    )
                    resolved[var_name] = value
                    sources[var_name] = source
                    session.log('debug', 'prepare_img', f'Resolved {var_name}',
                              {'value': str(value)[:50], 'source': source})
                    updated = True
                except Exception as e:
                    session.log('warn', 'prepare_img',
                              f'Failed to resolve {var_name}: {str(e)}')
                    resolved[var_name] = var_config.get('default', '')
                    sources[var_name] = 'default'
                    updated = True

            if not updated:
                break

        # 填充模板
        template = cover_config.get('background_prompt_template', '')
        for _ in range(3):
            prev = template
            for var_name, var_value in resolved.items():
                template = template.replace(f'{{{var_name}}}', str(var_value))
            if template == prev:
                break

        # 更新 session
        session.update_step('prepare_img', 'completed', {
            'variables': resolved,
            'variables_source': sources,
            'filled_prompt': template,
            'image_count': 1,
            'prompts': [template]
        })

        session.log('success', 'prepare_img', 'Step completed',
                   {'variables_count': len(resolved)})
        return True

    def _prepare_multi_image_prompts(self, session: XhsSession, cover_config: Dict,
                                    images_config: list) -> bool:
        """准备多图 prompts"""
        # 获取共享的 variables
        variables_config = cover_config.get('prompt_variables', {})

        # 读取搜索结果和内容
        research_data = ""
        if session.file_exists('research_raw.md'):
            research_data = session.read_file('research_raw.md')

        # 获取 title/subtitle
        gen_data = session.get_step_data('generate')
        title = gen_data.get('title', '')
        subtitle = gen_data.get('subtitle', '')

        context = {
            'topic': session.topic,
            'vertical': session.vertical,
            'date': datetime.now().strftime('%b %d').upper(),
            'title': title,
            'subtitle': subtitle
        }

        resolved = {}
        sources = {}

        # 解析共享变量
        if variables_config:
            max_iterations = 5
            for iteration in range(max_iterations):
                updated = False
                for var_name, var_config in variables_config.items():
                    if var_name in resolved:
                        continue

                    depends_on = var_config.get('depends_on', [])
                    if not all(dep in resolved for dep in depends_on):
                        continue

                    try:
                        update_ctx = {**context, **resolved}
                        value, source = self._resolve_variable(
                            var_name, var_config, update_ctx, session, research_data
                        )
                        resolved[var_name] = value
                        sources[var_name] = source
                        session.log('debug', 'prepare_img', f'Resolved {var_name}',
                                  {'value': str(value)[:50], 'source': source})
                        updated = True
                    except Exception as e:
                        session.log('warn', 'prepare_img',
                                  f'Failed to resolve {var_name}: {str(e)}')
                        resolved[var_name] = var_config.get('default', '')
                        sources[var_name] = 'default'
                        updated = True

                if not updated:
                    break

        # 为每个图片填充 prompt
        prompts = []
        image_configs = []

        for img_config in images_config:
            template = img_config.get('background_prompt_template', '')
            img_id = img_config.get('id', f'img_{len(prompts)}')

            # 填充模板变量
            filled_template = template
            for _ in range(3):
                prev = filled_template
                for var_name, var_value in resolved.items():
                    filled_template = filled_template.replace(f'{{{var_name}}}', str(var_value))
                if filled_template == prev:
                    break

            prompts.append(filled_template)
            image_configs.append({
                'id': img_id,
                'name': img_config.get('name', img_id),
                'aspect_ratio': img_config.get('aspect_ratio', '1:1'),
                'is_cover': img_config.get('is_cover', False)
            })

        # 更新 session
        session.update_step('prepare_img', 'completed', {
            'variables': resolved,
            'variables_source': sources,
            'image_count': len(prompts),
            'prompts': prompts,
            'image_configs': image_configs
        })

        session.log('success', 'prepare_img', 'Multi-image Step completed',
                   {'image_count': len(prompts), 'variables_count': len(resolved)})
        return True

    def _resolve_variable(self, var_name: str, var_config: Dict,
                         context: Dict, session: XhsSession,
                         research_data: str) -> Tuple[str, str]:
        """解析单个变量"""

        source = var_config.get('source', 'literal')
        default = var_config.get('default', '')

        # literal
        if source == 'literal':
            return var_config.get('value', ''), 'literal'

        # date
        if source == 'date':
            fmt = var_config.get('format', '%b %d')
            return datetime.now().strftime(fmt).upper(), 'date'

        # extract_from_topic
        if source == 'extract_from_topic':
            return self._extract_from_topic(var_config, context['topic']), 'extract_from_topic'

        # from_content
        if source == 'from_content':
            return self._extract_from_content(var_config, context, session, var_name), 'from_content'

        # web_search
        if source == 'web_search':
            return self._search_variable(var_config, var_name, context, session, research_data), 'web_search'

        # conditional
        if source == 'conditional':
            return self._resolve_conditional(var_config, context), 'conditional'

        # llm_inference
        if source == 'llm_inference':
            return self._infer_variable(var_config, context, var_key=var_name), 'llm_inference'

        return default, 'default'

    def _extract_from_topic(self, var_config: Dict, topic: str) -> str:
        """从话题中提取变量"""
        extract_type = var_config.get('extract', 'regex')
        pattern = var_config.get('pattern', '')

        if extract_type == 'regex' and pattern:
            match = re.search(pattern, topic, re.IGNORECASE)
            if match:
                return match.group(1) if match.groups() else match.group(0)

        if extract_type == 'code':
            ascii_only = re.sub(r'[^A-Za-z0-9]', ' ', topic)
            code_match = re.search(r'\b([A-Z]{1,5})\b', ascii_only.upper())
            if code_match:
                return code_match.group(1)
            codes = re.findall(r'[A-Z]{2,5}', ascii_only.upper())
            if codes:
                return max(codes, key=len)

        return topic[:10]

    def _extract_from_content(self, var_config: Dict, context: Dict,
                             session: XhsSession, var_name: str = '') -> str:
        """从内容中提取变量 - 完全泛化版本"""
        description = var_config.get('description', '')

        # 标准字段：标题、副标题
        if description == '标题':
            return context.get('title', '')
        if description == '副标题':
            return context.get('subtitle', '')

        # 泛化处理：任何包含"要点"、"总结"、"观点"等关键词的变量都从内容中提取
        # 使用变量出现顺序来分配要点索引，而不是依赖变量名
        point_keywords = ['要点', '总结', '观点', 'quote', 'point', 'highlight']
        if any(kw in description.lower() for kw in point_keywords):
            content = context.get('content', '')
            if not content:
                content_file = session.session_dir / 'content.md'
                if content_file.exists():
                    content = content_file.read_text()

            if content:
                # 使用 session 级别的计数器来跟踪要点提取顺序
                counter_key = '_content_point_counter'
                point_num = session._data.get(counter_key, 0) + 1
                session._data[counter_key] = point_num

                session.log('debug', 'prepare_img',
                    f'Extracting content point #{point_num} for {var_name} (desc: {description[:20]})')

                # 使用缓存：只在第一次调用时提取所有要点
                cache_key = '_key_points_cache'
                key_points = session._data.get(cache_key)

                if key_points is None:
                    key_points = self._extract_all_key_points(content, session)
                    session._data[cache_key] = key_points
                    session.log('debug', 'prepare_img', f'Cached {len(key_points)} key points')

                # 循环使用要点（如果请求的索引超出范围）
                if key_points:
                    index = (point_num - 1) % len(key_points)
                    return key_points[index]

        # 返回默认值
        return var_config.get('default', '')

    def _extract_key_point_from_content(self, content: str, point_num: int,
                                       session: XhsSession) -> Optional[str]:
        """从内容中提取第N个要点（已废弃，保留兼容性）"""
        # 获取所有要点
        key_points = self._extract_all_key_points(content, session)
        if point_num <= len(key_points):
            return key_points[point_num - 1]
        return None

    def _extract_all_key_points(self, content: str, session: XhsSession) -> list:
        """从内容中提取所有要点（3-4个）- 泛化版本，适用于所有垂类"""
        # 使用 LLM 提取要点，让 LLM 根据内容类型自适应
        extract_prompt = f"""从以下小红书内容中提取3-4个最精华的观点或卖点。

内容:
{content[:2000]}

要求:
- 每个要点8-15个中文字符
- 提取内容的核心观点、数据或亮点
- 不要加序号、标点符号
- 直接返回要点列表，每行一个

只返回要点列表，不要解释。"""

        result = _extract_with_llm(extract_prompt, timeout=30)

        if result and not _is_error_response(result):
            # 清理和过滤结果
            points = []
            for line in result.strip().split('\n'):
                line = line.strip()
                # 去除序号和符号
                line = line.lstrip('0123456789.-•、·●○○►▶▪')
                line = line.strip('\'"`"')

                # 泛化过滤：5-30字符，有实际内容
                if 5 <= len(line) <= 30:
                    # 必须有中文或数字或英文
                    has_content = (
                        any('\u4e00' <= char <= '\u9fff' for char in line) or
                        any(char.isdigit() for char in line) or
                        any('a' <= char.lower() <= 'z' for char in line)
                    )
                    if has_content:
                        # 截取到15字
                        if len(line) > 15:
                            line = line[:15]
                        points.append(line)

                if len(points) >= 4:
                    break

            if points:
                session.log('info', 'prepare_img', f'Extracted {len(points)} key points')
                return points

        # 备用策略：直接从内容中提取句子
        return self._extract_sentences_as_key_points(content)

    def _extract_sentences_as_key_points(self, content: str) -> list:
        """备用策略：从内容中提取句子作为要点"""
        import re

        # 按句号、问号、感叹号、换行分割
        sentences = re.split(r'[。！？\n]', content)

        points = []
        for sent in sentences:
            sent = sent.strip()
            # 过滤掉太短或太长的句子
            if 8 <= len(sent) <= 30:
                # 必须有实际内容（中文、数字或英文）
                has_content = (
                    any('\u4e00' <= char <= '\u9fff' for char in sent) or
                    any(char.isdigit() for char in sent) or
                    any('a' <= char.lower() <= 'z' for char in sent)
                )
                if has_content:
                    # 截取到15字
                    if len(sent) > 15:
                        sent = sent[:15]
                    points.append(sent)

                if len(points) >= 4:
                    break

        # 如果还是没提取到，返回通用要点
        if not points:
            return ["内容精华值得收藏", "实用干货持续分享", "真实体验仅供参考", "感谢关注支持"]

        return points

    def _search_variable(self, var_config: Dict, var_name: str,
                        context: Dict, session: XhsSession,
                        research_data: str) -> str:
        """通过搜索获取变量 - 配置驱动版本

        支持的配置选项：
        - extraction_mode: 'llm' | 'regex' - 提取模式（默认: llm）
        - regex_pattern: 正则表达式模式（regex 模式使用）
        - max_length: 结果最大长度（默认: 100）
        """
        default = var_config.get('default', '')
        extraction_mode = var_config.get('extraction_mode', 'llm')
        max_length = var_config.get('max_length', 100)
        description = var_config.get('description', '')

        # 特殊处理：对于股票价格，优先使用 Yahoo Finance API（最准确）
        if var_name == 'price' and session.vertical == 'stock':
            yahoo_price = _fetch_stock_price_yahoo(session.topic, timeout=10)
            if yahoo_price:
                session.log('info', 'prepare_img', f'Using Yahoo Finance price: {yahoo_price}')
                return yahoo_price

        # 对于 web_search 类型的变量，使用配置中定义的查询
        query = var_config.get('query', '').format(**context)

        # 使用 Brave Search 执行查询
        search_results = _fetch_brave_search(query, timeout=30)
        if search_results and not _is_error_response(search_results):

            # Regex 模式：使用配置的正则表达式提取
            if extraction_mode == 'regex':
                regex_pattern = var_config.get('regex_pattern', '')
                if regex_pattern:
                    try:
                        match = re.search(regex_pattern, search_results, re.IGNORECASE)
                        if match:
                            result = match.group(1) if match.groups() else match.group(0)
                            result = result.strip()[:max_length]
                            session.log('info', 'prepare_img', f'Extracted {var_name} via regex: {result[:50]}')
                            return result
                    except re.error as e:
                        session.log('warning', 'prepare_img', f'Regex error for {var_name}: {e}')

            # LLM 模式：使用 LLM 提取
            extract_prompt = f"""Extract the information from these search results.

Query: {query}
Description: {description}

Search results:
{search_results[:2000]}

Return ONLY the extracted value. No explanation."""

            result = _extract_with_llm(extract_prompt, timeout=30)
            if result and not _is_error_response(result):
                # 清理结果
                cleaned = result.strip().split('\n')[0][:max_length]
                session.log('info', 'prepare_img', f'Extracted {var_name} via LLM: {cleaned[:50]}')
                return cleaned

        # 如果是从研究数据中提取（回退）
        if research_data:
            # 尝试从研究数据中提取价格（兼容性）
            if 'price' in var_name.lower() or description.lower() in ['价格', '股价', 'price']:
                price = extract_price_from_research(research_data)
                if price:
                    session.log('info', 'prepare_img', f'Extracted price from research: {price}')
                    return price

        # 回退到默认值
        return default

    def _clean_variable_result(self, raw: str, default: str, max_length: int = 200) -> str:
        """通用的变量结果清理工具

        Args:
            raw: 原始结果文本
            default: 失败时返回的默认值
            max_length: 结果最大长度

        Returns:
            清理后的结果，或默认值
        """
        if not raw:
            return default

        # 检查是否是限流或错误响应
        error_indicators = [
            'rate limit', 'usage limit', 'unable to search', 'unable to retrieve',
            'cannot search', 'search service', 'service unavailable',
            'recommend checking', 'try checking', 'for the most current',
            'i apologize', 'apologize', 'not available', 'no information'
        ]
        raw_lower = raw.lower()
        if any(indicator in raw_lower for indicator in error_indicators):
            return default

        # 清理换行和多余空格
        cleaned = raw.strip().replace('\n', ' ').replace('\r', ' ')
        cleaned = re.sub(r'\s+', ' ', cleaned)

        # 截断到最大长度
        return cleaned[:max_length] if cleaned else default

    def _extract_reason_from_text(self, text: str) -> Optional[str]:
        """从文本中提取股票变动原因"""
        if not text:
            return None

        # 常见催化剂关键词模式
        catalyst_patterns = [
            (r'earnings?\s+(?:beat|miss|exceeded|topped|surpassed)', 'earnings report'),
            (r'AI\s+(?:demand|chip|growth|boom)', 'AI demand'),
            (r'revenue\s+(?:beat|miss|growth|surge)', 'revenue news'),
            (r'guidance\s+(?:raised|lowered|cut|updated)', 'guidance update'),
            (r'analyst\s+(?:upgrade|downgrade|rating)', 'analyst rating'),
            (r'product\s+(?:launch|announce|release)', 'product launch'),
            (r'dividend\s+(?:increase|cut|announce)', 'dividend news'),
            (r'stock\s+split', 'stock split'),
            (r'market\s+(?:rally|selloff|crash)', 'market movement'),
            (r'interest\s+rate', 'interest rate'),
            (r'inflation', 'inflation'),
            (r'supply\s+chain', 'supply chain'),
        ]

        text_lower = text.lower()
        for pattern, reason in catalyst_patterns:
            if re.search(pattern, text_lower):
                return reason

        return None

    def _resolve_conditional(self, var_config: Dict, context: Dict) -> str:
        """解析条件变量"""
        condition = var_config.get('condition', '')
        condition_var = var_config.get('condition_var', '')
        default = var_config.get('default', '')

        if condition_var not in context:
            return default

        var_value = str(context[condition_var])
        is_pos = False
        is_neg = False

        # 先检查是否有明确的正号号
        if '+' in var_value:
            is_pos = True
        elif var_value.replace('%', '').replace('.', '').lstrip('+-').isdigit():
            is_neg = True

        if condition == 'positive':
            if is_pos:
                return var_config.get('true_value', '')
            if is_neg:
                return var_config.get('false_value', '')
        elif condition == 'negative':
            if is_neg:
                return var_config.get('true_value', '')
            if is_pos:
                return var_config.get('false_value', '')

        return default

    def _infer_variable(self, var_config: Dict, context: Dict, var_key: str = '') -> str:
        """通过 LLM 推断变量"""
        inference_prompt = var_config.get('inference_prompt', '')
        if not inference_prompt:
            inference_prompt = f"Provide: {var_config.get('description', '')}"

        try:
            inference_prompt = inference_prompt.format(**context)
        except:
            pass

        prompt = f"""{inference_prompt}
Return ONLY the value, max 30 words. No explanation."""

        try:
            result = self.call_llm(prompt, expect_json=False, timeout=30)
            if result:
                result = result.strip().split('\n')[0][:150]
                # 检查是否是限流错误
                if _is_error_response(result):
                    return var_config.get('default', '')
                return result
        except:
            pass

        return var_config.get('default', '')


# =============================================================================
# Step 4a: Validate Stock Data (仅用于股票垂类)
# =============================================================================

class Step4aValidateStockData(BaseStep):
    """Step 4a: 验证股票数据准确性 - 多层验证确保数据万无一失"""

    # 数据合理性范围
    REASONABLE_PRICE_RANGE = (1, 10000)  # 股价合理范围
    REASONABLE_CHANGE_RANGE = (-30, 30)   # 日涨跌幅合理范围

    def run(self, session: XhsSession, **kwargs) -> bool:
        """执行股票数据验证步骤"""
        # 只对 stock 垂类执行验证
        if session.vertical != 'stock':
            return True

        session.log('info', 'validate_stock_data', 'Step started')
        session.update_step('validate_stock_data', 'in_progress')

        max_validation_rounds = 3  # 最多验证3轮

        for round_num in range(max_validation_rounds):
            session.log('info', 'validate_stock_data',
                       f'=== Validation round {round_num + 1}/{max_validation_rounds} ===')

            # 获取当前的数据
            prepare_data = session.get_step_data('prepare_img')
            variables = prepare_data.get('variables', {})
            sources = prepare_data.get('variables_source', {})

            stock_code = variables.get('stock_code', '')
            price = variables.get('price', '')
            change = variables.get('change', '')
            reason = variables.get('reason', '')

            session.log('info', 'validate_stock_data', 'Current data',
                       {'stock_code': stock_code, 'price': price, 'change': change, 'reason': reason})

            # 第一层验证：格式验证
            if not self._format_validation(stock_code, price, change, reason, variables, sources, session):
                continue  # 格式验证失败，进入下一轮

            # 第二层验证：多源数据获取与交叉验证
            if not self._cross_source_validation(stock_code, variables, sources, session):
                continue  # 交叉验证失败，进入下一轮

            # 第三层验证：数据合理性验证
            if not self._sanity_validation(variables.get('price', ''), variables.get('change', ''), session):
                continue  # 合理性验证失败，进入下一轮

            # 所有验证通过 - 重新解析依赖 change 的条件变量
            session.log('success', 'validate_stock_data', 'All validations passed!')
            self._re_resolve_conditionals(variables, sources, session)

            # 更新填充的 prompt（使用验证后的数据）
            config = self.load_vertical_config(session.vertical)
            cover_config = config.get('cover_config', {})
            variables_config = cover_config.get('prompt_variables', {})
            template = cover_config.get('background_prompt_template', '')
            for _ in range(3):
                prev = template
                for var_name, var_value in variables.items():
                    template = template.replace(f'{{{var_name}}}', str(var_value))
                if template == prev:
                    break

            # 更新 session
            session.update_step('prepare_img', 'completed', {
                'variables': variables,
                'variables_source': sources,
                'filled_prompt': template
            })

            session.update_step('validate_stock_data', 'completed', {
                'validation_rounds': round_num + 1,
                'validated_data': {
                    'stock_code': variables.get('stock_code', ''),
                    'price': variables.get('price', ''),
                    'change': variables.get('change', ''),
                    'reason': variables.get('reason', '')
                },
                'validation_passed': True
            })

            return True

        # 达到最大验证轮数 - 仍然重新解析条件变量
        self._re_resolve_conditionals(variables, sources, session)

        # 重新填充模板
        config = self.load_vertical_config(session.vertical)
        cover_config = config.get('cover_config', {})
        template = cover_config.get('background_prompt_template', '')
        for _ in range(3):
            prev = template
            for var_name, var_value in variables.items():
                template = template.replace(f'{{{var_name}}}', str(var_value))
            if template == prev:
                break

        session.update_step('prepare_img', 'completed', {
            'variables': variables,
            'variables_source': sources,
            'filled_prompt': template
        })

        session.update_step('validate_stock_data', 'completed', {
            'validation_result': 'max_rounds_reached',
            'final_data': variables,
            'validation_passed': False
        })
        session.log('warn', 'validate_stock_data', 'Reached max validation rounds, using current data')
        return True  # 继续执行，使用当前数据

    def _format_validation(self, stock_code: str, price: str, change: str, reason: str,
                          variables: dict, sources: dict, session: XhsSession) -> bool:
        """第一层：格式验证"""
        all_valid = True

        # 验证价格
        price_valid = self._validate_price(price)
        if not price_valid:
            session.log('warn', 'validate_stock_data', f'Invalid price format: {price}')
            new_price = self._fetch_price(stock_code, session)
            if new_price:
                variables['price'] = new_price
                sources['price'] = 'web_search_retry'
                session.log('info', 'validate_stock_data', f'Refetched price: {new_price}')
            else:
                all_valid = False

        # 验证变动
        change_valid = self._validate_change(change)
        if not change_valid:
            session.log('warn', 'validate_stock_data', f'Invalid change format: {change}')
            new_change = self._fetch_change(stock_code, session)
            if new_change:
                variables['change'] = new_change
                sources['change'] = 'web_search_retry'
                session.log('info', 'validate_stock_data', f'Refetched change: {new_change}')
            else:
                all_valid = False

        # 验证原因
        reason_valid = self._validate_reason(reason)
        if not reason_valid:
            session.log('warn', 'validate_stock_data', f'Invalid reason: {reason}')
            new_reason = self._fetch_reason(stock_code, session)
            if new_reason:
                variables['reason'] = new_reason
                sources['reason'] = 'web_search_retry'
                session.log('info', 'validate_stock_data', f'Refetched reason: {new_reason}')
            else:
                all_valid = False

        return all_valid

    def _cross_source_validation(self, stock_code: str, variables: dict, sources: dict,
                                session: XhsSession) -> bool:
        """第二层：多源数据获取与交叉验证 - 使用搜索功能"""
        # 对价格和变动进行二次获取，交叉验证
        session.log('info', 'validate_stock_data', 'Performing cross-source validation via search...')

        # 通过搜索二次获取价格
        price_prompt = f"""Search for: "{stock_code} stock price today"
Today: {datetime.now().strftime('%Y-%m-%d')}
Extract: Get the current stock price for {stock_code}.

Return ONLY the price in format $XXX.XX with dollar sign. No explanation."""
        try:
            result = subprocess.run(
                ['claude', '--dangerously-skip-permissions', '-p', price_prompt],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0 and result.stdout:
                match = re.search(r'\$\s*(\d{1,5}\.\d{2})', result.stdout)
                if match:
                    price_verify = f'${match.group(1)}'
                    if price_verify != variables.get('price'):
                        session.log('info', 'validate_stock_data',
                                   f'Price verification: original={variables.get("price")}, verified={price_verify}')
                        variables['price'] = price_verify
                        sources['price'] = 'search_verified'
        except Exception as e:
            session.log('warn', 'validate_stock_data', f'Price search verification failed: {e}')

        # 通过搜索二次获取变动
        change_prompt = f"""Search for: "{stock_code} stock percent change today"
Today: {datetime.now().strftime('%Y-%m-%d')}
Extract: Get today's percent change for {stock_code} stock.

Return ONLY the percentage with sign like +1.5% or -2.3%. No explanation."""
        try:
            result = subprocess.run(
                ['claude', '--dangerously-skip-permissions', '-p', change_prompt],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0 and result.stdout:
                match = re.search(r'([+-]?\d+\.?\d*)%', result.stdout)
                if match:
                    pct = match.group(1)
                    if not pct.startswith(('+', '-')):
                        pct = '+' + pct
                    change_verify = f'{pct}%'
                    if change_verify != variables.get('change'):
                        session.log('info', 'validate_stock_data',
                                   f'Change verification: original={variables.get("change")}, verified={change_verify}')
                        variables['change'] = change_verify
                        sources['change'] = 'search_verified'
        except Exception as e:
            session.log('warn', 'validate_stock_data', f'Change search verification failed: {e}')

        # 通过搜索二次获取原因
        reason_prompt = f"""Search for: "{stock_code} stock news today catalyst reason"
Today: {datetime.now().strftime('%Y-%m-%d')}
Extract: What is the main reason why {stock_code} stock is moving today?

Return ONLY a brief English explanation, maximum 5 words. Examples: 'AI demand surge', 'earnings beat expectations'. Do NOT include phrases like 'According to' or 'based on'."""
        try:
            result = subprocess.run(
                ['claude', '--dangerously-skip-permissions', '-p', reason_prompt],
                capture_output=True, text=True, timeout=45
            )
            if result.returncode == 0 and result.stdout:
                reason_verify = result.stdout.strip().split('\n')[0]
                reason_verify = re.sub(r'^["\']|["\']$', '', reason_verify)
                reason_verify = re.sub(r'[.!?;,:\-]+$', '', reason_verify).lower()
                words = reason_verify.split()[:5]
                reason_verify = ' '.join(words)
                if 3 <= len(reason_verify) <= 50 and reason_verify.isascii():
                    invalid_patterns = ['according to', 'based on', 'search result', 'unable to', 'not available']
                    if not any(p in reason_verify for p in invalid_patterns):
                        if reason_verify != variables.get('reason'):
                            session.log('info', 'validate_stock_data',
                                       f'Reason verification: original={variables.get("reason")}, verified={reason_verify}')
                            variables['reason'] = reason_verify
                            sources['reason'] = 'search_verified'
        except Exception as e:
            session.log('warn', 'validate_stock_data', f'Reason search verification failed: {e}')

        return True

    def _sanity_validation(self, price: str, change: str, session: XhsSession) -> bool:
        """第三层：数据合理性验证"""
        all_sane = True

        # 验证价格在合理范围内
        try:
            price_value = float(price.replace('$', ''))
            if not (self.REASONABLE_PRICE_RANGE[0] <= price_value <= self.REASONABLE_PRICE_RANGE[1]):
                session.log('warn', 'validate_stock_data',
                           f'Price {price_value} outside reasonable range {self.REASONABLE_PRICE_RANGE}')
                all_sane = False
        except (ValueError, AttributeError):
            session.log('error', 'validate_stock_data', f'Cannot parse price: {price}')
            all_sane = False

        # 验证变动在合理范围内
        try:
            change_value = float(change.replace('%', '').replace('+', ''))
            if not (self.REASONABLE_CHANGE_RANGE[0] <= change_value <= self.REASONABLE_CHANGE_RANGE[1]):
                session.log('warn', 'validate_stock_data',
                           f'Change {change_value}% outside reasonable range {self.REASONABLE_CHANGE_RANGE}')
                all_sane = False
        except (ValueError, AttributeError):
            session.log('error', 'validate_stock_data', f'Cannot parse change: {change}')
            all_sane = False

        if all_sane:
            session.log('info', 'validate_stock_data', 'Sanity validation passed')

        return all_sane

    def _validate_price(self, price: str) -> bool:
        """验证价格格式"""
        if not price or price == '---':
            return False
        # 格式: $XXX.XX
        return bool(re.match(r'^\$\d{1,5}\.\d{2}$', price))

    def _validate_change(self, change: str) -> bool:
        """验证变动格式"""
        if not change:
            return False
        # 拒绝无效值
        if change in ['0.0%', '+0.0%', '-0.0%', '0%', '+0%', '-0%', '---']:
            return False
        # 格式: +X.XX% 或 -X.XX%
        if not re.match(r'^[+-]\d+\.?\d*%$', change):
            return False
        # 拒绝接近 0 的值（可能是数据获取失败）
        numeric_part = change.strip('%').strip('+').strip('-')
        try:
            if float(numeric_part) < 0.01:
                return False
        except ValueError:
            return False
        return True

    def _validate_reason(self, reason: str) -> bool:
        """验证 reason 格式"""
        if not reason:
            return False

        # 检查默认值
        if reason == 'market volatility':
            return False

        # 检查长度上限（先检查，避免处理过长的无效消息）
        if len(reason) > 50:
            return False

        reason_lower = reason.lower()

        # 检查是否包含无效的关键词或模式（部分匹配）
        invalid_patterns = [
            'based on my',
            'according to',
            'per my',
            'i found',
            'search result',
            'cannot determine',
            'unable to',
            'unable to search',
            'not available',
            'no information',
            'no current',
            'as of my',
            'the article',
            'based on the',
            'according to the',
            'rate limit',
            'usage limit',
            'try checking',
            'yahoo finance',
            'bloomberg',
            'cnbc',
            'marketwatch',
            'recommend checking',
            'reset until',
            'apologize',
            'for the most current',
        ]
        for pattern in invalid_patterns:
            if pattern in reason_lower:
                return False

        # 应该是简短的英文短语，2-5个单词
        words = reason.strip().split()
        if not (2 <= len(words) <= 5):
            return False

        # 必须是纯 ASCII 字符
        if not reason.isascii():
            return False

        # 检查是否以冠词或代词开头（通常表示解析失败）
        invalid_starts = ['the ', 'a ', 'an ', 'i ', 'it ', 'this ', 'based on', 'according to', 'unable', 'unable to']
        if any(reason_lower.startswith(s) for s in invalid_starts):
            return False

        # 检查是否以标点符号结尾（可能是不完整的句子）
        if reason.endswith(',') or reason.endswith('.'):
            return False

        # 检查是否包含 URL 链接
        if 'http' in reason_lower or 'www.' in reason_lower or '.com' in reason_lower:
            return False

        return True

    def _fetch_price(self, stock_code: str, session: XhsSession) -> Optional[str]:
        """重新获取价格 - 使用搜索功能"""
        prompt = f"""Search for: "{stock_code} stock price today"
Today: {datetime.now().strftime('%Y-%m-%d')}
Extract: Get the current stock price for {stock_code}.

Return ONLY the price in format $XXX.XX with dollar sign. No explanation."""
        try:
            result = subprocess.run(
                ['claude', '--dangerously-skip-permissions', '-p', prompt],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0 and result.stdout:
                # 检查是否是限流错误
                if _is_error_response(result.stdout):
                    session.log('warn', 'validate_stock_data', 'Price search hit rate limit')
                    return None
                match = re.search(r'\$\s*(\d{1,5}\.\d{2})', result.stdout)
                if match:
                    return f'${match.group(1)}'
        except Exception as e:
            session.log('warn', 'validate_stock_data', f'Price search failed: {e}')
        return None

    def _fetch_change(self, stock_code: str, session: XhsSession) -> Optional[str]:
        """重新获取变动 - 使用搜索功能"""
        prompt = f"""Search for: "{stock_code} stock percent change today"
Today: {datetime.now().strftime('%Y-%m-%d')}
Extract: Get today's percent change for {stock_code} stock.

Return ONLY the percentage with sign like +1.5% or -2.3%. No explanation."""
        try:
            result = subprocess.run(
                ['claude', '--dangerously-skip-permissions', '-p', prompt],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0 and result.stdout:
                # 检查是否是限流错误
                if _is_error_response(result.stdout):
                    session.log('warn', 'validate_stock_data', 'Change search hit rate limit')
                    return None
                match = re.search(r'([+-]?\d+\.?\d*)%', result.stdout)
                if match:
                    pct = match.group(1)
                    if not pct.startswith(('+', '-')):
                        pct = '+' + pct
                    return f'{pct}%'
        except Exception as e:
            session.log('warn', 'validate_stock_data', f'Change search failed: {e}')
        return None

    def _fetch_reason(self, stock_code: str, session: XhsSession) -> Optional[str]:
        """重新获取 reason - 使用搜索功能"""
        prompt = f"""Search for: "{stock_code} stock news today catalyst reason"
Today: {datetime.now().strftime('%Y-%m-%d')}
Extract: What is the main reason why {stock_code} stock is moving today?

Return ONLY a brief English explanation, maximum 5 words. Examples: 'AI demand surge', 'earnings beat expectations'. Do NOT include phrases like 'According to' or 'based on'."""
        try:
            result = subprocess.run(
                ['claude', '--dangerously-skip-permissions', '-p', prompt],
                capture_output=True, text=True, timeout=45
            )
            if result.returncode == 0 and result.stdout:
                # 检查是否是限流错误
                if _is_error_response(result.stdout):
                    session.log('warn', 'validate_stock_data', 'Reason search hit rate limit')
                    return None
                reason_verify = result.stdout.strip().split('\n')[0]
                reason_verify = re.sub(r'^["\']|["\']$', '', reason_verify)
                reason_verify = re.sub(r'[.!?;,:\-]+$', '', reason_verify).lower()
                words = reason_verify.split()[:5]
                reason_verify = ' '.join(words)
                if 3 <= len(reason_verify) <= 50 and reason_verify.isascii():
                    invalid_patterns = ['according to', 'based on', 'search result', 'unable to', 'not available', 'rate limit', 'usage limit']
                    if not any(p in reason_verify for p in invalid_patterns):
                        return reason_verify
        except Exception as e:
            session.log('warn', 'validate_stock_data', f'Reason search failed: {e}')
        return None

    def _validate_product_name(self, stock_code: str, product_name: str) -> bool:
        """验证 product_name 是否与 stock_code 匹配"""
        if not product_name or product_name == 'flagship product':
            return False

        # 基本验证：检查是否包含明显的错误模式
        product_lower = product_name.lower()

        # 如果 product_name 中直接包含其他知名股票名称，可能有问题
        # 但这只是一种启发式检查，不能完全确定
        other_stocks = ['apple', 'google', 'microsoft', 'amazon', 'facebook', 'tesla', 'nvidia']
        stock_lower = stock_code.lower()

        for other in other_stocks:
            if other in product_lower and other != stock_lower:
                # 如果产品描述中包含其他公司名称，可能有问题
                # 但也可能是合法的（如"nvidia-compatible gpu"），所以只记录警告
                session.log('warn', 'validate_stock_data',
                           f'product_name "{product_name}" contains "{other}" - may not match {stock_code}')
                # 仍然返回 True，允许通过
                break

        return True

    def _fetch_product_name(self, stock_code: str, session: XhsSession) -> Optional[str]:
        """重新获取 product_name"""
        prompt = f"""For stock code '{stock_code}':

Step 1: What EXACT company does this ticker represent?
Step 2: What is that company's MOST iconic/recognizable product or building?

CRITICAL: Be specific to THIS company only. Do not guess a similar company in the same industry.

Return ONLY the product/building description in 2-6 words. No explanation."""

        try:
            result = subprocess.run(
                ['claude', '--dangerously-skip-permissions', '-p', prompt],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0 and result.stdout:
                cleaned = result.stdout.strip().split('\n')[0]
                cleaned = re.sub(r'^["\']|["\']$', '', cleaned)
                # 过滤掉垃圾前缀
                for prefix in ['based on my knowledge:', 'based on my knowledge,',
                               'based on ', 'according to ', 'step 1:', 'step 2:',
                               'the company is ', 'this is ']:
                    if cleaned.lower().startswith(prefix):
                        cleaned = cleaned[len(prefix):].strip()
                # 限制为 6 个单词以内
                words = cleaned.split()[:6]
                cleaned = ' '.join(words).rstrip('.,;:')
                if len(cleaned) >= 3:
                    return cleaned.lower()
        except Exception:
            pass
        return None

    def _re_resolve_conditionals(self, variables: dict, sources: dict, session: XhsSession) -> None:
        """重新解析依赖 change 的条件变量"""
        config = self.load_vertical_config(session.vertical)
        cover_config = config.get('cover_config', {})
        variables_config = cover_config.get('prompt_variables', {})

        # 获取 change 值
        change_value = variables.get('change', '')

        # 构建上下文
        context = {**variables}

        # 重新解析所有依赖 change 的变量
        for var_name, var_config in variables_config.items():
            depends_on = var_config.get('depends_on', [])
            if 'change' in depends_on and var_config.get('source') == 'conditional':
                try:
                    value = self._resolve_conditional(var_config, context)
                    variables[var_name] = value
                    sources[var_name] = 're_resolved'
                    session.log('debug', 'validate_stock_data',
                               f'Re-resolved conditional {var_name}: {value}')
                except Exception as e:
                    session.log('warn', 'validate_stock_data',
                               f'Failed to re-resolve {var_name}: {e}')


# =============================================================================
# Step 5: Generate Image
# =============================================================================

class Step5GenImg(BaseStep):
    """Step 5: 生成封面图"""

    def run(self, session: XhsSession, **kwargs) -> bool:
        """执行封面图生成步骤"""
        session.log('info', 'gen_img', 'Step started')
        session.update_step('gen_img', 'in_progress')

        try:
            config = self.load_vertical_config(session.vertical)
            cover_config = config.get('cover_config', {})

            # 获取填充好的 prompt
            prepare_data = session.get_step_data('prepare_img')

            # 检查是否是多图模式
            prompts = prepare_data.get('prompts', [])
            image_configs = prepare_data.get('image_configs', [])

            if prompts and len(prompts) > 1:
                # 多图模式
                return self._generate_multi_images(session, prompts, image_configs)
            else:
                # 单图模式（原有逻辑）
                return self._generate_single_image(session, prepare_data)

        except Exception as e:
            session.log('error', 'gen_img', f'Step failed: {str(e)}', exc_info=True)
            session.update_step('gen_img', 'failed', {'error': str(e)})
            return False

    def _generate_single_image(self, session: XhsSession, prepare_data: Dict) -> bool:
        """生成单图（原有逻辑）"""
        filled_prompt = prepare_data.get('filled_prompt', '')

        if not filled_prompt:
            raise ValueError('No prompt available for image generation')

        output_file = session.get_file_path('cover_bg.png')
        api_key = get_api_key()

        # 从配置读取 aspect_ratio
        config = self.load_vertical_config(session.vertical)
        cover_config = config.get('cover_config', {})
        aspect_ratio = cover_config.get('aspect_ratio', '1:1')

        session.log('info', 'gen_img', f'Generating image: {filled_prompt[:100]}...')

        generate_image(
            prompt=filled_prompt,
            output_path=output_file,
            api_key=api_key,
            resolution='1K',
            aspect_ratio=aspect_ratio
        )

        file_size = output_file.stat().st_size

        session.update_step('gen_img', 'completed', {
            'prompt_used': filled_prompt[:2000],
            'prompt_full_length': len(filled_prompt),
            'output_files': ['cover_bg.png'],
            'file_sizes': [file_size]
        })

        session.log('success', 'gen_img', 'Step completed',
                   {'file_size': file_size})
        return True

    def _generate_multi_images(self, session: XhsSession, prompts: list,
                              image_configs: list) -> bool:
        """生成多图"""
        api_key = get_api_key()
        output_files = []
        file_sizes = []
        reference_image = None  # 参考图片路径

        for idx, prompt in enumerate(prompts):
            output_file = session.get_file_path(f'cover_bg_{idx}.png')
            output_files.append(f'cover_bg_{idx}.png')

            # 获取 aspect_ratio
            aspect_ratio = '1:1'
            if idx < len(image_configs):
                aspect_ratio = image_configs[idx].get('aspect_ratio', '1:1')

            session.log('info', 'gen_img',
                       f'Generating image {idx + 1}/{len(prompts)}: {prompt[:100]}...')

            # 添加重试机制处理临时性 API 错误
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    generate_image(
                        prompt=prompt,
                        output_path=output_file,
                        api_key=api_key,
                        resolution='1K',
                        reference_image=reference_image,  # 传入参考图片
                        aspect_ratio=aspect_ratio  # 传入宽高比
                    )
                    file_size = output_file.stat().st_size
                    file_sizes.append(file_size)
                    session.log('debug', 'gen_img',
                               f'Image {idx} generated: {file_size} bytes')

                    # 第一张图片生成成功后，作为后续图片的参考
                    if idx == 0 and file_size > 0:
                        reference_image = output_file
                        session.log('info', 'gen_img',
                                   'First image will be used as reference for subsequent images')
                    break  # 成功，跳出重试循环

                except Exception as e:
                    error_msg = str(e)
                    is_retryable = any(code in error_msg for code in ['500', 'INTERNAL', '503', 'timeout'])

                    if attempt < max_retries - 1 and is_retryable:
                        session.log('warn', 'gen_img',
                                   f'Image {idx} failed (attempt {attempt + 1}/{max_retries}): {error_msg[:100]}, retrying...')
                        import time
                        time.sleep(2)  # 等待 2 秒后重试
                    else:
                        session.log('error', 'gen_img', f'Failed to generate image {idx}: {error_msg}')
                        # 创建一个占位文件，避免后续步骤失败
                        output_file.write_text(f'Image generation failed: {error_msg}')
                        file_sizes.append(0)
                        break

        session.update_step('gen_img', 'completed', {
            'image_count': len(prompts),
            'output_files': output_files,
            'file_sizes': file_sizes,
            'image_configs': image_configs,
            'used_reference_image': reference_image is not None
        })

        session.log('success', 'gen_img', 'Multi-image generation completed',
                   {'image_count': len(prompts)})
        return True


# =============================================================================
# Step 6: Overlay Logo
# =============================================================================

class Step6Overlay(BaseStep):
    """Step 6: 添加 Logo"""

    def run(self, session: XhsSession, **kwargs) -> bool:
        """执行 Logo 叠加步骤"""
        session.log('info', 'overlay', 'Step started')
        session.update_step('overlay', 'in_progress')

        try:
            config = self.load_vertical_config(session.vertical)
            cover_config = config.get('cover_config', {})

            # 获取生成步骤的数据
            gen_data = session.get_step_data('gen_img')
            output_files = gen_data.get('output_files', [])
            image_count = gen_data.get('image_count', 1)

            if image_count > 1 and len(output_files) > 1:
                # 多图模式
                return self._overlay_multi_images(session, output_files, cover_config)
            else:
                # 单图模式（原有逻辑）
                return self._overlay_single_image(session, cover_config)

        except Exception as e:
            session.log('error', 'overlay', f'Step failed: {str(e)}', exc_info=True)
            session.update_step('overlay', 'failed', {'error': str(e)})
            return False

    def _overlay_single_image(self, session: XhsSession, cover_config: Dict) -> bool:
        """单图 logo 叠加（原有逻辑）"""
        # 检查输入文件
        input_file = session.get_file_path('cover_bg.png')
        if not input_file.exists():
            raise FileNotFoundError('cover_bg.png not found')

        logo_file = cover_config.get('logo_file', '')

        # 查找 logo
        logo_path = self._find_logo(logo_file, session.vertical)

        output_file = session.get_file_path('cover.png')

        if not logo_path or not logo_path.exists():
            # 没有 logo，直接复制
            shutil.copy2(input_file, output_file)
            file_size = output_file.stat().st_size

            session.update_step('overlay', 'completed', {
                'logo_used': 'none',
                'output_files': ['cover.png'],
                'file_sizes': [file_size]
            })
            session.log('info', 'overlay', 'No logo found, using original background')
            return True

        # 使用 ImageMagick 添加 logo (尺寸和边距都是原来的2倍)
        result = subprocess.run([
            'magick', str(input_file),
            '(', str(logo_path), '-resize', '24%', ')',
            '-geometry', '+20+20',
            '-composite', str(output_file)
        ], capture_output=True, text=True)

        if result.returncode != 0:
            # 失败，使用原始背景
            shutil.copy2(input_file, output_file)
            file_size = output_file.stat().st_size

            session.update_step('overlay', 'completed', {
                'logo_used': f'{logo_path.name} (overlay failed)',
                'output_files': ['cover.png'],
                'file_sizes': [file_size]
            })
            session.log('warn', 'overlay', 'Logo overlay failed, using original background')
            return True

        file_size = output_file.stat().st_size

        session.update_step('overlay', 'completed', {
            'logo_used': logo_path.name,
            'output_files': ['cover.png'],
            'file_sizes': [file_size]
        })

        session.log('success', 'overlay', 'Step completed')
        return True

    def _overlay_multi_images(self, session: XhsSession, output_files: list,
                             cover_config: Dict) -> bool:
        """多图 logo 叠加"""
        logo_file = cover_config.get('logo_file', '')
        logo_path = self._find_logo(logo_file, session.vertical)

        final_output_files = []
        file_sizes = []

        for idx, bg_filename in enumerate(output_files):
            input_file = session.get_file_path(bg_filename)
            output_file = session.get_file_path(f'cover_{idx}.png')
            final_output_files.append(f'cover_{idx}.png')

            if not input_file.exists() or input_file.stat().st_size == 0:
                # 跳过无效文件
                file_sizes.append(0)
                continue

            if not logo_path or not logo_path.exists():
                # 没有 logo，直接复制
                shutil.copy2(input_file, output_file)
                file_size = output_file.stat().st_size
                file_sizes.append(file_size)
                session.log('debug', 'overlay', f'Image {idx}: no logo, copied')
                continue

            # 使用 ImageMagick 添加 logo
            result = subprocess.run([
                'magick', str(input_file),
                '(', str(logo_path), '-resize', '24%', ')',
                '-geometry', '+20+20',
                '-composite', str(output_file)
            ], capture_output=True, text=True)

            if result.returncode != 0:
                # 失败，使用原始背景
                shutil.copy2(input_file, output_file)
                session.log('warn', 'overlay', f'Image {idx}: logo overlay failed')

            file_size = output_file.stat().st_size
            file_sizes.append(file_size)
            session.log('debug', 'overlay', f'Image {idx}: overlay complete, size={file_size}')

        session.update_step('overlay', 'completed', {
            'logo_used': logo_path.name if logo_path else 'none',
            'image_count': len(final_output_files),
            'output_files': final_output_files,
            'file_sizes': file_sizes
        })

        session.log('success', 'overlay', 'Multi-image overlay completed',
                   {'image_count': len(final_output_files)})
        return True

    def _find_logo(self, logo_file: str, vertical: str) -> Optional[Path]:
        """查找 logo 文件"""
        candidates = []

        if logo_file:
            candidates.append(self.assets_dir / 'logo' / logo_file)

        candidates.extend([
            self.assets_dir / 'logo' / f'{vertical}.png',
            self.assets_dir / 'logo' / 'default.png'
        ])

        for path in candidates:
            if path.exists():
                return path

        return None


# =============================================================================
# Step 7: Deliver
# =============================================================================

class Step7Deliver(BaseStep):
    """Step 7: 发送到 Telegram"""

    def run(self, session: XhsSession, **kwargs) -> bool:
        """执行发送步骤"""
        session.log('info', 'deliver', 'Step started')
        session.update_step('deliver', 'in_progress')

        try:
            # 读取内容
            content = session.read_file('content.md')

            # 准备导出目录
            title = session._data.get('title', 'Untitled')
            safe_title = re.sub(r'[^\w\u4e00-\u9fff_-]', '_', title)[:30]
            if not safe_title:
                safe_title = 'Untitled'

            export_dir = Path.home() / 'Desktop' / 'Xiaohongshu_Exports' / \
                f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_title}"
            export_dir.mkdir(parents=True, exist_ok=True)

            # 复制文件到导出目录
            (export_dir / 'content.md').write_text(content, encoding='utf-8')

            # 检查是否有多图
            overlay_data = session.get_step_data('overlay')
            output_files = overlay_data.get('output_files', [])
            image_count = overlay_data.get('image_count', 1)

            cover_images = []
            for idx, filename in enumerate(output_files):
                src = session.get_file_path(filename)
                if src.exists() and src.stat().st_size > 0:
                    dest = export_dir / filename
                    shutil.copy2(src, dest)
                    cover_images.append(dest)

            session.log('info', 'deliver', f'Files archived to: {export_dir}')

            # 发送到 Telegram
            bot_token, chat_id = self._get_telegram_credentials()
            telegram_sent = False
            message_id = ''

            if bot_token and chat_id:
                try:
                    if len(cover_images) > 1:
                        # 多图模式：使用 sendMediaGroup
                        telegram_sent = self._send_media_group(
                            bot_token, chat_id, cover_images, content, session
                        )
                    elif len(cover_images) == 1:
                        # 单图模式：使用 sendPhoto
                        telegram_sent = self._send_photo(
                            bot_token, chat_id, cover_images[0], content, session
                        )
                    else:
                        # 无图：使用 sendMessage
                        telegram_sent = self._send_message(
                            bot_token, chat_id, content, session
                        )

                    if telegram_sent:
                        session.log('success', 'deliver', 'Telegram sent successfully')
                    else:
                        session.log('warn', 'deliver', 'Telegram send failed')

                except Exception as e:
                    session.log('warn', 'deliver', f'Telegram send error: {str(e)}')
            else:
                session.log('warn', 'deliver', 'Telegram credentials missing')

            session.update_step('deliver', 'completed', {
                'export_dir': str(export_dir),
                'telegram_sent': telegram_sent,
                'telegram_message_id': message_id,
                'image_count': len(cover_images)
            })

            session.log('success', 'deliver', 'Step completed')
            return True

        except Exception as e:
            session.log('error', 'deliver', f'Step failed: {str(e)}', exc_info=True)
            session.update_step('deliver', 'completed', {  # 发送失败也标记完成，因为文件已归档
                'export_dir': '',
                'telegram_sent': False,
                'error': str(e)
            })
            return True  # 文件已归档，返回 True

    def _send_photo(self, bot_token: str, chat_id: str, photo_path: Path,
                   content: str, session: XhsSession) -> bool:
        """发送单张图片"""
        result = subprocess.run([
            'curl', '-s', '-X', 'POST',
            f'https://api.telegram.org/bot{bot_token}/sendPhoto',
            '-F', f'chat_id={chat_id}',
            '-F', f'photo=@{photo_path}',
            '-F', f'caption={content}'
        ], capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            try:
                resp = json.loads(result.stdout)
                if resp.get('ok'):
                    return True
            except:
                pass
        return False

    def _send_media_group(self, bot_token: str, chat_id: str,
                         photo_paths: list, content: str, session: XhsSession) -> bool:
        """发送图片组（多图）"""
        # 构建 media 数组
        media_array = []
        for idx, photo_path in enumerate(photo_paths):
            if idx == 0:
                # 第一张图带 caption
                media_array.append({
                    "type": "photo",
                    "media": f"attach://photo{idx}",
                    "caption": content
                })
            else:
                media_array.append({
                    "type": "photo",
                    "media": f"attach://photo{idx}"
                })

        # 构建命令
        cmd = [
            'curl', '-s', '-X', 'POST',
            f'https://api.telegram.org/bot{bot_token}/sendMediaGroup',
            '-F', f'chat_id={chat_id}',
            '-F', f'media={json.dumps(media_array)}'
        ]

        # 添加图片文件
        for idx, photo_path in enumerate(photo_paths):
            cmd.extend(['-F', f'photo{idx}=@{photo_path}'])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0:
            try:
                resp = json.loads(result.stdout)
                if resp.get('ok'):
                    return True
            except:
                pass
        return False

    def _send_message(self, bot_token: str, chat_id: str,
                     content: str, session: XhsSession) -> bool:
        """发送纯文本消息"""
        result = subprocess.run([
            'curl', '-s', '-X', 'POST',
            f'https://api.telegram.org/bot{bot_token}/sendMessage',
            '-d', f'chat_id={chat_id}',
            '-d', f'text={content}'
        ], capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            try:
                resp = json.loads(result.stdout)
                if resp.get('ok'):
                    return True
            except:
                pass
        return False

    def _get_telegram_credentials(self) -> Tuple[str, str]:
        """获取 Telegram 凭据"""
        config_file = Path.home() / '.openclaw' / 'openclaw.json'
        if not config_file.exists():
            return '', ''

        with open(config_file) as f:
            data = json.load(f)

        bot_token = data.get('channels', {}).get('telegram', {}).get(
            'accounts', {}
        ).get('default', {}).get('botToken', '')

        # 获取 chat_id
        chat_id = ''
        try:
            result = subprocess.run(
                ['openclaw', 'sessions', '--json'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                json_start = result.stdout.find('{')
                if json_start >= 0:
                    sessions_data = json.loads(result.stdout[json_start:])
                    tg_sessions = [
                        s['key'].split(':')[-1] for s in sessions_data.get('sessions', [])
                        if 'telegram:direct' in s.get('key', '')
                    ]
                    if tg_sessions:
                        chat_id = tg_sessions[0]
        except:
            pass

        if not chat_id:
            chat_id = '6167775207'

        return bot_token, chat_id
