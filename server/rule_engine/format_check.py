"""格式规范检查 - 仅保留关键性问题检测"""

from __future__ import annotations

import re

from models import RuleReport, Severity, RuleCategory


def check_format(full_text: str) -> list[RuleReport]:
    """检测关键性的格式问题"""
    reports = []
    lines = full_text.split("\n")

    # 1. 检测超长段落（>80行：严重影响可读性）
    paragraphs = full_text.split("\n\n")
    for i, para in enumerate(paragraphs):
        if len(para.strip().split("\n")) > 80:
            reports.append(RuleReport(
                category=RuleCategory.format,
                severity=Severity.warning,
                title="段落过长",
                description=f"第{i+1}个段落超过80行，严重影响可读性，建议分段",
            ))

    return reports
