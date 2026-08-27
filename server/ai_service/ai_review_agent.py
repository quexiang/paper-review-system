"""AI Review Agent — generates per-section AI review comments with suggestions."""

from __future__ import annotations

import asyncio
import json
import re

from .retry import retry_with_backoff
from .json_extract import extract_json


_SYSTEM_PROMPT = """\
你是一位资深的学术期刊审稿人。请对以下论文章节进行逐章节的深度审阅。

## 规则检查
{rule_lines}

## 论文核心章节
{core_text}

请返回一个完整的 JSON 对象：
{{
  "ai_reviews": [
    {{
      "section": "章节名",
      "review_comment": "详尽审阅意见（每个维度: 内容质量/写作水平/具体问题/优点，至少200字）",
      "original_text": "原文关键片段",
      "suggestion": "具体修改建议（至少50字）"
    }}
  ]
}}

要求：
- 至少 5 条审阅意见，覆盖论文的主要章节
- 每条意见必须具体针对论文内容，不能泛泛而谈
- 指出原文的具体位置和修改建议
- 只返回 JSON，不要代码块"""


_SYSTEM_PROMPT_BILINGUAL = """\
You are a senior academic journal reviewer. Conduct deep, per-section reviews of the following paper.

## Rule Check
{rule_lines}

## Core Paper Sections
{core_text}

Please return a complete JSON object:
{{
  "ai_reviews": [
    {{
      "section": "Section name",
      "review_comment": "[English detailed review covering content quality, writing level, specific issues, strengths - >=200 words]\\n\\n--- 中文翻译 ---\\n\\n[Chinese translation]",
      "original_text": "[English quote]\\n\\n--- 中文翻译 ---\\n\\n[Chinese quote]",
      "suggestion": "[English suggestion >=50 words]\\n\\n--- 中文翻译 ---\\n\\n[Chinese suggestion]"
    }}
  ]
}}

Rules:
- At least 5 reviews covering major sections
- Each must be specific to the paper, not generic
- Bilingual fields: use \\n\\n--- 中文翻译 ---\\n\\n as separator
- Output ONLY JSON, no code blocks"""


async def generate_ai_reviews(
    text: str,
    rules: list,
    llm,
    model: str,
    is_english: bool = False,
) -> list:
    """Generate per-section AI review comments with suggestions."""
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
        print(f"[AiReviewAgent] Failed: timeout after retries")
        raise

    raw = resp.choices[0].message.content or "{}"

    # Clean thinking
    think_end = raw.find("</think>")
    if think_end >= 0:
        raw = raw[think_end + 8:].strip()

    # Extract & parse JSON (with truncation recovery)
    parsed = extract_json(raw, default={"ai_reviews": []})
    reviews = parsed.get("ai_reviews", [])

    # Ensure each item is a dict with expected keys
    clean_reviews = []
    for r in reviews:
        if isinstance(r, dict):
            clean_reviews.append({
                "section": r.get("section", "未命名章节"),
                "review_comment": r.get("review_comment", "审阅解析失败，建议人工复审。"),
                "original_text": r.get("original_text"),
                "suggestion": r.get("suggestion", "无"),
            })
    return clean_reviews
