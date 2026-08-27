"""Summary Agent — generates paper review summary (score, strengths, weaknesses, recommendation)."""

from __future__ import annotations

import asyncio
import re
import json

from .retry import retry_with_backoff
from .json_extract import extract_json


_SYSTEM_PROMPT = """\
你是一位资深的学术期刊审稿人。请阅读以下论文的核心章节，给出总体评价。

## 规则检查
{rule_lines}

## 论文核心章节
{core_text}

请返回一个 JSON 对象：
{{
  "overall_score": 0-100 的整数,
  "strengths": ["具体优点1", "优点2", "至少4条"],
  "weaknesses": ["具体缺点1", "缺点2", "至少4条"],
  "recommendation": "accept | minor_revision | major_revision | reject"
}}

要求：
- 每条优点/缺点必须具体针对论文内容，不能泛泛而谈
- 评分要客观公正，结合创新性、方法论、实验设计、写作水平等维度
- 只返回 JSON，不要代码块"""


_SYSTEM_PROMPT_BILINGUAL = """\
You are a senior academic journal reviewer. Read the following paper sections and provide an overall evaluation.

## Rule Check
{rule_lines}

## Core Paper Sections
{core_text}

Please return a JSON object:
{{
  "overall_score": integer 0-100,
  "strengths": ["Specific strength 1", "at least 4", "..."],
  "weaknesses": ["Specific weakness 1", "at least 4", "..."],
  "recommendation": "accept | minor_revision | major_revision | reject"
}}

Requirements:
- Each strength/weakness must be specific to the paper content, not generic
- Score should be objective considering innovation, methodology, experiments, writing quality
- Output ONLY JSON"""


async def generate_summary(
    text: str,
    rules: list,
    llm,
    model: str,
    is_english: bool = False,
) -> dict:
    """Generate summary: score, strengths, weaknesses, recommendation."""
    rule_lines = "\n".join(f"- [{r.severity.value}] {r.title}" for r in rules) or "No rule issues"
    core_text = text[:15000]

    system_prompt = _SYSTEM_PROMPT_BILINGUAL if is_english else _SYSTEM_PROMPT
    system_prompt = system_prompt.format(rule_lines=rule_lines, core_text=core_text)

    model_to_use = getattr(llm, "_model", model or "gpt-4o")

    async def _call_llm():
        return await asyncio.wait_for(
            llm.chat.completions.create(
                model=model_to_use,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": text}],
                temperature=0.3,
                max_tokens=8192,
            ),
            timeout=600.0,
        )

    try:
        resp = await retry_with_backoff(_call_llm, max_retries=3, base_delay=2.0, max_delay=30.0)
    except asyncio.TimeoutError:
        print(f"[SummaryAgent] Failed: timeout after retries")
        raise

    raw = resp.choices[0].message.content or "{}"

    # Clean thinking
    think_end = raw.find("</think>")
    if think_end >= 0:
        raw = raw[think_end + 8:].strip()

    # Extract & parse JSON (with truncation recovery)
    result = extract_json(raw, default={
        "overall_score": 60.0,
        "strengths": ["稿件结构基本完整"],
        "weaknesses": ["AI解析失败，建议人工复审"],
        "recommendation": "major_revision",
    })

    score = float(result.get("overall_score", 60.0))
    result["overall_score"] = max(0.0, min(100.0, score))
    return result
