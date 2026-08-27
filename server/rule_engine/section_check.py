"""章节完整性检查 - 仅保留关键性问题检测"""

from __future__ import annotations

import re

from models import RuleReport, Severity, RuleCategory


# 标准论文章节要求（中英文）
REQUIRED_SECTIONS = {
    "摘要": ["摘要", "abstract"],
    "关键词": ["关键词", "key word", "keyword"],
    "引言": ["引言", "绪论", "introduction"],
    "相关工作": ["文献综述", "literature review", "related work"],
    "方法": ["研究方法", "methodology", "methods", "method"],
    "实验/结果": ["实验结果", "results", "experiment", "evaluation"],
    "讨论": ["讨论", "discussion"],
    "结论": ["结论", "conclusion"],
    "参考文献": ["参考文献", "reference", "bibliography"],
}


def check_sections(full_text: str) -> list[RuleReport]:
    """检查论文是否包含所有必要的论文章节（仅报告缺失的关键章节）"""
    reports = []
    text_lower = full_text.lower()

    for section_name, keywords in REQUIRED_SECTIONS.items():
        found = any(kw.lower() in text_lower for kw in keywords)
        if not found:
            reports.append(RuleReport(
                category=RuleCategory.section,
                severity=Severity.info,
                title=f"可能缺少章节：{section_name}",
                description=f"论文中未检测到「{section_name}」部分",
                suggestion=f"如需完整论文结构，请添加「{section_name}」章节。",
            ))

    return reports


def analyze_section_balance(sections_info: list[dict]) -> list[RuleReport]:
    """分析各章节篇幅是否合理（放宽标准，仅报告极端情况）"""
    reports = []
    if len(sections_info) < 3:
        return reports

    content_lengths = [len(s.get("content", "")) for s in sections_info]
    total_words = sum(content_lengths)

    for i, section in enumerate(sections_info):
        length = content_lengths[i]
        title = section.get("title", "")
        # 仅报告极短的章节（< 20字，可能只是空标题）
        if length < 20 and title:
            reports.append(RuleReport(
                category=RuleCategory.section,
                severity=Severity.warning,
                title=f"章节「{title}」内容过短",
                description=f"当前仅 {length} 字，可能是空标题或占位符",
                suggestion="请填写该章节内容，或删除空标题。",
            ))
        # 报告极端不平衡的章节（> 总篇幅80%）
        elif total_words > 0 and length / total_words > 0.8:
            reports.append(RuleReport(
                category=RuleCategory.section,
                severity=Severity.info,
                title=f"章节「{title}」篇幅占比过高",
                description=f"占全文 {length/total_words*100:.1f}%，建议检查章节划分是否合理",
            ))

    return reports
