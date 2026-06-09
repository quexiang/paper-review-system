"""章节完整性检查 - 检测论文是否缺少必要章节"""

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
    """检查论文是否包含所有必要的论文章节"""
    reports = []
    text_lower = full_text.lower()

    for section_name, keywords in REQUIRED_SECTIONS.items():
        found = any(kw.lower() in text_lower for kw in keywords)
        if not found:
            reports.append(RuleReport(
                category=RuleCategory.section,
                severity=Severity.error,
                title=f"缺少章节：{section_name}",
                description=f"论文未包含「{section_name}」部分",
                suggestion=f"请添加「{section_name}」章节，确保内容完整。",
            ))

    return reports


def analyze_section_balance(sections_info: list[dict]) -> list[RuleReport]:
    """分析各章节篇幅是否合理"""
    reports = []
    if len(sections_info) < 3:
        return reports

    content_lengths = [len(s.get("content", "")) for s in sections_info]
    avg_len = sum(content_lengths) / len(content_lengths) if content_lengths else 0
    total_words = sum(content_lengths)

    for i, section in enumerate(sections_info):
        length = content_lengths[i]
        # 检测过短章节（< 50字）
        if length < 50 and section.get("title", ""):
            reports.append(RuleReport(
                category=RuleCategory.section,
                severity=Severity.warning,
                title=f"章节「{section['title']}」内容过短",
                description=f"当前仅 {length} 字，建议至少 200 字",
                suggestion="扩展该章节的内容，提供足够的论证或说明。",
            ))
        # 检测过长章节（> 总篇幅60%）
        elif total_words > 0 and length / total_words > 0.6:
            reports.append(RuleReport(
                category=RuleCategory.section,
                severity=Severity.warning,
                title=f"章节「{section['title']}」篇幅过长",
                description=f"占全文 {length/total_words*100:.1f}%，建议合理分配篇幅",
            ))

    return reports
