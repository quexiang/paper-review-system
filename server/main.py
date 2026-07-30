"""FastAPI 主入口 — 论文审稿系统 API"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()  # 加载 .env 文件，使 OPENAI_API_KEY 等环境变量生效

from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from openai import AsyncOpenAI
import pypdfium2 as pdfium

from models import (
    AIReviewItem,
    CompletionReport,
    CompletionItem,
    HistoryRecord,
    LogicalReview,
    CoherenceIssue,
    ParsedDocument,
    ReviewSummary,
    Revision,
    RuleReport,
)
from ai_service.polisher import polish_paper as _polish_paper
from ai_service.lit_review import generate_literature_review as _gen_lit_review
from parser import parse_text, detect_missing_sections, extract_sections
from rule_engine.section_check import check_sections, analyze_section_balance
from rule_engine.format_check import check_format
from rule_engine.citation_check import check_citations

# 在全局状态区域添加
_models_cache: list[dict] | None = None  # 缓存模型列表
_models_cache_time: float = 0.0          # 缓存时间戳

# ── 已知模型列表（静态 + Ollama 发现）──────────────────────

_KNOWN_MODELS: list[str] = [
    "claude-sonnet-4-5-20251001",
    "claude-opus-4-5-20251001",
    "claude-haiku-4-5-20251001",
]

# 自定义模型端点（非默认 base_url 的模型）
# API key 优先从环境变量 LAN_MODEL_API_KEY 读取
_LAN_KEY = os.getenv("LAN_MODEL_API_KEY", "sk-litellmXa304304")
_LAN_URL = "http://59.79.241.152:7000/v1"
_CUSTOM_ENDPOINTS: dict[str, tuple[str, str]] = {
    "claude-sonnet-4-5-20251001": (_LAN_URL, _LAN_KEY),
    "claude-opus-4-5-20251001":   (_LAN_URL, _LAN_KEY),
    "claude-haiku-4-5-20251001":  (_LAN_URL, _LAN_KEY),
}

def _discover_ollama_models() -> list[str]:
    """从 Ollama 发现可用模型，与已知模型列表合并"""
    import urllib.request
    try:
        resp = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        data = resp.read().decode("utf-8")
        models = [m["name"] for m in json.loads(data).get("models", [])]
        seen: set[str] = set()
        result: list[str] = []
        for m in (models + _KNOWN_MODELS):
            if m not in seen:
                seen.add(m)
                result.append(m)
        return result
    except Exception:
        return list(_KNOWN_MODELS)


def _get_available_models(force_refresh: bool = False) -> list[dict]:
    """返回可用模型列表（带缓存，缓存有效期 5 分钟）"""
    import time
    global _models_cache, _models_cache_time
    now = time.time()
    if not force_refresh and _models_cache is not None and (now - _models_cache_time) < 300:
        return _models_cache

    descriptions = {
        "claude-sonnet-4-5-20251001": "Claude Sonnet 4.5（局域网，深度推理）",
        "claude-opus-4-5-20251001": "Claude Opus 4.5（局域网，最强推理）",
        "claude-haiku-4-5-20251001": "Claude Haiku 4.5（局域网，极速响应）",
    }
    models = _discover_ollama_models()
    result = [{"name": m, "desc": descriptions.get(m, f"模型 {m}")} for m in models]
    _models_cache = result
    _models_cache_time = now
    return result


def _create_llm(model_name: str | None = None) -> AsyncOpenAI:
    """根据模型名创建对应的 LLM 客户端（支持自定义端点）"""
    target_model = model_name or os.getenv("MODEL_NAME", "gpt-4o")

    # 自定义端点模型：使用独立 API 地址和 key
    if target_model in _CUSTOM_ENDPOINTS:
        endpoint, api_key = _CUSTOM_ENDPOINTS[target_model]
        client = AsyncOpenAI(api_key=api_key, base_url=endpoint)
        client._model = target_model  # type: ignore
        return client

    client = AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY", ""),
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    )
    client._model = target_model  # type: ignore
    return client


# ── 全局状态 ───────────────────────────────────────────

_history: list[HistoryRecord] = []
_reports: dict[str, CompletionReport] = {}  # 存储完整报告供下载
_original_texts: dict[str, str] = {}         # 存储原始论文文本
_journals: dict[str, list[dict]] = {}         # 存储 LLM 推荐的期刊
_models_used: dict[str, str] = {}              # 存储每个审稿使用的大模型名称

#PDF解析函数
def _extract_pdf_text(raw_bytes: bytes) -> str:
    """用 pypdfium2 从 PDF 提取纯文本（兼容 v3/v4/v5），并清理特殊字符"""
    import pypdfium2 as pdfium
    import re

    doc = pdfium.PdfDocument(raw_bytes)
    text_parts: list[str] = []
    for page in doc:
        page_text = ""
        try:
            textpage = page.get_textpage()
            n_chars = textpage.count_chars()
            if n_chars > 0:
                page_text = textpage.get_text_range(index=0, count=n_chars)
            textpage.close()
        except AttributeError:
            try:
                page_text = page.get_text()
            except AttributeError:
                page_text = page.get_textb().decode("utf-8", errors="replace")
        if page_text.strip():
            text_parts.append(page_text)
    doc.close()

    full_text = "\n".join(text_parts)

    # ── 🆕 PDF 文本预处理：移除可能导致问题的特殊字符 ──
    def clean_pdf_text(text: str) -> str:
        # 移除软连字符（PDF 断词标记）
        text = text.replace('\xad', '')
        # 移除零宽空格、零宽连接符等不可见字符
        text = re.sub(r'[\u200B-\u200F\u2028-\u202F\uFEFF]', '', text)
        # 移除所有控制字符（保留 \n \r \t）
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        # 压缩连续空行（保留最多两个）
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text

    return clean_pdf_text(full_text)

#DOCX 解析函数
def _extract_docx_text(raw_bytes: bytes) -> str:
    """用 python-docx 提取文本"""
    from io import BytesIO
    from docx import Document as DocxDocument
    doc = DocxDocument(BytesIO(raw_bytes))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

# ── DOCX 报告生成 ────────────────────────────────────
def _build_docx(report: CompletionReport, original_text: str, journals: list[dict] | None = None) -> bytes:
    """根据审稿报告、原始文本和 LLM 推荐的期刊生成带批注的 DOCX 文件"""
    from io import BytesIO
    from docx import Document
    from docx.shared import Inches, Pt, Cm, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    import re
    import traceback

    # ---------- 强化清洗函数 ----------
    def clean(text) -> str:
        """强力清洗，移除所有可能使 XML 崩溃的字符"""
        if text is None:
            return ""
        if not isinstance(text, str):
            text = str(text)
        # 1. 移除所有控制字符（除了 \n \r \t）
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        # 2. 移除未配对的 surrogate（会导致 XML 错误）
        text = re.sub(r'[\uD800-\uDFFF]', '', text)
        # 3. 移除零宽字符和不可见分隔符
        text = re.sub(r'[\u200B-\u200F\u2028-\u202F\uFEFF]', '', text)
        # 4. 移除其他可能导致问题的 Unicode 控制字符
        text = re.sub(r'[\uFFF0-\uFFFF]', '', text)
        # 5. 移除连续的过多换行（保留最多2个）
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text

    # ---------- 安全写入辅助函数 ----------
    def safe_add_run(paragraph, text, **kwargs):
        """安全添加 run，失败时返回空 run"""
        if not text:
            return paragraph.add_run("", **kwargs)
        try:
            return paragraph.add_run(clean(text), **kwargs)
        except Exception as e:
            print(f"[DOCX] add_run 失败: {e}")
            return paragraph.add_run("", **kwargs)

    def safe_add_paragraph(doc, text, style=None):
        """安全添加段落，失败时返回空段落"""
        if not text:
            return doc.add_paragraph()
        try:
            return doc.add_paragraph(clean(text), style=style)
        except Exception as e:
            print(f"[DOCX] add_paragraph 失败: {e}")
            # 降级：尝试分段添加
            p = doc.add_paragraph()
            for line in str(text).split('\n')[:50]:  # 最多50行
                try:
                    if line.strip():
                        p.add_run(clean(line))
                        p.add_run('\n')
                except:
                    pass
            return p

    doc = Document()

    # 页面设置
    section = doc.sections[0]
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)

    style = doc.styles['Normal']
    style.font.name = '等线'
    style.font.size = Pt(11)
    style.paragraph_format.line_spacing = 1.5

    # ── 封面 ──────────────────────────────────────────
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run('学术论文审稿报告')
    run.font.size = Pt(26)
    run.font.bold = True
    run.font.color.rgb = RGBColor(0x4F, 0x46, 0xE5)

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    safe_add_run(subtitle, f'论文：{report.file_name}')
    subtitle.runs[-1].font.size = Pt(14)
    subtitle.runs[-1].font.color.rgb = RGBColor(0x52, 0x52, 0x5B)

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = meta.add_run(clean(f'审稿时间：{report.timestamp.strftime("%Y-%m-%d %H:%M")}'))
    run.font.size = Pt(11)
    run = meta.add_run(clean(f'\n总评分数：{report.summary.overall_score:.0f} / 100'))
    run.font.size = Pt(11)

    rec_text = {
        "accept": "建议接收", "minor_revision": "小修后接收",
        "major_revision": "大修后复审", "reject": "不建议接收"
    }.get(report.summary.recommendation, report.summary.recommendation)
    run = meta.add_run(clean(f'\n审稿结论：{rec_text}'))
    run.font.size = Pt(11)

    doc.add_page_break()

    # ── 总体评价 ────────────────────────────────────
    doc.add_heading('一、总体评价', level=1)
    doc.add_heading('论文优点', level=2)
    for s in report.summary.strengths:
        safe_add_paragraph(doc, s, style='List Bullet')
    doc.add_heading('需要改进', level=2)
    for w in report.summary.weaknesses:
        safe_add_paragraph(doc, w, style='List Bullet')

    doc.add_page_break()

    # ── 规则检查结果 ────────────────────────────────
    doc.add_heading('二、规则检查结果', level=1)
    if report.rules:
        for r in report.rules:
            sev_label = {"error": "❌ 错误", "warning": "⚠️ 警告", "info": "ℹ️ 提示"}.get(r.severity.value, r.severity.value)
            cat_label = {"section": "章节", "format": "格式", "citation": "引用", "grammar": "语法"}.get(r.category.value, r.category.value)
            doc.add_heading(clean(f'{sev_label}  [{cat_label}] {r.title}'), level=3)
            safe_add_paragraph(doc, r.description)
            if r.suggestion:
                p = doc.add_paragraph()
                safe_add_run(p, f'💡 建议：{r.suggestion}')
                p.runs[-1].font.italic = True
    else:
        safe_add_paragraph(doc, '✅ 未发现规则检查问题，论文格式符合学术规范。')

    doc.add_page_break()

    # ── 逻辑连贯性审查 ────────────────────────────
    doc.add_heading('三、逻辑连贯性审查', level=1)
    if report.logical_review:
        if report.logical_review.overall_assessment:
            doc.add_heading('总体评价', level=2)
            safe_add_paragraph(doc, report.logical_review.overall_assessment)

        if report.logical_review.section_logic:
            doc.add_heading('章节与段落逻辑', level=2)
            for item in report.logical_review.section_logic:
                safe_add_paragraph(doc, item, style='List Bullet')

        if report.logical_review.argument_logic:
            doc.add_heading('论点与论据逻辑', level=2)
            for item in report.logical_review.argument_logic:
                safe_add_paragraph(doc, item, style='List Bullet')

        if report.logical_review.coherence_issues:
            doc.add_heading('检测到的逻辑问题', level=2)
            sev_label = {"error": "❌ 严重", "warning": "⚠️ 一般", "info": "ℹ️ 提示"}
            for i, ci in enumerate(report.logical_review.coherence_issues, 1):
                doc.add_heading(clean(f'{i}. {sev_label.get(ci.severity, ci.severity)} — {ci.issue_type}'), level=3)
                safe_add_paragraph(doc, f'位置：{ci.location}')
                safe_add_paragraph(doc, ci.description)
                if ci.suggestion:
                    p = doc.add_paragraph()
                    safe_add_run(p, f'💡 建议：{ci.suggestion}')
                    p.runs[-1].font.italic = True

        if report.logical_review.theme_consistency:
            doc.add_heading('主题一致性评价', level=2)
            for item in report.logical_review.theme_consistency:
                safe_add_paragraph(doc, item, style='List Bullet')
    else:
        safe_add_paragraph(doc, '暂无逻辑连贯性审查结果。')

    doc.add_page_break()

    # ── AI 审阅意见 ────────────────────────────────
    doc.add_heading('四、AI 审阅意见', level=1)
    if report.ai_reviews:
        for i, r in enumerate(report.ai_reviews, 1):
            doc.add_heading(clean(f'{i}. {r.section}'), level=2)
            safe_add_paragraph(doc, r.review_comment)
            if r.suggestion:
                p = doc.add_paragraph()
                safe_add_run(p, f'💡 {r.suggestion}')
                p.runs[-1].font.italic = True
                p.runs[-1].font.color.rgb = RGBColor(0x4F, 0x46, 0xE5)
    else:
        safe_add_paragraph(doc, '暂无 AI 审阅意见。')

    doc.add_page_break()

    # ── 修订痕迹 ────────────────────────────────────
    doc.add_heading('五、修订痕迹（修改前后对比）', level=1)
    if report.revisions:
        for i, r in enumerate(report.revisions, 1):
            rev_emoji = {"insertion": "➕ 新增", "deletion": "❌ 删除", "modification": "🔄 修改"}
            label = rev_emoji.get(r.revision_type.value, r.revision_type.value)
            doc.add_heading(clean(f'{i}. {label} — {r.location}'), level=2)

            if r.original_text:
                p = doc.add_paragraph()
                safe_add_run(p, '【原文】')
                p.runs[-1].font.bold = True
                p.runs[-1].font.color.rgb = RGBColor(0xDC, 0x26, 0x26)
                p = doc.add_paragraph()
                safe_add_run(p, r.original_text)
                if p.runs:
                    p.runs[-1].font.strike = True
                    p.runs[-1].font.color.rgb = RGBColor(0xDC, 0x26, 0x26)

            p = doc.add_paragraph()
            safe_add_run(p, '【修改后】')
            p.runs[-1].font.bold = True
            p.runs[-1].font.color.rgb = RGBColor(0x05, 0x96, 0x69)
            p = doc.add_paragraph()
            safe_add_run(p, r.new_text)
            if p.runs:
                p.runs[-1].font.color.rgb = RGBColor(0x05, 0x96, 0x69)

            if r.rationale:
                p = doc.add_paragraph()
                safe_add_run(p, f'📝 理由：{r.rationale}')
                p.runs[-1].font.italic = True
                p.runs[-1].font.size = Pt(10)
    else:
        safe_add_paragraph(doc, '暂无修订痕迹。')

    doc.add_page_break()

    # ── 自动补全 ────────────────────────────────────
    doc.add_heading('六、自动补全内容', level=1)
    if report.completions:
        for i, c in enumerate(report.completions, 1):
            doc.add_heading(clean(f'{i}. {c.section}（置信度 {c.confidence:.0%}）'), level=2)
            safe_add_paragraph(doc, c.generated_content)
    else:
        safe_add_paragraph(doc, '论文章节完整，无需补全内容。')

    doc.add_page_break()

    # ── 推荐期刊 Top 10 ───────────────────────────────
    doc.add_heading('七、推荐期刊（Top 10）', level=1)

    score = report.summary.overall_score
    if score < 50:
        note = "当前稿件得分偏低，建议进一步完善实验验证和章节内容后投稿。"
    elif score < 70:
        note = "当前稿件处于中等水平，建议加强方法描述和实验对比后冲击高影响力期刊。"
    else:
        note = "稿件质量良好，建议优先尝试CCF-A/SCI Q1期刊，同时准备1-2个备选。"

    p = doc.add_paragraph()
    safe_add_run(p, f'💡 {note}')
    if p.runs:
        p.runs[-1].font.italic = True
        p.runs[-1].font.size = Pt(10)

    used_journals = (journals or [])[:10]
    if used_journals:
        table = doc.add_table(rows=1, cols=4)
        table.style = 'Light Grid Accent 1'
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        hdr = table.rows[0].cells
        hdr[0].text = '期刊名称'
        hdr[1].text = '级别'
        hdr[2].text = '匹配度'
        hdr[3].text = '推荐理由'

        for j in used_journals:
            row = table.add_row().cells
            row[0].text = clean(str(j.get("name", "")))
            p = row[1].paragraphs[0]
            safe_add_run(p, clean(str(j.get("level", ""))))
            if p.runs:
                p.runs[-1].font.bold = True
            match_val = j.get("match", "")
            row[2].text = clean(f"{match_val}%" if isinstance(match_val, (int, float)) else str(match_val))
            row[3].text = clean(str(j.get("reason", j.get("desc", ""))))

        from docx.shared import Cm
        for row_obj in table.rows:
            row_obj.cells[0].width = Cm(4.5)
            row_obj.cells[1].width = Cm(2.5)
            row_obj.cells[2].width = Cm(1.5)
            row_obj.cells[3].width = Cm(7.5)
    else:
        safe_add_paragraph(doc, '暂无推荐期刊数据。')

    doc.add_page_break()

    # ── 论文润色 ────────────────────────────────
    doc.add_heading('八、论文润色', level=1)
    if report.polished_paper:
        safe_add_paragraph(doc, report.polished_paper)
    else:
        safe_add_paragraph(doc, '暂无论文润色结果。')

    doc.add_page_break()

    # ── 文献综述 ────────────────────────────────
    doc.add_heading('九、文献综述', level=1)
    if report.literature_review:
        safe_add_paragraph(doc, report.literature_review)
    else:
        safe_add_paragraph(doc, '暂无文献综述结果。')

    # 写入内存
    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()

def _extract_core_sections(text: str, sections: list, max_chars: int = 20000) -> str:
    """
    智能提取论文的核心章节，优先保留摘要、引言、方法、实验、结论。
    自动删除参考文献、致谢、附录等非核心内容。
    返回的文本长度不超过 max_chars。
    """
    # 章节优先级（数字越小越重要）
    priority_map = {
        "摘要": 1, "abstract": 1,
        "引言": 2, "introduction": 2, "绪论": 2,
        "背景": 2, "background": 2,
        "方法": 3, "methodology": 3, "methods": 3,
        "实验": 4, "experiment": 4,
        "结果": 4, "results": 4,
        "评估": 4, "evaluation": 4,
        "讨论": 5, "discussion": 5,
        "分析": 5, "analysis": 5,
        "结论": 1, "conclusion": 1, "总结": 1,
    }

    # 需要完全跳过的章节关键词
    skip_keywords = [
        "reference", "参考文献", "致谢", "acknowledgment",
        "appendix", "附录", "作者简介", "biography"
    ]

    # 收集并评分每个章节
    scored_sections = []
    for sec in sections:
        title_lower = sec.title.lower()
        if any(kw in title_lower for kw in skip_keywords):
            continue
        # 检查章节内容是否为空
        content = getattr(sec, 'content', '')
        if not content or len(content.strip()) < 10:
            continue
        # 计算优先级
        priority = 9
        for key, p in priority_map.items():
            if key in title_lower:
                priority = p
                break
        scored_sections.append((priority, sec))

    # 按优先级排序
    scored_sections.sort(key=lambda x: x[0])

    # 按优先级拼接，直到达到 max_chars
    result_parts = []
    total_len = 0
    for _, sec in scored_sections:
        content = getattr(sec, 'content', '')
        section_text = f"## {sec.title}\n{content}\n\n"
        if total_len + len(section_text) > max_chars:
            remaining = max_chars - total_len
            if remaining > 500:
                result_parts.append(section_text[:remaining])
            break
        result_parts.append(section_text)
        total_len += len(section_text)

    if not result_parts:
        return text[:max_chars]
    return "".join(result_parts)

# ── 新增：AI 审阅独立函数（抽离 prompt 逻辑）────────────────
async def _perform_ai_review(
    text: str,
    rules: list[RuleReport],
    llm: AsyncOpenAI,
    model: str,
    parsed: ParsedDocument,
) -> dict:
    """
    仅执行 AI 审阅，返回解析后的 JSON dict。
    失败时返回兜底提取的数据，而不是抛出异常。
    """
    rule_lines = "\n".join(f"- [{r.severity.value}] {r.title}" for r in rules) or "无规则问题"
    section_titles = [s.title for s in parsed.sections] if parsed.sections else ["（未识别到章节）"]
    core_text = _extract_core_sections(text, parsed.sections, max_chars=20000)

    prompt = f"""你是一位资深的学术期刊审稿人，擅长全面、深入地评审学术论文。请对以下论文进行详尽的审阅，返回尽可能全面、完整的审阅结果（纯 JSON，不要使用代码块）。

    ## 规则检查结果
    {rule_lines}

    ## 论文核心章节（已自动筛选，保留摘要、引言、方法、实验、结论）

    {core_text}

    ## 重要要求
    你必须返回一个完整的 JSON 对象，包含以下全部字段。每项内容都必须**详尽、具体、有深度**，不能敷衍了事或泛泛而谈。

    ### summary - 总体评价
    {{"overall_score": 0-100 整数, "strengths": ["优点1", "优点2", ...], "weaknesses": ["缺点1", "缺点2", ...], "recommendation": "accept|minor_revision|major_revision|reject"}}
    要求：strengths 至少 4 条，weaknesses 至少 4 条，每条都要具体针对论文内容。

    ### ai_reviews - 逐章节 AI 审阅意见（至少 5 条）
    每条格式：{{"section": "章节名", "review_comment": "详尽的审阅意见（≥200字）", "original_text": "原文关键片段（可选）", "suggestion": "具体的修改建议（≥50字）"}}

    ### revisions - 修订痕迹（至少 8 条）
    每条格式：{{"revision_type": "insertion|deletion|modification", "original_text": "原文（删除/修改时填写）", "new_text": "修改后的内容", "location": "位置描述", "rationale": "修改理由"}}

    ### completions - 自动补全内容（至少 2 条，如果章节完整则生成内容补充建议）
    每条格式：{{"section": "章节名", "generated_content": "补充内容草稿（≥300字）", "confidence": 0.5-0.9}}

    ### journals - 推荐期刊 Top 10
    每条格式：{{"name": "期刊/会议全称", "level": "CCF-A/B/C 或 SCI Q1/Q2/Q3", "match": "匹配度百分比", "reason": "推荐理由（≥50字）"}}

    ### logical_review - 逻辑连贯性审查
    {{
      "section_logic": ["逐章节逻辑审查意见（至少3条）"],
      "argument_logic": ["论点论据审查意见（至少3条）"],
      "coherence_issues": [
        {{"location": "位置描述", "issue_type": "section_logic|argument_logic|sentence_coherence|theme_mismatch", "description": "问题描述", "severity": "error|warning|info", "suggestion": "修改建议"}}
      ],
      "theme_consistency": ["主题一致性评价（至少2条）"],
      "overall_assessment": "总体逻辑性评价（至少150字）"
    }}

    请确保返回的是完整的、合法的 JSON 对象。不要截断 JSON。如果内容过长，请适当压缩但保持完整结构。
    """

    raw = "{}"
    try:
        print("[AI review] 开始执行AI审阅")
        model_to_use = getattr(llm, "_model", model or "gpt-4o")
        import asyncio

        # 🆕 根据模型动态设置超时时间
        if "claude" in model_to_use.lower():
            timeout_seconds = 1200.0  # Claude 需要更多时间（20 分钟）
        else:
            timeout_seconds = 900.0  # 其他模型（15 分钟）

        print(f"[AI review] 开始调用 LLM（超时 {timeout_seconds} 秒）...")
        try:
            resp = await asyncio.wait_for(
                llm.chat.completions.create(
                    model=model_to_use,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=32768,
                ),
                timeout=timeout_seconds
            )
            print("[AI review] LLM 响应已返回")
        except asyncio.TimeoutError:
            print(f"[AI review] ❌ 请求超时（{timeout_seconds} 秒）")
            raise RuntimeError(f"AI审阅超时（{timeout_seconds}秒），请检查模型服务是否正常")

        raw = resp.choices[0].message.content or "{}"
        import re as _re

        # 清洗思维链
        _think_end = raw.find('</think>')
        if _think_end >= 0:
            raw = raw[_think_end + len('</think>'):].strip()
        _think_match = _re.search(r'(Here\'s a thinking process:).*?\n\n', raw, _re.DOTALL | _re.IGNORECASE)
        if _think_match:
            raw = raw[_think_match.end():].strip()

        # 提取 JSON
        json_str = raw
        m = _re.search(r'```(?:json)?\s*\n(.*?)\n```', raw, _re.DOTALL)
        if m:
            json_str = m.group(1)
        else:
            _brace_start = raw.find('{')
            _brace_end = raw.rfind('}')
            if _brace_start >= 0 and _brace_end > _brace_start:
                json_str = raw[_brace_start:_brace_end + 1]

        # ---- 清洗函数 ----
        def clean_json(s: str) -> str:
            s = _re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', s)
            s = _re.sub(r',\s*}', '}', s)
            s = _re.sub(r',\s*]', ']', s)
            s = _re.sub(r'}\s*{', '},{', s)
            s = _re.sub(r'\]\s*\[', '],[', s)
            open_braces = s.count('{') - s.count('}')
            open_brackets = s.count('[') - s.count(']')
            if open_braces > 0:
                s += '}' * open_braces
            if open_brackets > 0:
                s += ']' * open_brackets
            return s

        json_str = clean_json(json_str)

        # ---- 兜底提取函数 ----
        def extract_from_raw_text(text: str) -> dict:
            """当 JSON 完全无法解析时，从原始文本中提取关键信息"""
            import re

            # 提取分数
            score = 60.0
            score_patterns = [
                r'(?:overall_score|整体评分|总分)[\s:]+(\d+\.?\d*)',
                r'分数[：:]\s*(\d+\.?\d*)',
                r'(\d+)分',
                r'评分[：:]\s*(\d+)',
            ]
            for pattern in score_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    score = float(match.group(1))
                    if score < 10:
                        score = score * 10
                    break
            if score < 0 or score > 100:
                score = 60.0

            # 提取优点
            strengths = []
            strength_patterns = [
                r'(?:strengths|优点|优势)[\s:]*\[(.*?)\]',
                r'优点[：:]\s*(.+?)(?=缺点|不足|局限)',
                r'1\.\s*(.+?)(?=2\.|\n)',
            ]
            for pattern in strength_patterns:
                match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
                if match:
                    items = re.split(r'[,，]\s*', match.group(1).strip())
                    strengths = [s.strip() for s in items if s.strip()]
                    break
            if not strengths:
                strengths = ["稿件结构完整", "实验设计合理"]

            # 提取缺点
            weaknesses = []
            weakness_patterns = [
                r'(?:weaknesses|缺点|不足|局限)[\s:]*\[(.*?)\]',
                r'缺点[：:]\s*(.+?)(?=优点|优势|建议)',
                r'2\.\s*(.+?)(?=3\.|\n)',
            ]
            for pattern in weakness_patterns:
                match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
                if match:
                    items = re.split(r'[,，]\s*', match.group(1).strip())
                    weaknesses = [s.strip() for s in items if s.strip()]
                    break
            if not weaknesses:
                weaknesses = ["建议补充相关工作章节", "建议完善实验对比分析"]

            if score >= 80:
                recommendation = "accept"
            elif score >= 70:
                recommendation = "minor_revision"
            else:
                recommendation = "major_revision"

            return {
                "summary": {
                    "overall_score": score,
                    "strengths": strengths[:5],
                    "weaknesses": weaknesses[:5],
                    "recommendation": recommendation,
                },
                "ai_reviews": [{
                    "section": "整体（AI审阅摘要）",
                    "review_comment": text[:4000] if text else "无法解析审阅结果",
                    "original_text": None,
                    "suggestion": "由于 JSON 解析失败，以上是从原始响应中提取的内容摘要。建议重新提交审稿或更换模型。",
                }],
                "revisions": [],
                "completions": [],
                "logical_review": None,
            }

        # ---- 尝试解析 ----
        parsed_json = None

        # 尝试1：直接解析
        try:
            parsed_json = json.loads(json_str)
            print("[AI review] JSON 解析成功（完整）")
        except json.JSONDecodeError as e:
            print(f"[AI review] 完整JSON解析失败: {e}")

        # 尝试2：strict=False
        if parsed_json is None:
            try:
                parsed_json = json.loads(json_str, strict=False)
                print("[AI review] JSON 解析成功（strict=False）")
            except json.JSONDecodeError as e:
                print(f"[AI review] strict=False 解析失败: {e}")

        # 尝试3：截断长度
        if parsed_json is None:
            for max_len in [len(json_str) // 2, len(json_str) // 4, len(json_str) // 8]:
                try:
                    parsed_json = json.loads(json_str[:max_len], strict=False)
                    print(f"[AI review] JSON 解析成功（截断到 {max_len}）")
                    break
                except json.JSONDecodeError:
                    continue

        # 尝试4：ast.literal_eval
        if parsed_json is None:
            try:
                import ast
                parsed_json = ast.literal_eval(json_str)
                print("[AI review] ast.literal_eval 解析成功")
            except Exception as e:
                print(f"[AI review] ast.literal_eval 也失败: {e}")

        # 尝试5：替换单引号
        if parsed_json is None:
            try:
                json_str_fixed = json_str.replace("'", '"')
                parsed_json = json.loads(json_str_fixed, strict=False)
                print("[AI review] 单引号替换后解析成功")
            except Exception as e:
                print(f"[AI review] 单引号替换后解析也失败: {e}")

        # ---- 所有尝试都失败 → 兜底提取 ----
        if parsed_json is None:
            print("[AI review] ⚠️ 所有解析均失败，使用兜底提取")
            parsed_json = extract_from_raw_text(json_str)

        return parsed_json

    except Exception as e:
        # 最外层异常捕获
        print(f"[AI review] 发生异常，使用兜底提取: {e}")
        try:
            return extract_from_raw_text(raw)
        except Exception:
            return {
                "summary": {
                    "overall_score": 60.0,
                    "strengths": ["稿件结构完整"],
                    "weaknesses": ["AI审阅解析失败，建议人工复审"],
                    "recommendation": "major_revision",
                },
                "ai_reviews": [{
                    "section": "整体",
                    "review_comment": "AI 审阅响应未能解析，请检查模型服务或重新提交。",
                    "suggestion": "建议检查模型 API 是否正常工作，或更换其他模型重新审稿。",
                }],
                "revisions": [],
                "completions": [],
                "logical_review": None,
            }


# ── 新增：降级兜底 JSON 构建函数 ──────────────────────────

def _build_fallback_review(text: str, parsed: ParsedDocument, rules: list[RuleReport]) -> dict:
    """当 AI 审阅失败时，生成默认的 parsed_json"""
    missing = detect_missing_sections(text)
    section_titles = [s.title for s in parsed.sections] if parsed.sections else []
    topic_clues = "、".join(section_titles[:6]) if section_titles else "未识别"

    parsed_json = {
        "summary": {
            "overall_score": 50.0 if missing else 70.0,
            "strengths": ["稿件结构基本完整", f"包含 {len(section_titles)} 个章节"],
            "weaknesses": [f"缺少以下章节：{', '.join(missing)}"] if missing else ["暂无需要改进之处"],
            "recommendation": "major_revision" if missing else "minor_revision",
        },
        "ai_reviews": [{
            "section": "整体",
            "review_comment": (
                f"【内容质量】\n稿件共 {parsed.word_count} 字，{len(parsed.sections)} 个章节"
                f"（{topic_clues}）。"
                + (f"缺失章节：{', '.join(missing)}。" if missing else "")
                + "\n\n【写作水平】\n文本整体可读，但建议进一步优化表达和逻辑连贯性。"
                "\n\n【具体问题】\n由于 LLM 审阅未能成功完成，建议人工补充审阅以下方面："
                "内容的创新性、实验设计的合理性、数据分析的准确性。"
                "\n\n【优点亮点】\n论文整体框架完整，章节划分合理。"
            ),
            "suggestion": (
                f"1. 补充缺失章节（{', '.join(missing) if missing else '无' }）\n"
                "2. 优化各章节之间的逻辑衔接\n"
                "3. 检查实验数据的完整性和准确性\n"
                "4. 完善文献综述，突出研究创新点"
            ),
        }],
        "revisions": [],
        "completions": [{
            "section": m,
            "generated_content": (
                f"【章节定位】\n「{m}」是学术论文中的核心组成部分，"
                f"对于完整呈现研究工作和说服审稿人具有关键作用。"
                f"当前稿件中缺少该章节，需要基于论文已有内容（主题：{topic_clues}）进行补充。\n\n"
                f"【核心要点】\n该章节应涵盖以下关键内容：\n"
                f"1. 与该章主题直接相关的背景阐述\n"
                f"2. 结合论文已有研究内容的深入分析\n"
                f"3. 支撑结论的关键论据和数据\n\n"
                f"【草稿正文】\n（请作者根据论文具体内容进行撰写，"
                f"建议围绕{topic_clues}等已有章节中涉及的相关内容展开，"
                f"确保与全文逻辑一致、风格统一。）"
            ),
            "confidence": 0.35,
        } for m in missing],
    }
    return parsed_json


# ── 新增：安全包装润色和综述 ──────────────────────────────
async def _safe_polish(text: str, sections: list, llm: AsyncOpenAI, model: str) -> str | None:
    """安全执行论文润色，失败返回 None"""
    try:
        print("[Polisher] 开始执行润色")
        import re

        # 1. 清洗不可见字符
        text = text.replace('\xad', '')  # 软连字符
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', text)  # 控制字符

        # 2. 定义正文行检测函数
        def is_likely_text(line: str) -> bool:
            """
            安全版：宁可放过，不可错杀。
            只有确定是图表标签（轴刻度、图例、单位标识）才返回 False。
            """
            stripped = line.strip()
            if not stripped:
                return False

            # ── 第1层：硬拦截（这些 100% 不是正文） ──

            # ① 纯数字行（坐标轴刻度：0, 5, 10, 1000...）
            if re.match(r'^[\d\s,\.]+$', stripped):
                return False

            # ② 以 # 开头的图标题/注释
            if stripped.startswith('#'):
                return False

            # ③ 纯单位标签（如 "Throughput (requests/second)" 单独一行）
            #    只拦截这种短小的、括号包裹单位的行
            if re.search(r'^[A-Za-z\s]+\([a-z]+/[a-z]+\)$', stripped):
                return False
            if re.search(r'km\^2|hours?|seconds?|requests?/s', stripped, re.I) and len(stripped) < 30:
                return False

            # ④ 明确的图表引用（Figure / Table / Fig. / Tab.）
            if re.search(r'\b(Figure|Table|Fig\.|Tab\.)\s*\d+', stripped, re.IGNORECASE):
                return False

            # ── 第2层：只要有一点“正文痕迹”，立即放行 ──

            # ① 包含中文字符（中文论文的标题/段落，放行）
            if re.search(r'[\u4e00-\u9fff]', stripped):
                return True

            # ② 句子长度 > 40 字符（大概率是完整句子，放行）
            if len(stripped) > 40:
                return True

            # ③ 包含学术关键词（动词/名词）（放行，避免误杀 "Deep Learning" 等）
            academic_keywords = [
                'analysis', 'result', 'show', 'indicate', 'demonstrate',
                'provide', 'suggest', 'approach', 'method', 'data',
                'study', 'model', 'system', 'evaluate', 'develop', 'propose',
                'learning', 'mining', 'classification', 'recognition', 'extraction',
                'framework', 'architecture', 'performance', 'evaluation', 'experiment'
            ]
            if any(kw in stripped.lower() for kw in academic_keywords):
                return True

            # ④ 行首是数字编号 + 空格 + 大写字母/中文（章节标题，放行）
            if re.match(r'^\d+\.?\s+[A-Z\u4e00-\u9fff]', stripped):
                return True

            # ⑤ 全大写短词（缩写，如 "CNN", "LLM"）但包含在句子中？单独一行不放行
            #    但如果长度 > 3 且只含大写字母，可能是缩写标题（如 "INTRODUCTION"），放行
            if stripped.isupper() and len(stripped) >= 8:
                return True

            # ── 第3层：最后才拦截明显的图例 ──

            # 拦截：2~4 个单词，全部首字母大写，长度 < 30，且不含数字和标点
            # 例如 "Point Query", "Range Query", "Centralized IM", "Replicated NetCDF"
            if re.match(r'^[A-Z][a-z]+(?: [A-Z][a-z]+){1,3}$', stripped) and len(stripped) < 30:
                return False  # 拦截

            # 兜底：如果以上都没命中，但长度 > 15，为了安全放行
            if len(stripped) > 15:
                return True

            # 实在不确定的，放行（宁可多留，也不错杀）
            return True

        # 3. 按行分割并过滤
        lines = text.split('\n')
        filtered_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            # 跳过纯数字行（坐标轴刻度）
            if re.match(r'^[\d\s,\.]+$', stripped):
                continue
            # 跳过页码行
            if re.search(r'(Page|P\.?)\s*\d+\s*(of|/)\s*\d+', stripped, re.IGNORECASE):
                continue
            # 使用正文行检测
            if not is_likely_text(line):
                continue
            filtered_lines.append(line)

        # 4. 重新拼接
        core_text = '\n'.join(filtered_lines)

        # 5. 如果过滤后内容太少，fallback 到原文截断
        if len(core_text) < 500:
            print("[Polisher] 过滤后内容过少，使用原文截断")
            core_text = text[:15000]

        # 6. 压缩多余换行
        core_text = re.sub(r'\n{3,}', '\n\n', core_text)
        core_text = core_text.strip()

        print(f"[Polisher] 输入压缩后长度: {len(core_text)} 字")

        # 7. 调用润色（传入空列表表示直接润色全文）
        return await _polish_paper(core_text, [], llm, model)
    except Exception as e:
        print(f"[Polisher] 失败: {e}", file=sys.stderr)
        return None


async def _safe_lit_review(text: str, llm: AsyncOpenAI, model: str, parsed: ParsedDocument) -> str | None:
    """安全执行文献综述，失败返回 None"""
    try:
        print("[LitReview] 开始执行文献综述")

        # 【关键】只提取核心章节，压缩到 10000 字
        core_text = _extract_core_sections(text, parsed.sections, max_chars=10000)

        # 如果提取失败（sections 为空），fallback 到截断
        if not core_text or len(core_text) < 500:
            core_text = text[:12000]
            print(f"[LitReview] 章节提取失败，使用截断: {len(core_text)} 字")
        else:
            print(f"[LitReview] 输入文本从 {len(text)} 字压缩到 {len(core_text)} 字")

        return await _gen_lit_review(core_text, llm, model)
    except Exception as e:
        print(f"[LitReview] 失败: {e}", file=sys.stderr)
        return None

# ── 审阅流程（核心改造）───────────────────────────────────

async def run_review(parsed: ParsedDocument, model_name: str | None = None) -> CompletionReport:
    """完整的审稿流程：规则检查 → 并行执行（AI审阅、润色、综述）→ 组装报告"""
    text = parsed.full_text

    # 1. 规则检查（同步，轻量）
    rules: list[RuleReport] = []
    rules.extend(check_sections(text))
    rules.extend(analyze_section_balance([s.model_dump() for s in parsed.sections]))
    rules.extend(check_format(text))
    rules.extend(check_citations(text))

    # 准备 LLM 客户端
    llm = _create_llm(model_name)
    model_to_use = getattr(llm, "_model", model_name or "gpt-4o")

    # ── 创建三个并行任务，使用信号量限制全局并发 ──
    import time
    # ── 创建三个并行任务，使用信号量限制全局并发 ──
    sem = asyncio.Semaphore(3)# 不变

    async def _limited_task(coro):  # 不变
        async with sem:
            return await coro

    # 调用方式完全一样，只是函数内部做了优化
    ai_task = _limited_task(_perform_ai_review(text, rules, llm, model_to_use, parsed))
    polish_task = _limited_task(_safe_polish(text, parsed.sections, llm, model_to_use))  # ← 这个函数内部改了
    lit_task = _limited_task(_safe_lit_review(text, llm, model_to_use, parsed))

    task_start = time.time()
    print(f"[Timer] 三个并行任务开始发起: {task_start:.2f}")

    print("[Timer] 三个任务已全部发起，等待完成...")

    # 并行执行（完全不变）
    ai_result, polished_text, lit_review_text = await asyncio.gather(
        ai_task, polish_task, lit_task,
        return_exceptions=True
    )

    elapsed = time.time() - task_start
    print(f"[Timer] 三个并行任务全部完成，总耗时: {elapsed:.2f}s")

    # ── 处理 AI 审阅结果 ────────────────────────────
    if isinstance(ai_result, Exception):
        print(f"[AI Review] 失败，使用降级数据: {ai_result}", file=sys.stderr)
        parsed_json = _build_fallback_review(text, parsed, rules)
    else:
        parsed_json = ai_result

    # ── 降级补充：如果 LLM 未返回足够的 revisions/completions/journals ──
    # 复用原有逻辑（从 rules 生成修订，从缺失章节生成补全，从引擎推荐期刊）
    def _gen_revisions_from_rules() -> list[dict]:
        revs = []
        for r in rules:
            if r.severity in ("error", "warning"):
                revs.append({
                    "revision_type": "modification",
                    "original_text": r.description,
                    "new_text": r.suggestion or f"请根据「{r.title}」的要求修改此处内容。",
                    "location": r.location or r.category.value,
                    "rationale": f"规则检查 [{r.severity.value}] {r.title}",
                })
        return revs

    def _gen_completions_from_missing() -> list[dict]:
        missing = detect_missing_sections(text)
        completions = []
        for m in missing:
            completions.append({
                "section": m,
                "generated_content": (
                    f"【章节定位】\n"
                    f"「{m}」是学术论文中的关键组成部分，对于完整呈现研究工作、"
                    f"说服审稿人和读者具有重要作用。该章节在提交稿件中缺失，需要补充。\n\n"
                    f"【核心要点】\n"
                    f"该章节应涵盖以下内容：\n"
                    f"1. 与「{m}」相关的核心概念和背景知识\n"
                    f"2. 紧密结合论文已有研究内容的深入分析和讨论\n"
                    f"3. 支撑论文结论的关键论据、数据或引用\n\n"
                    f"【草稿正文】\n"
                    f"（请作者根据论文的具体研究内容、方法和数据进行撰写，"
                    f"确保与全文在逻辑上和风格上保持一致。）"
                ),
                "confidence": 0.30,
            })
        return completions

    from journal_recommender import recommend_journals as _recommend_journals

    def _gen_journals_from_content(text: str, summary: dict) -> list[dict]:
        score = summary.get("overall_score", 60)
        return _recommend_journals(text, overall_score=float(score))

    ai_revisions = parsed_json.get("revisions", []) or []
    ai_completions = parsed_json.get("completions", []) or []
    ai_journals = parsed_json.get("journals", []) or []
    sm = parsed_json.get("summary", {})

    if len(ai_revisions) < 2:
        rule_revs = _gen_revisions_from_rules()
        existing_locs = {r.get("location", "") for r in ai_revisions if isinstance(r, dict)}
        for rr in rule_revs:
            if rr.get("location") not in existing_locs:
                ai_revisions.append(rr)
        parsed_json["revisions"] = ai_revisions

    if len(ai_completions) < 1:
        rule_completions = _gen_completions_from_missing()
        existing_secs = {c.get("section", "") for c in ai_completions if isinstance(c, dict)}
        for rc in rule_completions:
            if rc.get("section") not in existing_secs:
                ai_completions.append(rc)
        parsed_json["completions"] = ai_completions

    if len(ai_journals) < 10:
        fallback_journals = _gen_journals_from_content(text, sm)
        existing_names = {j.get("name", "") for j in ai_journals if isinstance(j, dict)}
        for fj in fallback_journals:
            if fj.get("name") not in existing_names:
                ai_journals.append(fj)
        for j in (ai_journals or []):
            if isinstance(j, dict) and isinstance(j.get("match"), (int, float)):
                j["match"] = f"{j['match']}%"
        parsed_json["journals"] = ai_journals[:10]

    # ── 组装 Report ──────────────────────────────────
    sm = parsed_json.get("summary", {})

    def _safe_parse(items, cls):
        out = []
        for r in (items or []):
            if isinstance(r, dict):
                try:
                    out.append(cls(**r))
                except Exception:
                    pass
        return out

    # 解析逻辑连贯性审查
    lr_raw = parsed_json.get("logical_review", {}) or {}
    logical_review = None
    try:
        coherence_issues = []
        for ci in (lr_raw.get("coherence_issues") or []):
            if isinstance(ci, dict):
                coherence_issues.append(CoherenceIssue(
                    location=ci.get("location", "未知位置"),
                    issue_type=ci.get("issue_type", "sentence_coherence"),
                    description=ci.get("description", ""),
                    severity=ci.get("severity", "warning"),
                    suggestion=ci.get("suggestion"),
                ))
        logical_review = LogicalReview(
            section_logic=lr_raw.get("section_logic") or [],
            argument_logic=lr_raw.get("argument_logic") or [],
            coherence_issues=coherence_issues,
            theme_consistency=lr_raw.get("theme_consistency") or [],
            overall_assessment=lr_raw.get("overall_assessment", ""),
        )
    except Exception:
        pass

    # 组装报告
    report = CompletionReport(
        file_name=parsed.file_name,
        status="completed",
        summary=ReviewSummary(
            overall_score=max(0.0, min(100.0, float(sm.get("overall_score", 60.0)))),
            strengths=list(sm.get("strengths", [])),
            weaknesses=list(sm.get("weaknesses", [])),
            recommendation=str(sm.get("recommendation", "minor_revision")),
        ),
        rules=rules,
        ai_reviews=_safe_parse(parsed_json.get("ai_reviews"), AIReviewItem),
        revisions=_safe_parse(parsed_json.get("revisions"), Revision),
        completions=_safe_parse(parsed_json.get("completions"), CompletionItem),
        logical_review=logical_review,
        polished_paper=polished_text,        # 来自并行任务
        literature_review=lit_review_text,   # 来自并行任务
    )

    # 记录历史
    _history.append(HistoryRecord(
        id=report.id,
        file_name=parsed.file_name,
        timestamp=datetime.now(timezone.utc),
        summary={"score": report.summary.overall_score, "recommendation": report.summary.recommendation},
    ))
    _reports[report.id] = report
    _original_texts[report.id] = text
    _journals[report.id] = ai_journals
    _models_used[report.id] = model_name or os.getenv("MODEL_NAME", "gpt-4o")

    return report


# ── FastAPI App ────────────────────────────────────────

@asynccontextmanager
async def _lifespan(app: FastAPI):
    yield

app = FastAPI(title="论文审稿系统", version="1.0.0", lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.get("/")
def root():
    """根路径 — 返回 API 信息"""
    return {
        "service": "学术论文审稿系统",
        "version": "1.0.0",
        "api_docs": "/docs",
        "api_health": "/api/health",
        "api_models": "/api/models",
        "api_review": "/api/review (POST)",
        "frontend": "http://localhost:3000 (Vite 开发服务器)",
    }


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "paper-review-system"}


@app.get("/api/models")
def list_models():
    """列出可用大模型"""
    return _get_available_models()


@app.post("/api/review")
async def review(file: UploadFile = File(...), model: str | None = Form(default=None)):
    """上传论文并执行审稿（可选指定 model）"""
    ext = Path(file.filename or "").suffix.lower()
    raw = await file.read()

    if ext in (".txt", ".md"):
        text = raw.decode("utf-8", errors="replace")
    elif ext == ".pdf":
        text = _extract_pdf_text(raw)
    elif ext == ".docx":
        text = _extract_docx_text(raw)
    else:
        return JSONResponse(status_code=400, content={"error": f"不支持的格式：{ext}。支持 .pdf / .docx / .txt / .md"})

    # 中文字数更合理（英文用单词数，中文用字符数/2 估算）
    _wc = len(text.split())
    if _wc < 200 and len(text) > 200:  # 中文文章 split 词数极少
        _wc = len(text.replace('\n', '').replace(' ', ''))
    parsed = ParsedDocument(
        file_name=file.filename or "unknown",
        sections=extract_sections(text),
        full_text=text,
        word_count=max(_wc, 1),
    )

    report = await run_review(parsed, model_name=model)
    return report.model_dump()


@app.get("/api/history")
def get_history():
    records = sorted(_history, key=lambda r: r.timestamp, reverse=True)
    return [r.model_dump() for r in records]


@app.delete("/api/history/{review_id}")
def delete_history(review_id: str):
    global _history
    _history = [r for r in _history if r.id != review_id]
    _reports.pop(review_id, None)
    _original_texts.pop(review_id, None)
    _journals.pop(review_id, None)
    _models_used.pop(review_id, None)
    return {"ok": True}


@app.get("/api/recommend-journals/{review_id}")
def recommend_journals_for_review(review_id: str):
    """根据审稿报告和论文内容，推荐 Top 5 投稿期刊"""
    from journal_recommender import recommend_journals as _r

    report = _reports.get(review_id)
    if report is None:
        return JSONResponse(status_code=404, content={"error": "报告不存在"})

    text = _original_texts.get(review_id, "")
    llm_journals = _journals.get(review_id, [])

    # 优先用 LLM 推荐，为空则用引擎推荐
    if llm_journals and len(llm_journals) >= 3:
        return llm_journals

    return _r(text, overall_score=float(report.summary.overall_score))


@app.get("/api/download/{review_id}")
def download_report(review_id: str):
    """下载审稿报告 DOCX（含修改痕迹和批注）"""
    from fastapi.responses import Response
    from urllib.parse import quote

    report = _reports.get(review_id)
    if report is None:
        return JSONResponse(status_code=404, content={"error": "报告不存在或已过期，请重新提交审稿"})

    original_text = _original_texts.get(review_id, "")
    journals = _journals.get(review_id)
    docx_bytes = _build_docx(report, original_text, journals)

    # 生成文件名：论文名-模型名-北京时间日期-审稿报告.docx
    safe_name = report.file_name.rsplit('.', 1)[0]
    model_name = _models_used.get(review_id, "unknown")
    model_short = model_name.rsplit('/', 1)[-1].replace(':', '-').replace('_', '-')
    bj_date = report.timestamp.astimezone(timezone(timedelta(hours=8))).strftime("%Y%m%d")
    filename = f"{safe_name}-{model_short}-{bj_date}-审稿报告.docx"
    encoded_filename = quote(filename)

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)