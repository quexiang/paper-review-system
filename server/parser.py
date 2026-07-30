"""文档解析器 - 支持 PDF/DOCX/MD 格式的文本和结构提取"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from models import SectionInfo


def parse_text(text: str) -> dict:
    """从纯文本论文中提取章节结构和统计信息"""
    sections = extract_sections(text)
    word_count = len(text.split())

    return {
        "sections": [s.model_dump() for s in sections],
        "full_text": text,
        "word_count": word_count,
        "page_count": max(1, word_count // 500),
        "metadata": {
            "paragraphs": len([p for p in text.split("\n\n") if p.strip()]),
            "lines": len(text.split("\n")),
        },
    }


def extract_sections(text: str) -> list[SectionInfo]:
    """
    从学术论文文本中提取章节结构（专为双栏PDF优化）。
    只识别标准的章节标题，避免误判。
    """
    lines = text.split("\n")
    sections = []
    current = None
    current_content = []

    # 学术论文常见章节关键词（中英文）
    title_keywords = [
        "abstract", "摘要",
        "introduction", "引言", "绪论",
        "related work", "文献综述",
        "methodology", "methods", "方法", "研究方法",
        "experiments", "results", "实验", "结果",
        "discussion", "讨论",
        "conclusion", "结论", "总结",
        "acknowledgements", "致谢",
        "references", "参考文献"
    ]

    def is_title_line(line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return False

        # 条件1：数字编号标题（如 "1. Introduction" 或 "2.1 Methods"）
        num_match = re.match(r'^(\d+(?:\.\d+)*)\s+(.+)$', stripped)
        if num_match:
            title_text = num_match.group(2).strip()
            # 标题长度合理（≤ 80）且不包含句号、问号等
            if len(stripped) <= 80 and not any(c in title_text for c in '.。？?;；'):
                return True

        # 条件2：纯关键词标题（如 "Abstract"）
        lower_stripped = stripped.lower()
        # 必须整个词匹配，且长度不超过 40
        if len(stripped) <= 40:
            # 检查是否以关键词开头，或者完全等于关键词
            for kw in title_keywords:
                # 匹配该行以关键词开头（忽略大小写）
                if lower_stripped.startswith(kw) and len(kw) >= 4:
                    # 确保关键词后没有多余字符（或只有冒号/空格）
                    suffix = lower_stripped[len(kw):].strip()
                    if not suffix or suffix in [':', '：']:
                        return True
                # 也允许完全等于关键词（如 "Abstract"）
                if lower_stripped == kw:
                    return True
        return False

    for line in lines:
        stripped = line.strip()
        if is_title_line(stripped):
            # 保存上一个章节
            if current is not None:
                content = "\n".join(current_content).strip()
                current["content"] = content
                current["end_offset"] = len(text)  # 暂用占位
                sections.append(SectionInfo(**current))
            # 开启新章节
            current = {
                "title": stripped,
                "level": 1,  # 默认为一级标题，可根据编号细化（可选）
                "content": "",
                "start_offset": len(text)  # 后续精确计算
            }
            current_content = []
        else:
            # 累积正文
            current_content.append(line)

    # 保存最后一个章节
    if current is not None:
        current["content"] = "\n".join(current_content).strip()
        sections.append(SectionInfo(**current))

    # 如果完全没有识别到章节，fallback 到之前的逻辑（确保兼容性）
    if not sections:
        # 这里可以调用旧的实现，或者直接返回一个包含全文的章节
        sections = [SectionInfo(
            title="全文",
            level=1,
            content=text,
            start_offset=0,
            end_offset=len(text)
        )]

    # 更新偏移量（可选，用于高亮等）
    offset = 0
    for sec in sections:
        # 简化：用 content 长度估算，更精确的偏移需要重新扫描
        pass

    return sections


def detect_missing_sections(text: str) -> list[str]:
    """检测论文中缺失的标准学术论文章节"""
    mapping = {
        "摘要": ["摘要", "abstract"],
        "关键词": ["关键词", "key word", "keyword"],
        "引言": ["引言", "绪论", "introduction"],
        "文献综述": ["文献综述", "literature review", "related work"],
        "研究方法": ["研究方法", "methodology", "methods"],
        "实验结果": ["实验结果", "results", "experiment"],
        "讨论": ["讨论", "discussion"],
        "结论": ["结论", "conclusion"],
        "参考文献": ["参考文献", "reference"],
        "附录": ["附录", "appendix"],
    }

    full_lower = text.lower()
    missing = []
    for section_name, keywords in mapping.items():
        if not any(kw in full_lower for kw in keywords):
            missing.append(section_name)

    return missing
