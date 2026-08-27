"""Revision Agent — generates revision traces (insertions, deletions, modifications with rationale)."""

from __future__ import annotations

import asyncio
import json
import re

from .retry import retry_with_backoff
from .json_extract import extract_json


_SYSTEM_PROMPT = """\
你是一位资深的学术期刊审稿人。请对以下论文提出具体的修改建议，并以修订痕迹的形式展示。

## 规则检查
{rule_lines}

## 论文核心章节
{core_text}

请返回一个完整的 JSON 对象：
{{
  "revisions": [
    {{
      "revision_type": "insertion | deletion | modification",
      "original_text": "原文（删除/修改时填写）",
      "new_text": "修改后的内容",
      "location": "位置描述（章节名+段落）",
      "rationale": "详细的修改理由"
    }}
  ]
}}

要求：
- 至少 8 条修订建议
- 每条必须标注修改位置和详细理由
- insertion: 新增内容
- deletion: 删除内容
- modification: 修改原文
- 只返回 JSON，不要代码块"""


async def generate_revisions(
    text: str,
    rules: list,
    llm,
    model: str,
    is_english: bool = False,
) -> list:
    """Generate revision traces: insertions, deletions, modifications with rationale."""
    rule_lines = "\n".join(f"- [{r.severity.value}] {r.title}" for r in rules) or "No rule issues"
    core_text = text[:15000]

    system_prompt = _SYSTEM_PROMPT.format(rule_lines=rule_lines, core_text=core_text)
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
        print(f"[RevisionAgent] Failed: timeout after retries")
        raise

    raw = resp.choices[0].message.content or "{}"

    think_end = raw.find("</think>")
    if think_end >= 0:
        raw = raw[think_end + 8:].strip()

    # Extract & parse JSON (with truncation recovery)
    parsed = extract_json(raw, default={"revisions": []})
    revisions = parsed.get("revisions", [])

    clean = []
    for r in revisions:
        if isinstance(r, dict):
            rev_type = r.get("revision_type", "modification")
            # Normalize revision_type to match RevisionType enum
            if rev_type == "type":
                rev_type = "modification"
            clean.append({
                "revision_type": rev_type,
                "original_text": r.get("original_text"),
                "new_text": r.get("new_text", ""),
                "location": r.get("location", "未指定"),
                "rationale": r.get("rationale", "无"),
            })
    return clean
