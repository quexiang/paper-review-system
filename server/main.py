"""FastAPI 主入口 — 论文审稿系统 API"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
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
from parser import parse_text, detect_missing_sections, extract_sections
from rule_engine.section_check import check_sections, analyze_section_balance
from rule_engine.format_check import check_format
from rule_engine.citation_check import check_citations

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

def _get_available_models() -> list[dict]:
    """返回可用模型列表，每条包含 name 和 description"""
    descriptions = {
        "claude-sonnet-4-5-20251001": "Claude Sonnet 4.5（局域网，深度推理）",
        "claude-opus-4-5-20251001":   "Claude Opus 4.5（局域网，最强推理）",
        "claude-haiku-4-5-20251001":  "Claude Haiku 4.5（局域网，极速响应）",
    }
    models = _discover_ollama_models()
    return [
        {"name": m, "desc": descriptions.get(m, f"模型 {m}")}
        for m in models
    ]


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


# ── DOCX 报告生成 ────────────────────────────────────

def _build_docx(report: CompletionReport, original_text: str, journals: list[dict] | None = None) -> bytes:
    """根据审稿报告、原始文本和 LLM 推荐的期刊生成带批注的 DOCX 文件"""
    from io import BytesIO
    from docx import Document
    from docx.shared import Inches, Pt, Cm, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT

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
    run = subtitle.add_run(f'论文：{report.file_name}')
    run.font.size = Pt(14)
    run.font.color.rgb = RGBColor(0x52, 0x52, 0x5B)

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta.add_run(f'审稿时间：{report.timestamp.strftime("%Y-%m-%d %H:%M")}').font.size = Pt(11)
    meta.add_run(f'\n总评分数：{report.summary.overall_score:.0f} / 100').font.size = Pt(11)

    rec_text = {
        "accept": "建议接收", "minor_revision": "小修后接收",
        "major_revision": "大修后复审", "reject": "不建议接收"
    }.get(report.summary.recommendation, report.summary.recommendation)
    meta.add_run(f'\n审稿结论：{rec_text}').font.size = Pt(11)

    doc.add_page_break()

    # ── 总体评价 ────────────────────────────────────
    doc.add_heading('一、总体评价', level=1)
    doc.add_heading('论文优点', level=2)
    for s in report.summary.strengths:
        doc.add_paragraph(s, style='List Bullet')
    doc.add_heading('需要改进', level=2)
    for w in report.summary.weaknesses:
        doc.add_paragraph(w, style='List Bullet')

    doc.add_page_break()

    # ── 规则检查结果 ────────────────────────────────
    doc.add_heading('二、规则检查结果', level=1)
    if report.rules:
        for r in report.rules:
            sev_label = {"error": "❌ 错误", "warning": "⚠️ 警告", "info": "ℹ️ 提示"}.get(r.severity.value, r.severity.value)
            cat_label = {"section": "章节", "format": "格式", "citation": "引用", "grammar": "语法"}.get(r.category.value, r.category.value)
            doc.add_heading(f'{sev_label}  [{cat_label}] {r.title}', level=3)
            doc.add_paragraph(r.description)
            if r.suggestion:
                p = doc.add_paragraph()
                run = p.add_run(f'💡 建议：{r.suggestion}')
                run.font.italic = True
    else:
        doc.add_paragraph('✅ 未发现规则检查问题，论文格式符合学术规范。')

    doc.add_page_break()

    # ── 逻辑连贯性审查 ────────────────────────────
    doc.add_heading('三、逻辑连贯性审查', level=1)
    if report.logical_review:
        # 总体评价
        if report.logical_review.overall_assessment:
            doc.add_heading('总体评价', level=2)
            doc.add_paragraph(report.logical_review.overall_assessment)

        # 章节/段落逻辑
        if report.logical_review.section_logic:
            doc.add_heading('章节与段落逻辑', level=2)
            for item in report.logical_review.section_logic:
                doc.add_paragraph(item, style='List Bullet')

        # 论点论据逻辑
        if report.logical_review.argument_logic:
            doc.add_heading('论点与论据逻辑', level=2)
            for item in report.logical_review.argument_logic:
                doc.add_paragraph(item, style='List Bullet')

        # 逻辑问题检测
        if report.logical_review.coherence_issues:
            doc.add_heading('检测到的逻辑问题', level=2)
            sev_label = {"error": "❌ 严重", "warning": "⚠️ 一般", "info": "ℹ️ 提示"}
            for i, ci in enumerate(report.logical_review.coherence_issues, 1):
                doc.add_heading(f'{i}. {sev_label.get(ci.severity, ci.severity)} — {ci.issue_type}', level=3)
                doc.add_paragraph(f'位置：{ci.location}')
                doc.add_paragraph(ci.description)
                if ci.suggestion:
                    p = doc.add_paragraph()
                    run = p.add_run(f'💡 建议：{ci.suggestion}')
                    run.font.italic = True

        # 主题一致性
        if report.logical_review.theme_consistency:
            doc.add_heading('主题一致性评价', level=2)
            for item in report.logical_review.theme_consistency:
                doc.add_paragraph(item, style='List Bullet')
    else:
        doc.add_paragraph('暂无逻辑连贯性审查结果。')

    doc.add_page_break()

    # ── AI 审阅意见 ────────────────────────────────
    doc.add_heading('四、AI 审阅意见', level=1)
    if report.ai_reviews:
        for i, r in enumerate(report.ai_reviews, 1):
            doc.add_heading(f'{i}. {r.section}', level=2)
            doc.add_paragraph(r.review_comment)
            if r.suggestion:
                p = doc.add_paragraph()
                run = p.add_run(f'💡 {r.suggestion}')
                run.font.italic = True
                run.font.color.rgb = RGBColor(0x4F, 0x46, 0xE5)
    else:
        doc.add_paragraph('暂无 AI 审阅意见。')

    doc.add_page_break()

    # ── 修订痕迹 ────────────────────────────────────
    doc.add_heading('五、修订痕迹（修改前后对比）', level=1)
    if report.revisions:
        for i, r in enumerate(report.revisions, 1):
            rev_emoji = {"insertion": "➕ 新增", "deletion": "❌ 删除", "modification": "🔄 修改"}
            label = rev_emoji.get(r.revision_type.value, r.revision_type.value)
            doc.add_heading(f'{i}. {label} — {r.location}', level=2)

            if r.original_text:
                p = doc.add_paragraph()
                run = p.add_run('【原文】')
                run.font.bold = True
                run.font.color.rgb = RGBColor(0xDC, 0x26, 0x26)
                p = doc.add_paragraph()
                run = p.add_run(r.original_text)
                run.font.strike = True
                run.font.color.rgb = RGBColor(0xDC, 0x26, 0x26)

            p = doc.add_paragraph()
            run = p.add_run('【修改后】')
            run.font.bold = True
            run.font.color.rgb = RGBColor(0x05, 0x96, 0x69)
            p = doc.add_paragraph()
            run = p.add_run(r.new_text)
            run.font.color.rgb = RGBColor(0x05, 0x96, 0x69)

            if r.rationale:
                p = doc.add_paragraph()
                run = p.add_run(f'📝 理由：{r.rationale}')
                run.font.italic = True
                run.font.size = Pt(10)
    else:
        doc.add_paragraph('暂无修订痕迹。')

    doc.add_page_break()

    # ── 自动补全 ────────────────────────────────────
    doc.add_heading('六、自动补全内容', level=1)
    if report.completions:
        for i, c in enumerate(report.completions, 1):
            doc.add_heading(f'{i}. {c.section}（置信度 {c.confidence:.0%}）', level=2)
            doc.add_paragraph(c.generated_content)
    else:
        doc.add_paragraph('论文章节完整，无需补全内容。')

    doc.add_page_break()

    # ── 推荐期刊 Top 5 ───────────────────────────────
    doc.add_heading('七、推荐期刊（Top 10）', level=1)

    score = report.summary.overall_score

    if score < 50:
        note = "当前稿件得分偏低，建议进一步完善实验验证和章节内容后投稿。"
    elif score < 70:
        note = "当前稿件处于中等水平，建议加强方法描述和实验对比后冲击高影响力期刊。"
    else:
        note = "稿件质量良好，建议优先尝试CCF-A/SCI Q1期刊，同时准备1-2个备选。"

    p = doc.add_paragraph()
    run = p.add_run(f'💡 {note}')
    run.font.italic = True
    run.font.size = Pt(10)

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
            row[0].text = str(j.get("name", ""))
            p = row[1].paragraphs[0]
            run = p.add_run(str(j.get("level", "")))
            run.font.bold = True
            match_val = j.get("match", "")
            row[2].text = f"{match_val}%" if isinstance(match_val, (int, float)) else str(match_val)
            row[3].text = str(j.get("reason", j.get("desc", "")))

        from docx.shared import Cm
        for row_obj in table.rows:
            row_obj.cells[0].width = Cm(4.5)
            row_obj.cells[1].width = Cm(2.5)
            row_obj.cells[2].width = Cm(1.5)
            row_obj.cells[3].width = Cm(7.5)
    else:
        doc.add_paragraph('暂无推荐期刊数据。')

    # 写入内存
    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


# ── PDF 解析 ───────────────────────────────────────────

def _extract_pdf_text(raw_bytes: bytes) -> str:
    """用 pypdfium2 从 PDF 提取纯文本（兼容 v3/v4/v5）"""
    doc = pdfium.PdfDocument(raw_bytes)
    text_parts: list[str] = []
    for page in doc:
        # 兼容 pypdfium2 各版本 API 差异
        page_text = ""
        try:
            # v5+: get_textpage() → get_text_range()
            textpage = page.get_textpage()
            n_chars = textpage.count_chars()
            if n_chars > 0:
                page_text = textpage.get_text_range(index=0, count=n_chars)
            textpage.close()
        except AttributeError:
            try:
                # v4: get_text() → str
                page_text = page.get_text()
            except AttributeError:
                # v3: get_textb() → bytes
                page_text = page.get_textb().decode("utf-8", errors="replace")
        if page_text.strip():
            text_parts.append(page_text)
    doc.close()
    return "\n".join(text_parts)


# ── DOCX 解析 ─────────────────────────────────────────

def _extract_docx_text(raw_bytes: bytes) -> str:
    """用 python-docx 提取文本"""
    from io import BytesIO
    from docx import Document as DocxDocument
    doc = DocxDocument(BytesIO(raw_bytes))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


# ── 审阅流程 ───────────────────────────────────────────

async def run_review(parsed: ParsedDocument, model_name: str | None = None) -> CompletionReport:
    """完整的审稿流程：规则检查 → AI 审阅 → 生成报告（含修订痕迹 + 自动补全）"""
    text = parsed.full_text

    # 1. 规则检查
    rules: list[RuleReport] = []
    rules.extend(check_sections(text))
    rules.extend(analyze_section_balance([s.model_dump() for s in parsed.sections]))
    rules.extend(check_format(text))
    rules.extend(check_citations(text))

    # ── 辅助：从规则结果生成修订建议 ──────────────────
    def _gen_revisions_from_rules() -> list[dict]:
        """把规则检查问题转化为具体修订建议"""
        revs: list[dict] = []
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

    # ── 辅助：从缺失章节生成补全内容 ────────────────
    def _gen_completions_from_missing() -> list[dict]:
        """为缺失的标准章节生成 AI 补全占位"""
        missing = detect_missing_sections(text)
        completions: list[dict] = []
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
        """LLM 失败时的降级方案：用推荐引擎模块匹配期刊"""
        score = summary.get("overall_score", 60)
        return _recommend_journals(text, overall_score=float(score))

    # 2. AI 审阅 prompt
    llm = _create_llm(model_name)
    rule_lines = "\n".join(f"- [{r.severity.value}] {r.title}" for r in rules) or "无规则问题"

    # 将论文的章节列表告诉 LLM，帮助它定位
    section_titles = [s.title for s in parsed.sections] if parsed.sections else ["（未识别到章节）"]

    prompt = (
        f"你是一位资深的学术期刊审稿人，擅长全面、深入地评审学术论文。请对以下论文进行详尽的审阅，"
        f"返回尽可能全面、完整的审阅结果（纯 JSON，不要使用代码块）。\n\n"
        f"## 规则检查结果\n{rule_lines}\n\n"
        f"## 论文全文（前20000字）\n{text[:20000]}\n\n"
        "## 重要要求\n"
        "你必须返回一个完整的 JSON 对象，包含以下全部字段。每项内容都必须**详尽、具体、有深度**，"
        "不能敷衍了事或泛泛而谈。\n\n"
        "### summary - 总体评价\n"
        "{\"overall_score\": 0-100 整数, \"strengths\": [\"优点1\", \"优点2\", ...], \"weaknesses\": [\"缺点1\", \"缺点2\", ...], "
        "\"recommendation\": \"accept|minor_revision|major_revision|reject\"}\n"
        "要求：strengths 至少 4 条，weaknesses 至少 4 条，每条都要具体针对论文内容，不能泛泛而谈（如“创新性强”应具体说明哪个创新点）。\n\n"
        "### ai_reviews - 逐章节 AI 审阅意见\n"
        "要求：\n"
        "1. 为论文中的**每一个章节**都生成审阅意见，包括摘要、引言、方法、实验、结论等\n"
        "2. 每条 review_comment 必须**至少 300 个字**，建议按以下结构撰写：\n"
        "   ①【内容质量】该章节的内容是否充实、准确，核心论点是否清晰\n"
        "   ②【写作水平】表达是否清晰、专业，逻辑是否连贯\n"
        "   ③【具体问题】指出该章节中存在的具体问题（如有），引用原文片段佐证\n"
        "   ④【优点亮点】该章节做得好的地方\n"
        "3. 每条 suggestion 必须**至少 100 个字**，给出可操作的具体修改方案\n"
        "4. original_text 字段应截取原文中你正在评述的关键片段（50-200字），用于佐证你的观点\n"
        "5. 格式：\n"
        "[{\"section\": \"章节名\", \"review_comment\": \"按上述结构撰写的详尽审阅意见（≥300字）\", "
        "\"original_text\": \"原文关键片段（可选）\", \"suggestion\": \"具体的可操作的修改建议（≥100字）\"}]\n\n"
        "### revisions - 修订痕迹\n"
        "[{\"revision_type\": \"insertion|deletion|modification\", \"original_text\": \"被修改的原文（删除/修改时必填）\", "
        "\"new_text\": \"修改后的完整文本\", \"location\": \"章节名 + 段落位置\", \"rationale\": \"详细修改理由\"}]\n"
        "要求：至少 8 条，覆盖论文中各个章节需要改进的地方。每条的修改理由要充分说明为什么这样改更好。\n\n"
        "### completions - 自动补全内容\n"
        "要求：\n"
        "1. 如果论文缺少某些关键章节（如讨论、结论等），必须为**每个缺失章节**生成补全\n"
        "2. 即使论文没有明显缺失章节，也应检查各章节内容是否完整，为**内容单薄或不完整的章节**生成补全建议\n"
        "3. 每条 generated_content 必须**至少 500 个字**，按以下结构撰写：\n"
        "   ①【章节定位】该章节在论文中的作用和重要性\n"
        "   ②【核心要点】该章节应包含的关键内容和论点\n"
        "   ③【草稿正文】实际可用的内容草稿（用具体、学术化的语言撰写，紧密结合论文已有内容）\n"
        "4. 补全内容必须与论文的研究主题、方法、数据紧密结合，**不能是通用模板**\n"
        "5. 格式：\n"
        "[{\"section\": \"缺失或内容不足的章节名\", \"generated_content\": \"按上述结构撰写的内容（≥500字）\", "
        "\"confidence\": 0.5-0.9 的浮点数}]\n\n"
        "### journals - 推荐期刊 Top 10\n"
        "[{\"name\": \"期刊/会议全称（含缩写）\", \"level\": \"CCF-A/B/C 或 SCI Q1/Q2/Q3\", \"match\": \"匹配度百分比\", "
        "\"reason\": \"推荐理由：详细说明该期刊的征稿范围与本文主题、方法、创新点的具体匹配关系（至少 50 字）\"}]\n"
        "要求：至少 10 条，每条推荐理由必须具体、有针对性。\n\n"
        "### logical_review - 逻辑连贯性审查（必须详尽填写）\n"
        "{\n"
        "  \"section_logic\": [\"逐章节的详细逻辑审查意见1\", \"意见2\", ...],\n"
        "  \"argument_logic\": [\"论点论据逻辑性审查意见1\", \"意见2\", ...],\n"
        "  \"coherence_issues\": [\n"
        "    {\"location\": \"具体位置描述（章节名+段落）\", \"issue_type\": \"section_logic|argument_logic|sentence_coherence|theme_mismatch\", "
        "     \"description\": \"问题的详细描述\", \"severity\": \"error|warning|info\", \"suggestion\": \"具体的修改建议\"}\n"
        "  ],\n"
        "  \"theme_consistency\": [\"与段落/论文主题一致性评价1\", \"评价2\", ...],\n"
        "  \"overall_assessment\": \"总体逻辑性评价（至少 150 字）\"\n"
        "}\n\n"
        "逻辑连贯性审查要点（请逐项详尽审查）：\n"
        "1. section_logic（至少 4 条）：逐章节检查论文结构是否合理，章节之间的逻辑递进关系是否清晰，"
        "各章节主题是否明确、重点突出。\n"
        "2. argument_logic（至少 4 条）：检查每个核心论点的论据是否充分，推理过程是否严密，"
        "是否存在逻辑跳跃、循环论证、因果混淆等问题。\n"
        "3. coherence_issues（至少 5 条）：检测具体的行文逻辑问题，包括：\n"
        "   - sentence_coherence：语句不通顺、前后衔接不自然\n"
        "   - argument_logic：论证跳跃、论据不足、推理漏洞\n"
        "   - section_logic：章节间逻辑断层、段落与章节主题不符\n"
        "   - theme_mismatch：与论文核心主题不相关的内容\n"
        "4. theme_consistency（至少 3 条）：评价全文是否围绕核心主题展开，各章节内容是否服务于同一研究目标。\n"
        "5. overall_assessment（至少 150 字）：对论文整体逻辑性给出综合性的总体评价。\n\n"
        "请根据论文的实际创新性、研究方法和主题内容，推荐 10 个最适合投稿的期刊或会议。\n"
        "必须考虑论文质量水平与期刊级别的匹配——高创新高分的推荐顶会/顶刊，中等水平的推荐合适级别的期刊。\n"
        "每条推荐理由必须具体说明该期刊为什么适合本文，不能泛泛而谈。不要返回空数组！\n"
    )
    raw = "{}"
    try:
        model_to_use = getattr(llm, "_model", model_name or "gpt-4o")  # type: ignore
        resp = await llm.chat.completions.create(  # type: ignore
            model=model_to_use,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=16384,
        )
        raw = resp.choices[0].message.content or "{}"
        import re as _re
        # 去除 vLLM Claude thinking 块：</think> 之后才是实际 JSON
        _think_end = raw.find('</think>')
        if _think_end >= 0:
            raw = raw[_think_end + len('</think>'):].strip()
        # 去除 thinking 前缀（无闭合标签的情况）
        _think_match = _re.search(r'(Here\'s a thinking process:).*?\n\n', raw, _re.DOTALL | _re.IGNORECASE)
        if _think_match:
            raw = raw[_think_match.end():].strip()
        # 尝试从 markdown 代码块中提取 JSON
        m = _re.search(r'```(?:json)?\s*\n(.*?)\n```', raw, _re.DOTALL)
        if m:
            parsed_json = json.loads(m.group(1))
        else:
            # 从混杂文本中提取 JSON（找最外层 {}）
            _brace_start = raw.find('{')
            _brace_end = raw.rfind('}')
            if _brace_start >= 0 and _brace_end > _brace_start:
                raw = raw[_brace_start:_brace_end + 1]
            parsed_json = json.loads(raw)
    except Exception as e:
        # LLM 调用/解析失败时：基于规则生成默认结果
        import sys as _sys, traceback as _tb
        print(f"[WARN] LLM failed: {e}", file=_sys.stderr)
        if raw and raw != "{}":
            print(f"[WARN] Raw response (first 500 chars): {raw[:500]}", file=_sys.stderr)
        missing = detect_missing_sections(text)
        section_titles = [s.title for s in parsed.sections] if parsed.sections else []
        # 从已有章节尝试推断论文主题
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

    # 3. 降级补充：如果 LLM 未返回足够的 revisions/completions/journals，从规则/内容生成
    ai_revisions = parsed_json.get("revisions", []) or []
    ai_completions = parsed_json.get("completions", []) or []
    ai_journals = parsed_json.get("journals", []) or []

    sm = parsed_json.get("summary", {})  # 提前提取，供降级函数使用评分
    if len(ai_revisions) < 2:
        rule_revs = _gen_revisions_from_rules()
        # 合并 LLM 返回的和规则生成的，避免重复
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
        # 规范化 match 值（LLM 可能返回 int，统一转为 "92%" 格式）
        for j in (ai_journals or []):
            if isinstance(j, dict) and isinstance(j.get("match"), (int, float)):
                j["match"] = f"{j['match']}%"
        parsed_json["journals"] = ai_journals[:10]

    # 4. 组装报告（防御性解析：LLM 返回的数据可能包含非 dict 条目，需过滤）
    sm = parsed_json.get("summary", {})

    def _safe_parse(items, cls):
        """过滤非 dict 条目并安全实例化 Pydantic model"""
        out = []
        for r in (items or []):
            if isinstance(r, dict):
                try:
                    out.append(cls(**r))
                except Exception:
                    pass  # 字段不完整则跳过
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
        pass  # 逻辑审查解析失败不影响其他审稿结果

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
    )

    # 4. 记录历史（保存完整报告和原文供下载）
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
    safe_name = report.file_name.rsplit('.', 1)[0] if '.' in report.file_name else report.file_name
    model_name = _models_used.get(review_id, "unknown")
    # 模型名取最后一段（去掉路径前缀如 huihui_ai/deepseek-r1 → deepseek-r1）
    model_short = model_name.rsplit('/', 1)[-1].replace(':', '-').replace('_', '-')
    # 北京时间 (UTC+8)
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
