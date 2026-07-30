"""文献综述 — 基于论文内容生成一篇完整的学术文献综述"""

from __future__ import annotations

import re
import asyncio

_SYSTEM_PROMPT = """\
你是一位资深的学术研究者。请根据提供的论文全文，生成一篇与该论文主题相关的学术文献综述。

文献综述要求：
1. **主题识别**：从论文中提取核心研究主题、关键词和研究领域
2. **领域综述**：围绕核心主题，综述该领域的研究现状和发展脉络
3. **分类组织**：按研究主题或方法论将相关文献分类组织，每类综述 300-500 字
4. **研究空白**：指出当前研究的不足和本论文填补的研究空白
5. **学术规范**：使用正式的学术语言，引用格式为 [编号]

文献综述结构：
- **引言**：简述研究领域背景和意义（约 200 字）
- **主题一综述**：第一个主要研究方向的进展与现状
- **主题二综述**：第二个主要研究方向的进展与现状
- **主题三综述**：第三个主要研究方向的进展与现状
- **研究空白与展望**：指出现有研究不足，引出本论文的研究价值
- **结语**：总结全文，展望未来研究方向

重要：
- 只输出文献综述正文，不要输出标题、前言或额外说明
- 综述内容必须与论文主题紧密相关，不能泛泛而谈
- 使用学术化的正式语言，字数至少 2000 字
- 合理组织内容，使综述具有逻辑性和连贯性

请直接输出文献综述正文：
"""


async def generate_literature_review(full_text: str, llm_client: object, model: str) -> str:
    """基于论文全文生成文献综述"""
    # 截取论文内容，截断过长内容
    text_preview = full_text[:20000]
    model_to_use = getattr(llm_client, "_model", model or "gpt-4o")

    try:
        resp = await asyncio.wait_for(
            llm_client.chat.completions.create(
                model=model_to_use,
                messages=[{"role": "system", "content": _SYSTEM_PROMPT}, {"role": "user", "content": text_preview}],
                temperature=0.7,
                max_tokens=8192,
            ),
            timeout=600.0
        )
    except asyncio.TimeoutError:
        print("[LitReview] 文献综述请求超时（600秒）")
        raise

    response_text = resp.choices[0].message.content or ""

    # ── 🆕 思维链清洗（与 polisher.py 保持一致） ──

    # 1. 去除 </think> 标签及其前的内容
    think_end = response_text.find('</think>')
    if think_end >= 0:
        response_text = response_text[think_end + len('</think>'):].strip()

    # 2. 去除 "Here's a thinking process:" 前缀及其后的思维链
    think_match = re.search(r'(Here\'s a thinking process:).*?\n\n', response_text, re.DOTALL | re.IGNORECASE)
    if think_match:
        response_text = response_text[think_match.end():].strip()

    # 3. 去除 markdown 代码块包裹（原有逻辑，保留）
    match = re.search(r"```(?:text|markdown|文献综述)?\s*\n(.*?)\n```", response_text, re.DOTALL)
    if match:
        return match.group(1).strip()

    return response_text.strip()