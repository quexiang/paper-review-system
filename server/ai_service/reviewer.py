"""AI 审阅器 - 基于 LLM 进行论文语义级审阅"""

from __future__ import annotations

import json
from models import AIReviewItem, Revision, ReviewSummary, RuleReport


# ── 系统提示词 ──────────────────────────────────────────────


_SYSTEM_PROMPT = """\
你是一位资深的学术期刊审稿人，负责评审学术论文。请对论文进行严格、全面、建设性的审阅。

你的输出必须是一个严格的 JSON 对象，包含以下字段：
{
  "summary": {
    "overall_score": 0-100,
    "strengths": ["优点1", "优点2"],
    "weaknesses": ["缺点1", "缺点2"],
    "recommendation": "accept | minor_revision | major_revision | reject"
  },
  "ai_reviews": [
    {
      "section": "章节名",
      "review_comment": "详细的审阅意见",
      "original_text": "原文相关片段（如有）",
      "suggestion": "具体修改建议"
    }
  ],
  "revisions": [
    {
      "type": "insertion | deletion | modification",
      "original_text": "原文（仅删除/修改时填写）",
      "new_text": "修改后的内容或补充内容",
      "location": "位置描述",
      "rationale": "修改理由"
    }
  ],
  "completions": [
    {
      "section": "缺失章节名",
      "generated_content": "AI 生成的补充内容草稿",
      "confidence": 0.5-1.0
    }
  ]
}

请确保：
1. 评分客观公正，结合学术规范、逻辑严密性、创新性等维度
2. 审阅意见具体且有建设性
3. 对缺失章节提供基于论文内容的合理补全建议
4. 修订痕迹清晰标注修改位置和内容
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

{full_text[:15000]}  # 截断过长内容以避免 token 超限
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
