"""Logical Review Agent — generates section logic, argument logic, coherence issues, theme consistency, overall assessment."""

from __future__ import annotations

import asyncio
import json
import re

from .retry import retry_with_backoff
from .json_extract import extract_json


_SYSTEM_PROMPT = """\
你是一位资深的学术期刊审稿人，擅长逻辑性审查。请仔细阅读以下论文的核心章节，审查逻辑连贯性。

## 规则检查
{rule_lines}

## 论文核心章节
{core_text}

请返回一个完整的 JSON 对象：
{{
  "research_theme": "概括论文核心研究问题、目标和主要方法，至少100字",
  "research_framework": "用ASCII结构图画出研究路线和整体框架，各章节间用箭头表示逻辑关系",
  "section_logic": ["逐章节详细逻辑审查意见1", "至少3条"],
  "argument_logic": ["论点论据逻辑审查意见1", "至少3条"],
  "coherence_issues": [
    {{
      "location": "位置描述",
      "issue_type": "section_logic | argument_logic | sentence_coherence | theme_mismatch",
      "description": "详细问题描述",
      "severity": "error | warning | info",
      "suggestion": "修改建议"
    }}
  ],
  "theme_consistency": ["与核心主题一致性评价1", "至少2条"],
  "overall_assessment": "总体逻辑性评价，至少150字"
}}

逻辑审查要求：
- 紧密围绕论文研究主题展开
- 研究框架必须用ASCII图清晰画出各章节/模块的逻辑关系
- 每条审查意见要具体指出论文中的位置和问题
- 不要返回代码块，直接返回 JSON"""


_SYSTEM_PROMPT_BILINGUAL = """\
You are a senior academic journal reviewer specializing in logical review. Read the following paper sections carefully and review logical coherence.

## Rule Check
{rule_lines}

## Core Paper Sections
{core_text}

Please return a complete JSON object:
{{
  "research_theme": "Summarize core research question, objective, methodology, >=100 words",
  "research_framework": "Draw ASCII structure diagram showing research roadmap and framework with arrows between chapters",
  "section_logic": ["[English item 1]\\n\\n--- 中文翻译 ---\\n\\n[中文翻译]", "..."],
  "argument_logic": ["[English item 1]\\n\\n--- 中文翻译 ---\\n\\n[中文翻译]", "..."],
  "coherence_issues": [
    {{
      "location": "Location (English)",
      "issue_type": "section_logic | argument_logic | sentence_coherence | theme_mismatch",
      "description": "[English description]\\n\\n--- 中文翻译 ---\\n\\n[中文翻译]",
      "severity": "error | warning | info",
      "suggestion": "[English suggestion]\\n\\n--- 中文翻译 ---\\n\\n[中文翻译]"
    }}
  ],
  "theme_consistency": ["[English item]\\n\\n--- 中文翻译 ---\\n\\n[中文翻译]", "..."],
  "overall_assessment": "[English assessment >=150 words]\\n\\n--- 中文翻译 ---\\n\\n[中文评价 >=150字]"
}}

Rules:
- Focus on the paper's research theme
- ASCII diagram must show actual chapter names and logical flows
- Each comment must be specific to the paper's content
- Bilingual fields: use \\n\\n--- 中文翻译 ---\\n\\n as separator (literal two-char sequences, not actual newlines)
- Output ONLY JSON, no code blocks"""


async def generate_logical_review(
    text: str,
    rules: list,
    llm,
    model: str,
    is_english: bool = False,
) -> dict:
    """Generate logical review including research theme, framework, section/argument logic, coherence issues, theme consistency, overall assessment."""
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
        print(f"[LogicalReviewAgent] Failed: timeout after retries")
        raise

    raw = resp.choices[0].message.content or "{}"

    # Clean thinking
    think_end = raw.find("</think>")
    if think_end >= 0:
        raw = raw[think_end + 8:].strip()

    # Extract & parse JSON (with truncation recovery)
    result = extract_json(raw, default={
        "research_theme": "",
        "research_framework": "",
        "section_logic": [],
        "argument_logic": [],
        "coherence_issues": [],
        "theme_consistency": [],
        "overall_assessment": "由于AI解析失败，无法生成逻辑审查结果。",
    })

    return result
