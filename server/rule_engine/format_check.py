"""格式规范检查 - 检测论文排版、标点等格式问题"""

from __future__ import annotations

import re

from models import RuleReport, Severity, RuleCategory


def check_format(full_text: str) -> list[RuleReport]:
    """全面格式检查"""
    reports = []
    lines = full_text.split("\n")

    # 1. 检测连续标点重复（如。。。）
    for i, line in enumerate(lines):
        if re.search(r"([,.!?；：。、])\1{2,}", line):
            reports.append(RuleReport(
                category=RuleCategory.format,
                severity=Severity.warning,
                title="标点重复",
                description=f"第{i+1}行发现连续相同标点符号",
                suggestion="删除多余的标点符号。",
                location=f"第{i+1}行",
            ))

    # 2. 检测中英文混排空格问题
    for i, line in enumerate(lines):
        if re.search(r"[a-zA-Z][一-鿿]", line) or re.search(r"[一-鿿][a-zA-Z]", line):
            reports.append(RuleReport(
                category=RuleCategory.format,
                severity=Severity.info,
                title="中英文混排提示",
                description=f"第{i+1}行中英文之间建议添加空格",
                suggestion="在中文字符和英文字符之间插入一个空格。",
                location=f"第{i+1}行",
            ))

    # 3. 检测超长段落（>50行）
    paragraphs = full_text.split("\n\n")
    for i, para in enumerate(paragraphs):
        if len(para.strip().split("\n")) > 50:
            reports.append(RuleReport(
                category=RuleCategory.format,
                severity=Severity.warning,
                title="段落过长",
                description=f"第{i+1}个段落超过50行，建议分段",
            ))

    # 4. 检测标题格式（不应以正文格式出现）
    headers = [l.strip() for l in lines if re.match(r"^#{1,6}\s+", l)]
    chinese_headers = [l.strip() for l in lines if re.match(r"^[一二三四五六七八九十]+[章节篇]", l)]
    total_lines = max(len(lines), 1)

    if len(headers) + len(chinese_headers) < total_lines * 0.05 and total_lines > 20:
        reports.append(RuleReport(
            category=RuleCategory.format,
            severity=Severity.warning,
            title="标题结构不明显",
            description=f"全文{total_lines}行仅有{len(headers)+len(chinese_headers)}个显式标题",
            suggestion="建议使用Markdown标题语法（#）或中文编号格式标注章节标题。",
        ))

    return reports
