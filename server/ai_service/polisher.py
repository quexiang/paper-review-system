"""论文润色 — 逐章润色后拼接为完整 SCI 级学术文稿"""

from __future__ import annotations

import re
def has_repetitive_pattern(text: str, threshold: int = 20) -> bool:
    words = re.findall(r'\b\w+\b', text)
    if not words:
        return False
    from collections import Counter
    most_common = Counter(words).most_common(1)
    return most_common and most_common[0][1] > threshold

def truncate_repetitive_text(text: str, threshold: int = 20) -> str:
    """如果检测到重复词，截取到重复首次出现之前"""
    words = re.findall(r'\b\w+\b', text)
    if not words:
        return text
    from collections import defaultdict
    word_positions = defaultdict(list)
    for idx, w in enumerate(words):
        word_positions[w].append(idx)
    for w, positions in word_positions.items():
        if len(positions) > threshold:
            # 截取到该词第一次出现之前（按字符粗略估算）
            cut_pos = positions[0] * 6  # 6 为平均字符/词
            return text[:cut_pos].strip()
    return text

_SYSTEM_PROMPT = """\
你是一位专业的学术语言编辑。请对以下论文章节进行语言润色，但**严格保留原文的所有技术内容、术语、数据和论证逻辑**。

润色范围（只改这些）：
1. 修正语法错误和标点问题
2. 优化不通顺或拗口的句子
3. 调整过于冗长的表达，使其更简洁
4. 强化句间和段间的逻辑连接词

绝对禁止（不能碰这些）：
1. 不能替换或简化专业术语（如"碳排放交易价格"不能改成"碳价"）
2. 不能删减或重新组织论证内容
3. 不能改变原文的数据、数字、百分比
4. 不能替换原文的关键动词和表述方式
5. 不能用自己的话重新表述原文的意思

核心原则：润色后的文本**意思必须与原文完全相同**，只是语言表达更流畅、更规范。

重要：
- 只输出润色后的文本，不要输出任何解释、说明、标记或额外内容
- 保留原文的结构（段落划分、标题层级）
- 保留所有引用标记如 [1]、(Smith, 2020) 等
- 保留所有数学公式、变量、符号

请直接输出润色后的完整文本：
"""

_SYSTEM_PROMPT_BILINGUAL = """\
You are a professional academic language editor. Please polish the following paper section, but **strictly preserve all technical content, terminology, data, and argumentation logic**.

Polishing scope (only these):
1. Fix grammar errors and punctuation issues
2. Optimize awkward or unfluent sentences
3. Simplify overly verbose expressions
4. Strengthen logical connectors between sentences and paragraphs

Absolutely forbidden (do NOT do these):
1. Do NOT replace or simplify technical terminology
2. Do NOT delete or reorganize argument content
3. Do NOT change original data, numbers, or percentages
4. Do NOT replace key verbs and expressions
5. Do NOT rephrase the original meaning in your own words

Core principle: The polished text **must have exactly the same meaning** as the original, only with more fluent and professional expression.

Important:
- Output ONLY the polished text, no explanations, notes, tags, or extra content
- Preserve the original structure (paragraph divisions, heading hierarchy)
- Preserve all citation markers like [1], (Smith, 2020), etc.
- Preserve all mathematical formulas, variables, and symbols

IMPORTANT - BILINGUAL OUTPUT:
After outputting the polished English text, append the Chinese translation using the exact delimiter "--- 中文翻译 ---" on its own line.
The format should be: [English polished text]\n\n--- 中文翻译 ---\n\n[Chinese translation of the polished text]
Both versions must be complete and accurate.

Please output the polished text:
"""


async def polish_section(
    section_text: str, llm_client: object, model: str, is_english: bool = False
) -> str:
    """润色单个论文章节，返回润色后的文本"""
    import re
    import asyncio

    model_to_use = getattr(llm_client, "_model", model or "gpt-4o")
    # 英文稿件使用双语 prompt
    system_prompt = _SYSTEM_PROMPT_BILINGUAL if is_english else _SYSTEM_PROMPT
    try:
        resp = await asyncio.wait_for(
            llm_client.chat.completions.create(
                model=model_to_use,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": section_text}],
                temperature=0.7,
                max_tokens=8192,
                stop=["\n\n\n"],
            ),
            timeout=600.0  # 10 分钟超时
        )
    except asyncio.TimeoutError:
        raise TimeoutError("章节润色超时（600秒）")

    response_text = resp.choices[0].message.content or ""

    # ---------- 关键：清洗 thinking 块 ----------
    # 去除 Claude thinking 块（</think> 标签）
    think_end = response_text.find('</think>')
    if think_end >= 0:
        response_text = response_text[think_end + len('</think>'):].strip()

    # 去除 "Here's a thinking process:" 前缀
    think_match = re.search(r'(Here\'s a thinking process:).*?\n\n', response_text, re.DOTALL | re.IGNORECASE)
    if think_match:
        response_text = response_text[think_match.end():].strip()
    # ---------- 清洗结束 ----------

    # 👇 在这里插入调试日志（清洗之后，去除 markdown 之前）
    print(f"[Polisher] 清洗后文本长度: {len(response_text)}，前200字符: {response_text[:200]}")

    # 去除 markdown 代码块包裹
    match = re.search(r"```(?:text|markdown)?\s*\n(.*?)\n```", response_text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return response_text.strip()


async def polish_paper(full_text: str, sections: list, llm_client: object, model: str, is_english: bool = False) -> str:
    """
    按章节拆分论文，并发润色后拼接为完整润色文稿。
    """
    import asyncio

    async def _build_and_polish(sec: object, sec_idx: int, sem: asyncio.Semaphore) -> tuple[int, str]:
        if sec.level == 1:
            header = f"# {sec.title}\n"
        elif sec.level == 2:
            header = f"## {sec.title}\n"
        elif sec.level == 3:
            header = f"### {sec.title}\n"
        else:
            header = f"{'#' * sec.level} {sec.title}\n"
        section_content = header + sec.content
        async with sem:
            polished = await polish_section(section_content, llm_client, model, is_english)
        return sec_idx, polished

    CONCURRENT_LIMIT = 4  # 保持内部并发，但受 main.py 的 Semaphore(2) 限制，实际就是 2

    if sections and len(sections) > 0:
        sem = asyncio.Semaphore(CONCURRENT_LIMIT)
        tasks = [_build_and_polish(sec, i, sem) for i, sec in enumerate(sections)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        polished_map: dict[int, str] = {}
        failed_count = 0
        for idx, result in enumerate(results):
            if isinstance(result, Exception) or not isinstance(result, tuple):
                failed_count += 1
                print(f"[Polisher] 章节 {idx} 润色失败，使用原文: {result}")
                continue
            sec_idx, polished = result
            polished_map[sec_idx] = polished

        polished_sections: list[str] = []
        for i, sec in enumerate(sections):
            if sec.level == 1:
                header = f"# {sec.title}\n"
            elif sec.level == 2:
                header = f"## {sec.title}\n"
            elif sec.level == 3:
                header = f"### {sec.title}\n"
            else:
                header = f"{'#' * sec.level} {sec.title}\n"
            if i in polished_map:
                polished_sections.append(polished_map[i])
            else:
                polished_sections.append(header + sec.content)

        # 【关键修改】直接拼接，删掉所有 pre/post 处理
        polished_all = "\n\n".join(polished_sections)

        if failed_count:
            print(
                f"[Polisher] 共 {len(sections)} 章，{len(sections) - failed_count} 章润色成功，{failed_count} 章使用原文")
        return polished_all

    # 没有解析到章节，直接润色全文
    print("[Polisher] 未解析到章节，直接润色全文")
    return await polish_section(full_text, llm_client, model)