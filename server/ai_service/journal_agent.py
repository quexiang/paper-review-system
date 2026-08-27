"""Journal Agent — recommends top journals based on paper content using LLM analysis."""

from __future__ import annotations

import asyncio
import json
import re

from .retry import retry_with_backoff
from .json_extract import extract_json


_SYSTEM_PROMPT = """\
你是一位资深的学术期刊编辑和审稿人。请根据以下论文的核心内容，推荐最适合投稿的 Top 10 期刊/会议。

## 论文核心章节
{core_text}

## 论文摘要/主题
{abstract_text}

请返回一个完整的 JSON 对象：
{{
  "journals": [
    {{
      "name": "期刊/会议全称",
      "level": "CCF-A | CCF-B | CCF-C | SCI Q1 | SCI Q2 等",
      "match": "匹配度百分比数字",
      "reason": "推荐理由（至少50字，结合论文具体内容和期刊特点）"
    }}
  ]
}}

要求：
- 推荐 Top 10 期刊/会议
- 匹配度要合理（高分对应高匹配）
- 推荐理由要结合论文的具体内容（如方法、领域、贡献）
- 包含中英文期刊/会议
- 按匹配度降序排列
- 只返回 JSON，不要代码块"""


async def generate_journals(
    text: str,
    sections: list,
    llm,
    model: str,
    is_english: bool = False,
) -> list:
    """Generate journal recommendations based on paper content analysis."""
    core_text = text[:15000]
    # Extract abstract for better recommendations
    abstract_text = ""
    for s in (sections or []):
        if s.title.lower() in ("摘要", "abstract", "绪论", "introduction"):
            abstract_text = s.content[:3000]
            break
    if not abstract_text:
        abstract_text = text[:3000]

    system_prompt = _SYSTEM_PROMPT.format(core_text=core_text, abstract_text=abstract_text)
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
        print(f"[JournalAgent] Failed: timeout after retries")
        raise

    raw = resp.choices[0].message.content or "{}"

    think_end = raw.find("</think>")
    if think_end >= 0:
        raw = raw[think_end + 8:].strip()

    # Extract & parse JSON (with truncation recovery)
    parsed = extract_json(raw, default={"journals": []})
    journals = parsed.get("journals", [])

    clean = []
    for j in journals:
        if isinstance(j, dict):
            match_val = j.get("match", 0)
            if isinstance(match_val, str):
                match_val = match_val.replace("%", "")
            try:
                match_val = min(100, max(0, int(match_val)))
            except (ValueError, TypeError):
                match_val = 0
            clean.append({
                "name": j.get("name", "未知期刊"),
                "level": j.get("level", "未分类"),
                "match": match_val,
                "reason": j.get("reason", "无推荐理由"),
            })
    return clean
