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

def fetch_stock_price(stock_code: str, timeout: int = 90) -> Optional[str]:
    """获取股票最新价格"""
    prompt = f"""What is the CURRENT stock price of {stock_code}?
Today is {datetime.now().strftime('%Y-%m-%d')}.

Return ONLY the price in format $XXX.XX (with dollar sign).
Example: $150.25

Return ONLY the price, nothing else."""
    try:
        result = subprocess.run(
            ['claude', '--dangerously-skip-permissions', '-p', prompt],
            capture_output=True, text=True, timeout=timeout
        )
        if result.returncode == 0 and result.stdout:
            match = re.search(r'\$\d{1,5}\.\d{2}', result.stdout)
            if match:
                return match.group(0)
    except (subprocess.TimeoutExpired, Exception):
        pass
    return None


def fetch_stock_change(stock_code: str, timeout: int = 90) -> Optional[str]:
    """获取股票最新变动百分比"""
    prompt = f"""What is the MOST RECENT daily percent change for {stock_code} stock?
Today is {datetime.now().strftime('%Y-%m-%d')}.

Return ONLY the percentage with sign and percent sign.
Format: +X.XX% or -X.XX%
Example: +1.5% or -2.3%

Return ONLY the percentage, nothing else."""
    try:
        result = subprocess.run(
            ['claude', '--dangerously-skip-permissions', '-p', prompt],
            capture_output=True, text=True, timeout=timeout
        )
        if result.returncode == 0 and result.stdout:
            # 修复: 使用 group(0) 而不是 group(1)
            match = re.search(r'[+-]?\d+\.?\d*%', result.stdout)
            if match:
                pct = match.group(0)  # 修复: group(0) 是整个匹配
                # 确保有符号
                if not pct.startswith(('+', '-')):
                    context = result.stdout.lower()[:100]
                    if any(w in context for w in ['down', 'declin', 'fall', 'drop', 'loss']):
                        pct = '-' + pct
                    else:
                        pct = '+' + pct
                return pct
    except (subprocess.TimeoutExpired, Exception):
        pass
    return None


def fetch_stock_reason(stock_code: str, timeout: int = 60) -> Optional[str]:
    """获取股票变动原因"""
    prompt = f"""What is the main reason why {stock_code} stock is moving today?
Today is {datetime.now().strftime('%Y-%m-%d')}.

Return ONLY a brief English explanation, maximum 5 words.
Examples: 'AI demand surge', 'earnings beat expectations', 'regulatory concerns', 'market sell-off'

Return ONLY the brief reason, no explanation."""
    try:
        result = subprocess.run(
            ['claude', '--dangerously-skip-permissions', '-p', prompt],
            capture_output=True, text=True, timeout=timeout
        )
        if result.returncode == 0 and result.stdout:
            cleaned = result.stdout.strip().split('\n')[0]
            cleaned = re.sub(r'^["\']|["\']$', '', cleaned)
            words = cleaned.split()[:5]
            cleaned = ' '.join(words)
            cleaned = re.sub(r'[.!?;,]+$', '', cleaned)
            if len(cleaned) >= 3:
                return cleaned.lower()
    except (subprocess.TimeoutExpired, Exception):
        pass
    return None


def extract_price_from_research(research_data: str) -> Optional[str]:
    """从研究数据中提取价格（简化版）"""
    patterns = [
        r'(?:Current(?:\s*Stock)?(?:\s*Price)?|Price|Last(?:\s*Price)?)\s*[:=]\s*\$?\s*(\d{1,5}\.?\d{0,2})',
        r'\$\s*(\d{1,5}\.\d{2})\s*(?:USD)?\s*(?:per\s*share|/share)?',
        r'\$\s*(\d{1,5})\s',
        r'(?:trading|at|around|currently)\s*\$?\s*(\d{1,5}\.?\d{0,2})',
    ]
    for pattern in patterns:
        match = re.search(pattern, research_data[:3000], re.IGNORECASE)
        if match:
            price_num = match.group(1)
            if '.' not in price_num:
                price_num = f'{price_num}.00'
            elif len(price_num.split('.')[1]) == 1:
                price_num = f'{price_num}0'
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

        # 尝试提取 ```json ``` 代码块
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试找到第一个 { 和最后一个 }
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end+1])
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Cannot parse JSON from LLM output: {text[:200]}")


# =============================================================================
# Step 1: Research
# =============================================================================

class Step1Research(BaseStep):
    """Step 1: 搜索数据"""

    def run(self, session: XhsSession, **kwargs) -> bool:
        """执行搜索步骤"""
        session.log('info', 'research', 'Step started',
                   {'topic': session.topic, 'vertical': session.vertical})

        session.update_step('research', 'in_progress')

        try:
            config = self.load_vertical_config(session.vertical)
            research_config = config.get('content_research', {})
            queries = research_config.get('queries', [])

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
                query = template.replace('{topic}', session.topic).replace('{year}', str(current_year))

                search_queries_used.append(query)
                session.log('info', 'research', f'Searching: {query[:50]}...',
                          {'purpose': purpose})

                search_prompt = f"""Search the web for: "{query}"

Today's date is {datetime.now().strftime('%Y-%m-%d')}.

Summarize the key findings in a structured format. Include:
- Key data points (prices, numbers, dates)
- Important news or events
- Relevant facts about the topic

Be thorough and factual. Do not fabricate data."""

                try:
                    search_start = time.time()
                    result = subprocess.run(
                        ['claude', '--dangerously-skip-permissions', '-p', search_prompt],
                        capture_output=True, text=True, timeout=60
                    )
                    elapsed = time.time() - search_start

                    if result.returncode == 0 and result.stdout.strip():
                        all_results.append(
                            f"## Query: {query}\n**Purpose**: {purpose}\n\n{result.stdout.strip()}"
                        )
                        session.log('debug', 'research', 'Search successful',
                                  {'query': query[:30], 'elapsed': round(elapsed, 2)})
                        self._save_search_results(session, query, result.stdout.strip(), elapsed)
                    else:
                        error_msg = result.stderr[:200] if result.stderr else 'Unknown error'
                        all_results.append(
                            f"## Query: {query}\n**Purpose**: {purpose}\n\n**Search failed**: {error_msg}"
                        )
                        session.log('warn', 'research', 'Search failed',
                                  {'query': query[:30], 'error': error_msg})

                except subprocess.TimeoutExpired:
                    all_results.append(f"## Query: {query}\n**Purpose**: {purpose}\n\n**Search timed out**")
                    session.log('error', 'research', 'Search timed out', {'query': query[:30]})

                except Exception as e:
                    all_results.append(f"## Query: {query}\n**Purpose**: {purpose}\n\n**Search error**: {str(e)}")
                    session.log('error', 'research', 'Search error',
                              {'query': query[:30], 'error': str(e)})

            # 写入 research_raw.md
            research_output = '\n\n---\n\n'.join(all_results)
            session.write_file('research_raw.md', research_output)

            # 更新 session
            session.update_step('research', 'completed', {
                'search_queries': search_queries_used,
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

## 搜索结果（必须基于这些数据）

{research_data}

{feedback_section}

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
4. 所有数据必须来自搜索结果，不允许编造
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
            return self._extract_from_content(var_config, context, session), 'from_content'

        # web_search
        if source == 'web_search':
            return self._search_variable(var_config, var_name, context, session, research_data), 'web_search'

        # conditional
        if source == 'conditional':
            return self._resolve_conditional(var_config, context), 'conditional'

        # llm_inference
        if source == 'llm_inference':
            return self._infer_variable(var_config, context), 'llm_inference'

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
                             session: XhsSession) -> str:
        """从内容中提取变量"""
        # 简化版：从 session 获取
        if var_config.get('description') == 'title':
            return context.get('title', '')
        if var_config.get('description') == 'subtitle':
            return context.get('subtitle', '')
        return var_config.get('default', '')

    def _search_variable(self, var_config: Dict, var_name: str,
                        context: Dict, session: XhsSession,
                        research_data: str) -> str:
        """通过搜索获取变量"""
        default = var_config.get('default', '')
        stock_code = context.get('stock_code', '')

        # 特殊处理股票相关变量 - 使用共享的辅助函数
        if var_name == 'price' and stock_code:
            result = fetch_stock_price(stock_code, timeout=90)
            if result:
                return result
            # 回退到从 research_data 提取
            if research_data:
                price = extract_price_from_research(research_data)
                if price:
                    session.log('info', 'prepare_img', f'Extracted price from research: {price}')
                    return price
            return default

        if var_name == 'change' and stock_code:
            result = fetch_stock_change(stock_code, timeout=90)
            if result:
                return result
            # 回退到从 research_data 提取
            if research_data:
                change = extract_change_from_research(research_data)
                if change:
                    session.log('info', 'prepare_img', f'Extracted change from research: {change}')
                    return change
            return default

        if var_name == 'reason' and stock_code:
            result = fetch_stock_reason(stock_code, timeout=60)
            if result:
                return result
            return default

        # 其他变量使用通用搜索
        query = var_config.get('query', '').format(**context)
        description = var_config.get('description', '')

        search_prompt = f"""Search for: "{query}"
Today: {datetime.now().strftime('%Y-%m-%d')}
Extract: {description}

Return ONLY the value, maximum 30 words. No explanation."""

        try:
            result = self.call_llm(search_prompt, expect_json=False, timeout=90)
            if result:
                return self._clean_variable_result(var_name, result.strip(), default)
        except Exception as e:
            session.log('warn', 'prepare_img', f'Search failed for {var_name}: {str(e)}')

        return default

    def _clean_variable_result(self, var_name: str, raw: str, default: str) -> str:
        """清理变量结果"""
        if not raw:
            return default

        # 清理换行
        cleaned = raw.strip().replace('\n', ' ').replace('\r', ' ')
        cleaned = re.sub(r'\s+', ' ', cleaned)

        if var_name == 'price':
            # 提取价格
            match = re.search(r'\$\s*(\d{1,5}\.?\d{0,2})', cleaned)
            if match:
                return f'${match.group(1)}'
            return cleaned[:50]

        if var_name == 'change':
            # 提取百分比
            match = re.search(r'([+-]?\d+\.?\d*)%', cleaned)
            if match:
                pct = match.group(1)
                if not pct.startswith(('+', '-')):
                    pct = '+' + pct
                return f'{pct}%'
            return cleaned[:50]

        if var_name == 'reason':
            # 清理为简短英文
            words = cleaned.split()[:5]
            cleaned = ' '.join(words)
            cleaned = re.sub(r'[.!?;,]+$', '', cleaned)
            return cleaned.lower() if len(cleaned) >= 3 else 'market volatility'

        return cleaned[:200]

    def _resolve_conditional(self, var_config: Dict, context: Dict) -> str:
        """解析条件变量"""
        condition = var_config.get('condition', '')
        condition_var = var_config.get('condition_var', '')
        default = var_config.get('default', '')

        if condition_var not in context:
            return default

        var_value = str(context[condition_var])
        is_pos = '+' in var_value or var_value.replace('.', '').isdigit() and float(var_value.replace('%', '')) > 0
        is_neg = '-' in var_value

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

    def _infer_variable(self, var_config: Dict, context: Dict) -> str:
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
                return result.strip().split('\n')[0][:150]
        except:
            pass

        return var_config.get('default', '')


# =============================================================================
# Step 4a: Validate Stock Data (仅用于股票垂类)
# =============================================================================

class Step4aValidateStockData(BaseStep):
    """Step 4a: 验证股票数据准确性"""

    def run(self, session: XhsSession, **kwargs) -> bool:
        """执行股票数据验证步骤"""
        # 只对 stock 垂类执行验证
        if session.vertical != 'stock':
            return True

        session.log('info', 'validate_stock_data', 'Step started')
        session.update_step('validate_stock_data', 'in_progress')

        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            # 获取当前的数据
            prepare_data = session.get_step_data('prepare_img')
            variables = prepare_data.get('variables', {})
            sources = prepare_data.get('variables_source', {})

            stock_code = variables.get('stock_code', '')
            price = variables.get('price', '')
            change = variables.get('change', '')
            reason = variables.get('reason', '')

            session.log('info', 'validate_stock_data',
                       f'Validation attempt {retry_count + 1}/{max_retries}',
                       {'stock_code': stock_code, 'price': price, 'change': change, 'reason': reason})

            # 验证价格格式
            price_valid = self._validate_price(price)
            if not price_valid:
                session.log('warn', 'validate_stock_data', f'Invalid price format: {price}')
                # 重新获取价格
                new_price = self._fetch_price(stock_code, session)
                if new_price:
                    variables['price'] = new_price
                    sources['price'] = 'web_search_retry'
                    session.log('info', 'validate_stock_data', f'Refetched price: {new_price}')

            # 验证变动格式
            change_valid = self._validate_change(change)
            if not change_valid:
                session.log('warn', 'validate_stock_data', f'Invalid change format: {change}')
                # 重新获取变动
                new_change = self._fetch_change(stock_code, session)
                if new_change:
                    variables['change'] = new_change
                    sources['change'] = 'web_search_retry'
                    session.log('info', 'validate_stock_data', f'Refetched change: {new_change}')

            # 验证 reason
            reason_valid = self._validate_reason(reason)
            if not reason_valid:
                session.log('warn', 'validate_stock_data', f'Invalid reason: {reason}')
                # 重新获取 reason
                new_reason = self._fetch_reason(stock_code, session)
                if new_reason:
                    variables['reason'] = new_reason
                    sources['reason'] = 'web_search_retry'
                    session.log('info', 'validate_stock_data', f'Refetched reason: {new_reason}')

            # 更新填充的 prompt
            config = self.load_vertical_config(session.vertical)
            cover_config = config.get('cover_config', {})
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

            # 最终验证
            if (self._validate_price(variables.get('price', '')) and
                self._validate_change(variables.get('change', '')) and
                self._validate_reason(variables.get('reason', ''))):
                session.update_step('validate_stock_data', 'completed', {
                    'validated_data': {
                        'stock_code': stock_code,
                        'price': variables.get('price', ''),
                        'change': variables.get('change', ''),
                        'reason': variables.get('reason', '')
                    }
                })
                session.log('success', 'validate_stock_data', 'All data validated successfully')
                return True

            retry_count += 1

        # 达到最大重试次数
        session.update_step('validate_stock_data', 'completed', {
            'validation_result': 'max_retries_reached',
            'final_data': variables
        })
        session.log('warn', 'validate_stock_data', 'Reached max retries, using current data')
        return True  # 继续执行，使用当前数据

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
            'not available',
            'no information',
            'as of my',
            'the article',
            'based on the',
            'according to the',
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
        invalid_starts = ['the ', 'a ', 'an ', 'i ', 'it ', 'this ', 'based on', 'according to']
        if any(reason_lower.startswith(s) for s in invalid_starts):
            return False

        # 检查是否以标点符号结尾（可能是不完整的句子）
        if reason.endswith(',') or reason.endswith('.'):
            return False

        return True

    def _fetch_price(self, stock_code: str, session: XhsSession) -> Optional[str]:
        """重新获取价格"""
        result = fetch_stock_price(stock_code, timeout=90)
        if result:
            return result
        session.log('warn', 'validate_stock_data', 'Failed to fetch price')
        return None

    def _fetch_change(self, stock_code: str, session: XhsSession) -> Optional[str]:
        """重新获取变动"""
        result = fetch_stock_change(stock_code, timeout=90)
        if result:
            return result
        session.log('warn', 'validate_stock_data', 'Failed to fetch change')
        return None

    def _fetch_reason(self, stock_code: str, session: XhsSession) -> Optional[str]:
        """重新获取 reason"""
        result = fetch_stock_reason(stock_code, timeout=60)
        if result:
            return result
        session.log('warn', 'validate_stock_data', 'Failed to fetch reason')
        return None


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

        session.log('info', 'gen_img', f'Generating image: {filled_prompt[:100]}...')

        generate_image(
            prompt=filled_prompt,
            output_path=output_file,
            api_key=api_key,
            resolution='1K'
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

            try:
                generate_image(
                    prompt=prompt,
                    output_path=output_file,
                    api_key=api_key,
                    resolution='1K',
                    reference_image=reference_image  # 传入参考图片
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

            except Exception as e:
                session.log('error', 'gen_img', f'Failed to generate image {idx}: {str(e)}')
                # 创建一个占位文件，避免后续步骤失败
                output_file.write_text(f'Image generation failed: {str(e)}')
                file_sizes.append(0)

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
