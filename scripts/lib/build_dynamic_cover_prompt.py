#!/usr/bin/env python3
"""
Dynamic Cover Prompt Generator
泛化的动态封面 Prompt 生成器

支持通过 LLM + 搜索来获取变量值，填充模板生成生图 Prompt
"""

import json
import re
import sys
import subprocess
from datetime import datetime

# 全局缓存，用于存储股票行情数据，确保 price 和 change 来自同一数据源
_stock_data_cache = {}


def call_llm(prompt):
    """调用 LLM"""
    try:
        result = subprocess.run(
            ['claude', '--dangerously-skip-permissions', '-p', prompt],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception as e:
        return None


def get_stock_quote_data(stock_code):
    """一次性获取股票的所有行情数据，确保数据一致性"""
    # 检查缓存
    if stock_code in _stock_data_cache:
        return _stock_data_cache[stock_code]

    # 使用 search_variable 分别获取价格和涨跌幅
    price_config = {
        'source': 'web_search',
        'query': f'{stock_code} stock price today',
        'default': '---',
        'description': 'The current stock price. Return ONLY the price with $ sign like $150.25.'
    }

    change_config = {
        'source': 'web_search',
        'query': f'{stock_code} stock percent change today',
        'default': '0.0%',
        'description': 'Today\'s percent change. Return ONLY the percentage with sign like +1.5% or -2.3%.'
    }

    # 创建临时 context
    context = {'topic': stock_code, 'vertical': 'stock'}

    # 获取价格和涨跌幅
    price = search_variable(price_config, context)
    change = search_variable(change_config, context)

    # 尝试从 change 结果中提取前收盘价
    prev_close = None
    if change != '0.0%' and change != price_config['default']:
        # 涨跌幅格式正确，但可能需要前收盘价来验证
        pass

    # 如果涨跌幅为默认值，尝试从价格结果中提取前收盘价并计算
    if change == '0.0%' and price != '---':
        # 可能需要重新搜索获取前收盘价
        prev_config = {
            'source': 'web_search',
            'query': f'{stock_code} stock previous close price',
            'default': None,
            'description': 'The previous close price. Return ONLY the price with $ sign.'
        }
        prev_result = call_llm(f"""Search for '{stock_code} stock previous close' and return the price in format $XXX.XX""")
        if prev_result:
            prev_match = re.search(r'\$\s*(\d{1,5}[\.,]\d{2})', prev_result, re.IGNORECASE)
            if prev_match:
                try:
                    prev_close = float(prev_match.group(1).replace(',', '.'))
                    # 计算涨跌幅
                    current_price = float(price.replace('$', '').replace(',', '.'))
                    change_pct = ((current_price - prev_close) / prev_close) * 100
                    change = f"{change_pct:+.2f}%"
                except (ValueError, ZeroDivisionError):
                    pass

    data = {
        'price': price if price != '---' else '---',
        'change': change,
        'previous_close': prev_close
    }

    # 缓存结果
    _stock_data_cache[stock_code] = data
    return data


def extract_from_topic(variable_config, topic, vertical):
    """从话题中提取变量值"""
    extract_type = variable_config.get('extract', 'regex')
    pattern = variable_config.get('pattern', '')

    if extract_type == 'regex' and pattern:
        match = re.search(pattern, topic, re.IGNORECASE)
        if match:
            return match.group(1) if match.groups() else match.group(0)

    # 默认：提取大写字母组合作为代码
    if extract_type == 'code':
        # 先将话题中非ASCII字符全部移除，只留英文字母和数字
        ascii_only = re.sub(r'[^A-Za-z0-9]', ' ', topic)

        # 优先提取完整的股票代码模式：1-5个大写字母开头，可能跟数字
        # 使用更精确的模式匹配股票代码（常见的1-5个字母）
        code_match = re.search(r'\b([A-Z]{1,5})\b', ascii_only.upper())
        if code_match:
            return code_match.group(1)

        # 回退：查找所有大写字母组合
        codes = re.findall(r'[A-Z]{2,5}', ascii_only.upper())
        if codes:
            # 返回最像股票代码的（最长的大写字母组合）
            return max(codes, key=len)

    return topic[:10]  # 回退：取话题前10个字符


def search_variable(variable_config, context):
    """通过带有搜索功能的 LLM 获取变量值"""
    query_template = variable_config.get('query', '')
    query = query_template.format(**context)
    description = variable_config.get('description', '')

    # 获取当前日期，确保搜索最新数据
    today = datetime.now().strftime('%Y-%m-%d')

    # 直接使用有搜索能力的 Claude 获取并提取答案
    llm_prompt = f"""Search the live web for the following query: '{query}'

IMPORTANT: Today's date is {today}. Make sure you get the MOST RECENT data from today ({today}).

Based on the live search results, extract exactly the value for: {description}

CRITICAL RULES:
- Return ONLY the extracted value, nothing else.
- Maximum 30 words for reasons, 10 words for other values.
- No source links, no reasoning, no markdown, no extra text.
- If it is a price, format as $XXX.XX
- If it is a percentage (percent change): You MUST find BOTH the current price AND previous close, then CALCULATE: ((current - previous) / previous) * 100. Return format like +1.5% or -2.3% with sign.
- If it is a reason (原因), use exactly 20-30 Chinese characters or 12-18 English words to summarize today's stock price movement catalyst. Be specific and detailed."""

    result = call_llm(llm_prompt)

    # 强制清理：截断过长回复，防止污染生图 prompt
    if result:
        # 检查是否是无效结果（包含"未找到"、"not found"、"无法获取"等）
        invalid_patterns = [
            r'未找到', r'找不到', r'无法获取', r'not found', r'unable to find',
            r'could not find', r'no data', r'搜索结果主要显示', r'请提供具体日期'
        ]
        for pattern in invalid_patterns:
            if re.search(pattern, result, re.IGNORECASE):
                # 使用默认值，而不是无效的搜索结果
                return variable_config.get('default', '市场波动')

        # 如果有提取模式，优先使用正则匹配提取
        extract_pattern = variable_config.get('extract_pattern', '')
        if extract_pattern:
            match = re.search(extract_pattern, result, re.IGNORECASE)
            if match:
                result = match.group(1) if match.groups() else match.group(0)

        # 移除常见的废话开头（多级清理）
        preambles = [
            "Based on the search results", "I found that", "According to",
            "As of", "The extracted value is", "The current value is",
            "根据搜索结果", "我发现", "当前的", "提取的结果是",
            "The percentage change is", "The change is", "Today's change is"
        ]
        for preamble in preambles:
            if preamble.lower() in result.lower()[:50]:
                # 尝试用正则移除前缀直到第一个冒号或逗号之后
                result = re.sub(rf"^{preamble}.*?[:：,，]\s*", "", result, flags=re.IGNORECASE)

        # 再次尝试：如果还是太长且包含 "is"，可能是一个完整的句子，尝试提取 "is" 之后的内容
        if len(result) > 30 and " is " in result:
             result = result.split(" is ")[-1]

        # 特殊处理：如果是原因类型，截断到较长的中文描述
        if "reason" in description.lower() or "原因" in description:
            # 检查是中文还是英文内容
            chinese_chars = re.findall(r'[\u4e00-\u9fff]', result)
            if chinese_chars and len(chinese_chars) > 10:
                # 主要是中文内容
                # 找到合适的截断点（在标点符号处）
                best_pos = len(result)
                for i in range(len(result) - 1, -1, -1):
                    char = result[i]
                    if char in '。！？，、；：':
                        # 检查这个位置之前的中文字符数
                        chars_before = re.findall(r'[\u4e00-\u9fff]', result[:i+1])
                        if 20 <= len(chars_before) <= 35:  # 理想范围
                            best_pos = i + 1
                            break
                result = result[:best_pos]
            else:
                # 主要是英文内容，取前15个单词
                words = result.split()
                if len(words) > 15:
                    result = ' '.join(words[:15])

        # 特殊处理：如果是百分比类型，强制提取百分比格式并四舍五入
        elif "percentage" in description.lower() or "percent change" in description.lower():
            # 优先查找百分比模式
            percent_match = re.search(r'[+-]?\d+\.?\d*%', result)
            if percent_match:
                percent_str = percent_match.group(0)
                # 提取数字并四舍五入到2位小数
                num_match = re.search(r'[+-]?\d+\.?\d*', percent_str)
                if num_match:
                    num = float(num_match.group(0))
                    result = f"{num:+.2f}%"
                else:
                    result = percent_str
            else:
                # 尝试提取数字并添加 %
                num_match = re.search(r'[+-]?\d+\.?\d*', result)
                if num_match:
                    num = float(num_match.group(0))
                    # 如果是美元值（大于100），可能需要转换
                    # 但由于无法准确知道股价，我们直接返回带 % 的格式
                    # 如果数字很小（小于10），直接添加%
                    if abs(num) < 10:
                        result = f"{num:+.2f}%"
                    else:
                        # 大数字可能是美元值，无法准确转换，返回默认值
                        result = variable_config.get('default', '0.0%')

        # 如果是价格，确保有 $ 符号且格式正确
        elif "price" in description.lower() or ("$" in result and "%" not in result):
            # 尝试提取数字和 $ 符号
            price_match = re.search(r'\$?(\d+[\.,]\d{2})', result)
            if price_match:
                result = f"${price_match.group(1).replace(',', '.')}"

        # 只取第一行，并硬截断到150字符（支持更长的 AI Note）
        result = result.split('\n')[0].strip()
        if len(result) > 150:
            result = result[:150]

    # 如果结果为空或无效，返回默认值
    if not result or len(result) < 2:
        return variable_config.get('default', '市场波动')

    return result


def infer_variable(variable_config, context):
    """通过 LLM 推断变量值"""
    inference_prompt = variable_config.get('inference_prompt', '')
    if not inference_prompt:
        inference_prompt = f"Based on the context, provide: {variable_config.get('description', '')}"

    # 关键：用 context 替换 prompt 中的变量占位符（如 {stock_code}）
    try:
        inference_prompt = inference_prompt.format(**context)
    except KeyError:
        pass  # 如果有些变量还未解析则跳过

    full_prompt = f"""{inference_prompt}

CRITICAL: Return ONLY the requested value in max 30 words. No explanation, no preamble, no markdown."""
    result = call_llm(full_prompt)

    # 截断保护，和 search_variable 一样
    if result:
        result = result.split('\n')[0].strip()
        if len(result) > 150:
            result = result[:150]
    
    return result


def get_variable_value(var_name, var_config, context):
    """获取单个变量的值"""
    source = var_config.get('source', 'literal')
    default = var_config.get('default', '')
    vertical = context.get('vertical', '')
    topic = context.get('topic', '')

    # 特殊处理：stock vertical 的 price 和 change 使用统一的数据源
    if vertical == 'stock' and var_name in ['price', 'change']:
        stock_code = context.get('stock_code', topic)
        stock_data = get_stock_quote_data(stock_code)
        if var_name == 'price':
            return stock_data.get('price', default)
        elif var_name == 'change':
            return stock_data.get('change', default)

    # 1. 字面值
    if source == 'literal':
        return var_config.get('value', '')

    # 2. 从话题提取
    if source == 'extract_from_topic':
        return extract_from_topic(var_config, topic, vertical)

    # 3. 网络搜索
    if source == 'web_search':
        value = search_variable(var_config, context)
        return value if value else default

    # 4. LLM 推断
    if source == 'llm_inference':
        value = infer_variable(var_config, context)
        return value if value else default

    # 5. 日期时间
    if source == 'date':
        format_str = var_config.get('format', '%b %d')
        return datetime.now().strftime(format_str).upper()

    # 6. 条件判断
    if source == 'conditional':
        condition = var_config.get('condition', '')
        condition_var = var_config.get('condition_var', '')
        if condition_var in context:
            var_value = str(context[condition_var])
            clean_val = var_value.replace('%', '').replace(',', '').replace('$', '').replace('¥', '').strip()

            is_pos = '+' in var_value
            is_neg = '-' in var_value

            try:
                num = float(clean_val)
                if num > 0: is_pos = True
                if num < 0: is_neg = True
            except ValueError:
                pass

            if condition == 'positive':
                if is_pos:
                    return var_config.get('true_value', '')
                elif is_neg:
                    return var_config.get('false_value', '')
            elif condition == 'negative':
                if is_neg:
                    return var_config.get('true_value', '')
                elif is_pos:
                    return var_config.get('false_value', '')

        return var_config.get('default', '')

    return default


def resolve_variables(variables_config, context):
    """解析所有变量"""
    resolved = {}
    max_iterations = 5  # 防止循环依赖

    for iteration in range(max_iterations):
        updated = False
        for var_name, var_config in variables_config.items():
            if var_name in resolved:
                continue

            # 检查依赖是否都已解析
            depends_on = var_config.get('depends_on', [])
            if all(dep in resolved for dep in depends_on):
                # 更新 context，包含已解析的变量
                update_context = {**context, **resolved}
                value = get_variable_value(var_name, var_config, update_context)
                if value is not None:
                    resolved[var_name] = value
                    updated = True

        if not updated:
            break  # 没有更新，退出循环

    return resolved


def fill_template(template, variables):
    """填充模板，支持变量值中包含占位符的情况"""
    result = template
    # 多轮替换，处理变量值中包含占位符的情况
    for _ in range(3):
        prev_result = result
        for var_name, var_value in variables.items():
            placeholder = f"{{{var_name}}}"
            result = result.replace(placeholder, str(var_value))
        # 如果没有变化，提前退出
        if result == prev_result:
            break
    return result


def main():
    if len(sys.argv) < 4:
        print("Usage: build_dynamic_cover_prompt.py <vertical_config> <topic> <vertical>", file=sys.stderr)
        sys.exit(1)

    config_path = sys.argv[1]
    topic = sys.argv[2]
    vertical = sys.argv[3]

    # 读取垂类配置
    with open(config_path, 'r') as f:
        config = json.load(f)

    cover_config = config.get('cover_config', {})
    template = cover_config.get('background_prompt_template', '')
    variables_config = cover_config.get('prompt_variables', {})

    if not template:
        print("错误: 未找到 background_prompt_template", file=sys.stderr)
        sys.exit(1)

    # 如果没有定义变量，直接返回模板
    if not variables_config:
        print(template, end='')
        return

    # 初始上下文
    context = {
        'topic': topic,
        'vertical': vertical,
        'date': datetime.now().strftime('%b %d').upper()
    }

    # 对于 stock vertical，预先解析 stock_code 并添加到 context
    if vertical == 'stock' and 'stock_code' in variables_config:
        stock_code_config = variables_config['stock_code']
        stock_code = get_variable_value('stock_code', stock_code_config, context)
        context['stock_code'] = stock_code

    # 解析所有变量
    print(f"# 解析 {len(variables_config)} 个变量...", file=sys.stderr)
    resolved = resolve_variables(variables_config, context)

    for var_name, var_value in resolved.items():
        print(f"#  {var_name} = {var_value}", file=sys.stderr)

    # 填充模板
    final_prompt = fill_template(template, resolved)

    print("", file=sys.stderr)
    print("# Prompt 生成完成", file=sys.stderr)
    print(final_prompt, end='')


if __name__ == '__main__':
    main()
