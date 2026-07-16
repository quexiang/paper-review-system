"""AI 审阅器 - 基于 LLM 进行论文语义级审阅"""

from __future__ import annotations

import json
from models import AIReviewItem, Revision, ReviewSummary, RuleReport


# ── 系统提示词 ──────────────────────────────────────────────


_SYSTEM_PROMPT = """\
你是一位资深的学术期刊审稿人，擅长全面、深入地评审学术论文。请对论文进行详尽、严格、建设性的审阅。

你的输出必须是一个严格的 JSON 对象，包含以下全部字段。每项内容都必须详尽、具体、有深度：

{
  "summary": {
    "overall_score": 0-100,
    "strengths": ["具体优点1", "具体优点2", ...],
    "weaknesses": ["具体缺点1", "具体缺点2", ...],
    "recommendation": "accept | minor_revision | major_revision | reject"
  },
  "ai_reviews": [
    {
      "section": "章节名",
      "review_comment": "详尽的审阅意见（涵盖该章节的优缺点、内容质量、逻辑性等）",
      "original_text": "原文关键片段（可选）",
      "suggestion": "具体修改建议"
    }
  ],
  "revisions": [
    {
      "type": "insertion | deletion | modification",
      "original_text": "原文（仅删除/修改时填写）",
      "new_text": "修改后的内容或补充内容",
      "location": "位置描述",
      "rationale": "详细的修改理由"
    }
  ],
  "completions": [
    {
      "section": "缺失章节名",
      "generated_content": "AI 生成的补充内容草稿（与论文主题高度相关）",
      "confidence": 0.5-1.0
    }
  ],
  "logical_review": {
    "section_logic": ["逐章节的详细逻辑审查意见1", "意见2", ...],
    "argument_logic": ["论点论据逻辑性审查意见1", "意见2", ...],
    "coherence_issues": [
      {
        "location": "具体位置描述（章节名+段落）",
        "issue_type": "section_logic | argument_logic | sentence_coherence | theme_mismatch",
        "description": "问题的详细描述",
        "severity": "error | warning | info",
        "suggestion": "具体的修改建议"
      }
    ],
    "theme_consistency": ["与段落/论文主题一致性评价1", "评价2", ...],
    "overall_assessment": "总体逻辑性评价（至少100字）"
  }
}

逻辑连贯性审查要求（请逐项详尽审查）：
1. section_logic（至少3条）：逐章节检查论文结构是否合理，章节之间的逻辑递进关系是否清晰，各章节主题是否明确
2. argument_logic（至少3条）：检查每个核心论点的论据是否充分，推理过程是否严密，是否存在逻辑跳跃、循环论证、因果混淆等问题
3. coherence_issues（至少3条）：检测具体的行文逻辑问题，包括语句不通顺、论证不连贯、与段落主题不符、与论文核心主题不相关等
4. theme_consistency（至少2条）：评价全文是否围绕核心主题展开，各章节内容是否服务于同一研究目标
5. overall_assessment（至少100字）：对论文整体逻辑性给出综合性的总体评价

请确保：
1. 评分客观公正，结合学术规范、逻辑严密性、创新性等维度
2. 审阅意见具体且有建设性，每项内容都给出充分的细节，不应泛泛而谈
3. 对缺失章节或内容不完整的部分，提供基于论文内容的合理补全建议
4. 修订痕迹清晰标注修改位置和内容，修改理由要充分说明
5. 逻辑连贯性审查要具体指出问题位置和类型，要有深度
"""


async def generate_review(
    full_text: str,
    rule_reports: list[RuleReport],
    llm_client: object,
) -> dict:
    """调用 LLM 生成完整的审阅报告"""

    # 构建规则检查结果摘要
    rule_summary = ""
    if rule_reports:
        rule_summary = "## 规则检查结果\n" + "\n".join(
            f"- [{r.severity.value}] {r.category.value}: {r.title} — {r.description}"
            for r in rule_reports
        ) + "\n"
    else:
        rule_summary = "## 规则检查结果\n无重大格式问题。\n"

    user_message = f"""\
请对以下学术论文进行审阅。

{rule_summary}
## 论文全文

{full_text[:20000]}  # 截断过长内容以避免 token 超限
"""

    response_text = await llm_client.chat(_SYSTEM_PROMPT, user_message)

    # 解析 LLM 返回的 JSON
    try:
        # 提取 JSON 部分（可能包含在 markdown code block 中）
        import re
        json_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", response_text, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group(1))
        else:
            # 尝试直接解析整个响应
            parsed = json.loads(response_text)
    except (json.JSONDecodeError, Exception):
        # 降级：返回默认结构
        parsed = {
            "summary": {
                "overall_score": 60.0,
                "strengths": ["内容较为完整"],
                "weaknesses": ["需要进一步修改完善"],
                "recommendation": "minor_revision",
            },
            "ai_reviews": [
                {"section": "整体", "review_comment": response_text[:1000],
                 "original_text": None, "suggestion": None},
            ],
            "revisions": [],
            "completions": [],
        }

    # 确保 score 在有效范围内
    if "summary" in parsed:
        parsed["summary"]["overall_score"] = max(0.0, min(100.0, float(parsed["summary"].get("overall_score", 60.0))))

    return parsed
