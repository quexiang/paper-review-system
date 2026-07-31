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

_SYSTEM_PROMPT_BILINGUAL = """\
You are a senior academic researcher. Based on the provided paper, generate a comprehensive academic literature review related to the paper's topic.

Literature review requirements:
1. **Topic Identification**: Extract core research topics, keywords, and research fields from the paper
2. **Field Review**: Review the current research status and development trajectory around the core topic
3. **Categorized Organization**: Categorize related literature by research topic or methodology, with 300-500 words per category
4. **Research Gaps**: Point out current research shortcomings and how this paper fills the gaps
5. **Academic Standards**: Use formal academic language, citation format as [number]

Literature review structure:
- **Introduction**: Briefly introduce the research field background and significance (about 200 words)
- **Theme One Review**: Progress and current status of the first major research direction
- **Theme Two Review**: Progress and current status of the second major research direction
- **Theme Three Review**: Progress and current status of the third major research direction
- **Research Gaps and Outlook**: Identify limitations of existing research and highlight this paper's research value
- **Conclusion**: Summarize the full text and look forward to future research directions

Important:
- Output ONLY the literature review body text, no title, preface, or extra explanation
- Review content must be closely related to the paper's topic, not generic
- Use formal academic language, at least 2000 words
- Organize content logically and coherently

IMPORTANT - BILINGUAL OUTPUT:
After outputting the literature review in English, append the Chinese translation using the exact delimiter "--- 中文翻译 ---" on its own line.
The format must be: [English literature review text]\n\n--- 中文翻译 ---\n\n[Chinese translation of the literature review]
Both versions must be complete and accurate.

Please output the literature review:
"""


async def generate_literature_review(full_text: str, llm_client: object, model: str, is_english: bool = False) -> str:
    """基于论文全文生成文献综述"""
    # 截取论文内容，截断过长内容
    text_preview = full_text[:20000]
    model_to_use = getattr(llm_client, "_model", model or "gpt-4o")
    # 英文稿件使用双语 prompt
    system_prompt = _SYSTEM_PROMPT_BILINGUAL if is_english else _SYSTEM_PROMPT

    try:
        resp = await asyncio.wait_for(
            llm_client.chat.completions.create(
                model=model_to_use,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": text_preview}],
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