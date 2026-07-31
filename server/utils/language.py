"""语言检测工具 — 判断论文稿件是中文还是英文"""

from __future__ import annotations

import re


def is_english_text(text: str, threshold: float = 0.15) -> bool:
    """判断文本是否为英文稿件。

    方法：统计中文字符占比。如果中文字符占比低于 threshold，则认为是英文。
    阈值 0.15 允许少量中文摘要/关键词存在（英文论文常带中文摘要）。

    Args:
        text: 原始文本
        threshold: 中文占比阈值，默认 0.15（15%）

    Returns:
        True 如果判断为英文稿件，否则 False
    """
    cjk_count = len(re.findall(r'[一-鿿]', text))
    # 总字符数（排除换行和空白）
    total = len(text.replace('\n', '').replace(' ', '').replace('\r', ''))
    if total == 0:
        return False
    return (cjk_count / total) < threshold


def detect_language(text: str) -> str:
    """检测文本主要语言。

    Returns:
        "en" 如果为英文，"zh" 如果为中文
    """
    return "en" if is_english_text(text) else "zh"
