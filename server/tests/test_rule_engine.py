"""单元测试 — 规则检查"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(__file__) + "/..")

from rule_engine.section_check import check_sections, analyze_section_balance
from rule_engine.format_check import check_format
from rule_engine.citation_check import check_citations


class TestCheckSections:
    def test_all_sections_present(self):
        # 使用 REQUIRED_SECTIONS 中定义的 keywords 匹配
        text = """摘要
这是一篇完整的论文。

关键词
keyword1

引言
介绍背景。

文献综述
综述相关工作。

研究方法
描述方法。

实验结果
展示数据。

讨论
讨论分析。

结论
总结全文。

参考文献
[1] 作者. 标题. 2024.
"""
        result = check_sections(text)
        assert len(result) == 0

    def test_missing_sections(self):
        text = "这是一篇没有标准章节的文本。"
        result = check_sections(text)
        assert len(result) > 0
        assert all(r.title.startswith("缺少章节：") for r in result)
        assert all(r.severity.value == "error" for r in result)

    def test_english_sections(self):
        text = """Abstract
This is an abstract.

Keywords
keyword1, keyword2

Introduction
This is an introduction.

Literature Review
Related work section.

Methods
This is the method.

Experiments
Experimental results.

Discussion
Discussion of results.

Conclusion
This is the conclusion.

References
1. Author. Title. 2024.
"""
        result = check_sections(text)
        assert len(result) == 0


class TestAnalyzeSectionBalance:
    def test_extreme_imbalance(self):
        sections = [
            {"title": "引言", "content": "A" * 100},
            {"title": "方法", "content": "B" * 10},
            {"title": "结论", "content": "C" * 10},
        ]
        result = analyze_section_balance(sections)
        assert any("篇幅占比过高" in r.title for r in result)

    def test_normal_balance(self):
        sections = [
            {"title": "引言", "content": "A" * 300},
            {"title": "方法", "content": "B" * 300},
            {"title": "结论", "content": "C" * 300},
        ]
        result = analyze_section_balance(sections)
        assert len(result) == 0

    def test_short_section(self):
        # 需要至少 3 个章节才能触发检查
        sections = [
            {"title": "引言", "content": "A" * 300},
            {"title": "方法", "content": "AB"},
            {"title": "结论", "content": "C" * 300},
        ]
        result = analyze_section_balance(sections)
        assert any("内容过短" in r.title for r in result)


class TestCheckFormat:
    def test_long_paragraph(self):
        lines = ["这是段落内容。"] * 100
        text = "\n".join(lines) + "\n\n" + "短段落。"
        result = check_format(text)
        assert any("段落过长" in r.title for r in result)

    def test_normal_format(self):
        text = "第一段内容。\n\n第二段内容。\n\n第三段内容。"
        result = check_format(text)
        assert len(result) == 0


class TestCheckCitations:
    def test_matching_citations(self):
        # 参考文献格式使用 "1. 作者" 以匹配正则 \[?(\d+)\]?\.(
        text = """正文中引用了 [1] 和 [2]。

参考文献
1. 作者A. 标题A. 2024.
2. 作者B. 标题B. 2024.
"""
        result = check_citations(text)
        unmatched = [r for r in result if "引用编号不匹配" in r.title]
        assert len(unmatched) == 0

    def test_no_reference_section(self):
        text = "正文引用了[1]。"
        result = check_citations(text)
        assert len(result) == 0
