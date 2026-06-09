"""引用检查 - 检测文中引用与参考文献列表的匹配情况"""

from __future__ import annotations

import re

from models import RuleReport, Severity, RuleCategory


def check_citations(full_text: str) -> list[RuleReport]:
    """检查文中引用是否与参考文献对应"""
    reports = []
    text_lower = full_text.lower()

    # 检测是否有参考文献部分
    has_references = any(kw in text_lower for kw in ["参考文献", "reference", "bibliography"])
    if not has_references:
        return reports

    # 提取参考文献条目
    ref_section_match = re.search(r"(?:参考文献|reference|bibliography)\s*\n((?:.*\n)*?)(?:附录|致谢|\Z)", full_text, re.IGNORECASE)
    references = []
    if ref_section_match:
        ref_block = ref_section_match.group(1)
        # 尝试匹配 [1], [2] 等格式或数字编号
        references = re.findall(r"\[?(\d+)\]?\.", ref_block)

    # 提取文中引用标记
    inline_citations = re.findall(r"\[(\d+)\]", full_text)
    chinese_citations = re.findall(r"（(\d+)）", full_text)

    all_inline = set(inline_citations + chinese_citations)
    ref_nums = set(references)

    if not ref_nums:
        reports.append(RuleReport(
            category=RuleCategory.citation,
            severity=Severity.warning,
            title="参考文献格式不明",
            description="参考文献列表未检测到标准编号格式（如 [1]、[2]）",
            suggestion="使用数字编号格式标注参考文献，例如：\n[1] 作者. 标题. 期刊, 年份.\n[2] 作者. 书名. 出版社, 年份.",
        ))
        return reports

    # 检查是否有文中引用但不在参考文献中
    unmatched = all_inline - ref_nums
    if unmatched:
        reports.append(RuleReport(
            category=RuleCategory.citation,
            severity=Severity.warning,
            title="引用编号不匹配",
            description=f"发现 {len(unmatched)} 处文中引用编号不在参考文献列表中",
            suggestion="请检查引用编号的一致性。",
        ))

    # 检查是否有参考文献但未在文中引用
    if ref_nums - all_inline:
        unused = ref_nums - all_inline
        reports.append(RuleReport(
            category=RuleCategory.citation,
            severity=Severity.info,
            title="存在未引用的参考文献",
            description=f"有 {len(unused)} 条参考文献未在正文中引用",
            suggestion="请在正文中添加对应引用，或删除不必要的参考文献。",
        ))

    return reports
