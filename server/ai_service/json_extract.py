"""Shared JSON extraction with thinking-stripping and truncation recovery."""

from __future__ import annotations

import json
import re


def _strip_thinking(raw: str) -> str:
    """Remove thinking/reasoning text that LLMs often prepend to JSON output.

    Handles patterns like:
    - Here's a thinking process: ...
    - Thinking Process: ...
    - Reasoning: ...
    """
    s = raw
    # Pattern: "Here's a thinking process:" / "Thinking Process:" / "Reasoning:"
    # followed by newline + numbered items
    m = re.match(
        r'(?:Here.*thinking\s+process|Thinking\s+Process|Reasoning)[:\s]+',
        s, re.IGNORECASE,
    )
    if m:
        s = s[m.end():].lstrip('\n')

    return s


def _find_json_end(text: str, start: int) -> int:
    """Given text and the index of the opening '{' at *start*, return the index of the matching '}'."""
    depth = 0
    in_string = False
    escape_next = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape_next:
            escape_next = False
            continue
        if ch == '\\':
            escape_next = True
            continue
        if in_string:
            if ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return i
    return -1


def _fix_truncated_json(raw: str) -> str:
    """Attempt to repair a JSON string that was cut off mid-token (truncated by max_tokens)."""
    s = raw.strip()

    # Find the last valid position before depth goes negative
    depth = 0
    in_string = False
    escape_next = False
    last_valid_end = len(s)
    for i, ch in enumerate(s):
        if escape_next:
            escape_next = False
            continue
        if ch == '\\':
            escape_next = True
            continue
        if in_string:
            if ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == '{' or ch == '[':
            depth += 1
        elif ch == '}' or ch == ']':
            depth -= 1
            if depth < 0:
                last_valid_end = i
                depth = 0
                break

    if depth > 0:
        s = s[:last_valid_end]
        # Add closing braces for each unclosed opener
        ob = s.count('{') - s.count('}')
        cb = s.count('[') - s.count(']')
        s += '}' * ob + ']' * cb

    # Fix unclosed string at end
    if s and s[-1] != '"':
        i = len(s) - 1
        while i >= 0 and s[i] != '"':
            i -= 1
        if i >= 0:
            s = s[:i] + '"}'
            ob = s.count('{') - s.count('}')
            cb = s.count('[') - s.count(']')
            s += '}' * ob + ']' * cb

    return s


def _extract_raw(raw: str) -> str:
    """Extract the first JSON-like substring from *raw*.

    Strategy:
      1. ```json … ``` code block
      2. ``` … ``` code block
      3. Strip thinking text → brace-matched {…}
      4. Fall back to whole raw
    """
    # 1. Markdown code block
    m = re.search(r'```(?:json)?\s*\n(.*?)\n```', raw, re.DOTALL)
    if m:
        return m.group(1)

    # 2. Generic code block
    m = re.search(r'```\s*\n(.*?)\n```', raw, re.DOTALL)
    if m:
        return m.group(1)

    # 3. Strip thinking text, then brace-match
    cleaned = _strip_thinking(raw)
    b_start = cleaned.find("{")
    if b_start >= 0:
        b_end = _find_json_end(cleaned, b_start)
        if b_end > b_start:
            return cleaned[b_start : b_end + 1]

    # 4. Final fallback (will likely fail downstream)
    return raw


def extract_json(raw: str, default: dict | None = None) -> dict:
    """Extract and parse JSON from raw LLM response, with thinking-stripping and truncation recovery.

    Args:
        raw: Raw LLM response text (may contain thinking, markdown, etc.)
        default: Fallback dict if parsing fails entirely.

    Returns:
        Parsed dict. On complete failure returns *default* or empty dict.
    """
    extracted = _extract_raw(raw)

    # Clean trailing commas (common LLM artifact)
    extracted = re.sub(r',\s*}', '}', extracted)
    extracted = re.sub(r',\s*]', ']', extracted)

    # Try parse
    try:
        return json.loads(extracted)
    except json.JSONDecodeError:
        pass

    # Try fix truncation
    try:
        fixed = _fix_truncated_json(extracted)
        return json.loads(fixed)
    except (json.JSONDecodeError, Exception):
        pass

    # Final fallback
    return default or {}
