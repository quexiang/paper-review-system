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
    """从论文文本中提取带层级结构的章节"""
    lines = text.split("\n")
    sections: list[dict] = []
    current: Optional[dict] = None

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        # 检测 ATX style 标题 (## Header)
        level_match = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if level_match and len(level_match.group(1)) <= 2:
            if current:
                sections.append(current)
            current = {
                "title": level_match.group(2).strip(),
                "level": min(len(level_match.group(1)), 3),
                "content": "",
                "start_offset": sum(len(l) + 1 for l in lines[:idx]),
            }
            continue

        # 检测中文编号标题 (一、 / （一）/ 第X章)
        cn_match = re.match(r"^([一二三四五六七八九十]+)[章节篇]\s*[,.，。、：:]?\s*(.*)$", stripped)
        if cn_match:
            full_title = cn_match.group(1) + cn_match.group(2).strip() if cn_match.group(2) else cn_match.group(1)
            if current:
                sections.append(current)
            current = {
                "title": full_title,
                "level": 1,
                "content": "",
                "start_offset": sum(len(l) + 1 for l in lines[:idx]),
            }
            continue

        # 累积内容
        if current is not None:
            current["content"] += stripped + "\n"

    if current is not None:
        sections.append(current)

    return [SectionInfo(**s) for s in sections]


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
