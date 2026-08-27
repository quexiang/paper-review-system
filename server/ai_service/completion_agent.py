"""Completion Agent — detects missing/underdeveloped sections and generates content drafts."""

from __future__ import annotations

import asyncio
import json
import re

from .retry import retry_with_backoff
from .json_extract import extract_json


_SYSTEM_PROMPT = """\
你是一位资深的学术期刊审稿人。请阅读以下论文，检测缺失或内容不足的章节，并生成补充内容草稿。

## 论文核心章节
{core_text}

## 现有章节列表
{section_list}

请返回一个完整的 JSON 对象：
{{
  "completions": [
    {{
      "section": "章节名",
      "generated_content": "补充内容草稿（至少300字，与论文主题紧密结合）",
      "confidence": 0.5-0.9
    }}
  ]
}}

要求：
- 至少 2 条补全建议
- 如果章节缺失，生成完整的章节草稿
- 如果章节存在但内容不足，提供扩展建议
- 补全内容必须与论文主题紧密结合
- 只返回 JSON，不要代码块"""


async def generate_completions(
    text: str,
    sections: list,
    llm,
    model: str,
    is_english: bool = False,
) -> list:
    """Generate completion suggestions with content drafts for missing/underdeveloped sections."""
    core_text = text[:15000]
    section_list = "\n".join(f"- {s.title}" for s in sections) if sections else "未识别到章节"

    system_prompt = _SYSTEM_PROMPT.format(core_text=core_text, section_list=section_list)
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
        print(f"[CompletionAgent] Failed: timeout after retries")
        raise

    raw = resp.choices[0].message.content or "{}"

    think_end = raw.find("</think>")
    if think_end >= 0:
        raw = raw[think_end + 8:].strip()

    # Extract & parse JSON (with truncation recovery)
    parsed = extract_json(raw, default={"completions": []})
    completions = parsed.get("completions", [])

    clean = []
    for c in completions:
        if isinstance(c, dict):
            conf = c.get("confidence", 0.5)
            try:
                conf = max(0.5, min(0.9, float(conf)))
            except (ValueError, TypeError):
                conf = 0.5
            clean.append({
                "section": c.get("section", "未指定章节"),
                "generated_content": c.get("generated_content", "（请根据论文内容撰写）"),
                "confidence": conf,
            })
    return clean
