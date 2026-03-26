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
        codes = re.findall(r'[A-Z]{1,5}', ascii_only.upper())
        if codes:
            # 返回最像股票代码的（最长的大写字母组合）
            return max(codes, key=len)

    return topic[:10]  # 回退：取话题前10个字符


def search_variable(variable_config, context):
    """通过带有搜索功能的 LLM 获取变量值"""
    query_template = variable_config.get('query', '')
    query = query_template.format(**context)
    description = variable_config.get('description', '')

    # 直接使用有搜索能力的 Claude 获取并提取答案
    llm_prompt = f"""Search the live web for the following query: '{query}'

Based on the live search results, extract exactly the value for: {description}

CRITICAL RULES:
- Return ONLY the extracted value, nothing else.
- Maximum 10 words.
- No source links, no reasoning, no markdown, no extra text.
- If it is a price, format as $XXX.XX
- If it is a percentage, format as +X.X% or -X.X% (MUST include % sign)
- If it is a reason, use max 5 English words or max 8 Chinese characters."""

    result = call_llm(llm_prompt)

    # 强制清理：截断过长回复，防止污染生图 prompt
    if result:
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

        # 特殊处理：如果是原因类型，截断到简短中文
        if "reason" in description.lower() or "原因" in description:
            # 提取前8个中文字符或前5个英文单词
            chinese_chars = re.findall(r'[\u4e00-\u9fff]', result)
            if chinese_chars:
                # 取前8个中文字符
                result = ''.join(chinese_chars[:8])
            else:
                # 英文取前5个单词
                words = result.split()[:5]
                result = ' '.join(words)

        # 特殊处理：如果是百分比类型，强制提取百分比格式
        elif "percentage" in description.lower() or "%" in description or "percent" in description.lower():
            # 优先查找百分比模式
            percent_match = re.search(r'[+-]?\d+\.?\d*%', result)
            if percent_match:
                result = percent_match.group(0)
            else:
                # 尝试提取数字并添加 %
                num_match = re.search(r'[+-]?\d+\.?\d*', result)
                if num_match:
                    num = float(num_match.group(0))
                    # 如果是美元值（大于100），可能需要转换
                    # 但由于无法准确知道股价，我们直接返回带 % 的格式
                    # 如果数字很小（小于10），直接添加%
                    if abs(num) < 10:
                        result = f"{num:+.1f}%"
                    else:
                        # 大数字可能是美元值，无法准确转换，返回默认值
                        result = variable_config.get('default', '0.0%')

        # 如果是价格，确保有 $ 符号且格式正确
        elif "price" in description.lower() or ("$" in result and "%" not in result):
            # 尝试提取数字和 $ 符号
            price_match = re.search(r'\$?(\d+[\.,]\d{2})', result)
            if price_match:
                result = f"${price_match.group(1).replace(',', '.')}"

        # 只取第一行，并硬截断到80字符
        result = result.split('\n')[0].strip()
        if len(result) > 80:
            result = result[:80]

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

CRITICAL: Return ONLY the requested value in max 10 words. No explanation, no preamble, no markdown."""
    result = call_llm(full_prompt)
    
    # 截断保护，和 search_variable 一样
    if result:
        result = result.split('\n')[0].strip()
        if len(result) > 80:
            result = result[:80]
    
    return result


def get_variable_value(var_name, var_config, context):
    """获取单个变量的值"""
    source = var_config.get('source', 'literal')
    default = var_config.get('default', '')

    # 1. 字面值
    if source == 'literal':
        return var_config.get('value', '')

    # 2. 从话题提取
    if source == 'extract_from_topic':
        return extract_from_topic(var_config, context.get('topic', ''), context.get('vertical', ''))

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
