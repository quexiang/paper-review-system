"""Knowledge Graph Agent — extracts knowledge structure and builds a graph visualization."""

from __future__ import annotations

import asyncio
import json
import re

from .retry import retry_with_backoff
from .json_extract import extract_json


_SYSTEM_PROMPT = """\
你是一位资深的学术期刊审稿人。请阅读以下论文，提取其中的知识结构并构建知识图谱。

## 论文核心章节
{core_text}

请返回一个完整的 JSON 对象：
{{
  "summary": "知识图谱结构简要描述（至少100字）",
  "nodes": [
    {{"id": "n1", "label": "实体名称", "type": "theory | method | concept | result | variable | finding", "description": "节点描述"}},
    {{... 8-15 个节点}}
  ],
  "edges": [
    {{"source": "n1", "target": "n2", "label": "关系描述", "type": "supports | uses | contradicts | related | causes | improves"}},
    {{... 5-10 条关系}}
  ]
}}

注意：
- nodes: 提取论文中的关键知识元素（理论、方法、概念、结果、变量、发现等）
- edges: 描述节点之间的关系（如"方法A支持理论B"、"变量C影响结果D"）
- id 必须全局唯一，使用 "n1", "n2" 等
- edges 的 source 和 target 必须引用存在的节点 id
- 只返回 JSON，不要代码块"""


async def generate_knowledge_graph(
    text: str,
    llm,
    model: str,
    is_english: bool = False,
) -> dict:
    """Generate knowledge graph with nodes and edges from paper content."""
    core_text = text[:15000]

    system_prompt = _SYSTEM_PROMPT.format(core_text=core_text)

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
        print(f"[KnowledgeGraphAgent] Failed: timeout after retries")
        raise

    raw = resp.choices[0].message.content or "{}"

    # Clean thinking
    think_end = raw.find("</think>")
    if think_end >= 0:
        raw = raw[think_end + 8:].strip()

    # Extract & parse JSON (with truncation recovery)
    result = extract_json(raw, default={"summary": "", "nodes": [], "edges": []})

    return result
