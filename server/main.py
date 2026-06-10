"""FastAPI 主入口 — 论文审稿系统 API"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
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
    ParsedDocument,
    ReviewSummary,
    Revision,
    RuleReport,
)
from parser import parse_text, detect_missing_sections
from rule_engine.section_check import check_sections, analyze_section_balance
from rule_engine.format_check import check_format
from rule_engine.citation_check import check_citations

# ── 已知模型列表（静态 + Ollama 发现）──────────────────────


_KNOWN_MODELS: list[str] = [
    "gpt-4o",
    "gpt-4o-mini",
    "claude-sonnet-4-20250514",
    "claude-haiku-4-5-20250514",
    "qwen3.6:latest",
    "deepseek-r1:671b",
    "llama3.3:70b",
]

def _discover_ollama_models() -> list[str]:
    """从 Ollama 发现可用模型，与已知模型列表合并"""
    import urllib.request
    try:
        resp = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        data = resp.read().decode("utf-8")
        models = [m["name"] for m in json.loads(data).get("models", [])]
        # 合并去重，Ollama 的模型排在前面（因为 .env 优先指向 Ollama）
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
        "gpt-4o": "GPT-4o（OpenAI，综合能力强）",
        "gpt-4o-mini": "GPT-4o mini（轻量，速度快）",
        "claude-sonnet-4-20250514": "Claude Sonnet 4（Anthropic，深度推理）",
        "claude-haiku-4-5-20250514": "Claude Haiku 4（Anthropic，快速）",
        "qwen3.6:latest": "Qwen 3.6（通义千问，本地部署）",
        "deepseek-r1:671b": "DeepSeek R1 671B（深度推理）",
        "llama3.3:70b": "Llama 3.3 70B（Meta，开源）",
    }
    models = _discover_ollama_models()
    return [
        {"name": m, "desc": descriptions.get(m, f"模型 {m}")}
        for m in models
    ]


def _create_llm(model_name: str | None = None) -> AsyncOpenAI:
    """根据模型名创建对应的 LLM 客户端"""
    target_model = model_name or os.getenv("MODEL_NAME", "gpt-4o")
    client = AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY", ""),
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    )
    client._model = target_model  # type: ignore
    return client


# ── 全局状态 ───────────────────────────────────────────

_history: list[HistoryRecord] = []
_llm_client: AsyncOpenAI | None = None


def _get_llm() -> AsyncOpenAI:
    global _llm_client
    if _llm_client is None:
        _llm_client = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )
        _llm_client._model = os.getenv("MODEL_NAME", "gpt-4o")  # type: ignore
    return _llm_client


# ── PDF 解析 ───────────────────────────────────────────

def _extract_pdf_text(raw_bytes: bytes) -> str:
    """用 pypdfium2 从 PDF 提取纯文本"""
    doc = pdfium.PdfDocument(raw_bytes)
    text_parts: list[str] = []
    for page in doc:
        text = page.get_textb().decode("utf-8", errors="replace")
        if text.strip():
            text_parts.append(text)
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
    """完整的审稿流程：规则检查 → AI 审阅 → 生成报告"""
    text = parsed.full_text

    # 1. 规则检查
    rules: list[RuleReport] = []
    rules.extend(check_sections(text))
    rules.extend(analyze_section_balance(parsed.sections))
    rules.extend(check_format(text))
    rules.extend(check_citations(text))

    # 2. AI 审阅
    llm = _create_llm(model_name)
    target_model = getattr(llm, "_model", model_name or "gpt-4o")
    rule_lines = "\n".join(f"- [{r.severity.value}] {r.title}" for r in rules) or "无规则问题"

    prompt = (
        f"你是一位资深的学术期刊审稿人。请对以下论文进行严格审阅，并返回纯 JSON（不要使用代码块）。\n\n"
        f"## 规则检查结果\n{rule_lines}\n\n"
        f"## 论文全文（前15000字）\n{text[:15000]}\n\n"
        "请返回以下结构的 JSON：\n"
        "{"
        '"summary":{"overall_score":60,"strengths":[],"weaknesses":[],"recommendation":"minor_revision"},'
        '"ai_reviews":[{"section":"整体","review_comment":"意见","suggestion":"建议"}],'
        '"revisions":[], "completions":[]\n'
        "}\n"
    )
    try:
        model_to_use = getattr(llm, "_model", model_name or "gpt-4o")  # type: ignore
        resp = await llm.chat.completions.create(  # type: ignore
            model=model_to_use,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=8000,
        )
        raw = resp.choices[0].message.content or "{}"
        # 尝试从 markdown 代码块中提取 JSON
        import re as _re
        m = _re.search(r'```(?:json)?\s*\n(.*?)\n```', raw, _re.DOTALL)
        parsed_json = json.loads(m.group(1)) if m else json.loads(raw)
    except Exception:
        # 降级：基于规则的默认结果
        missing = detect_missing_sections(text)
        completions_out: list[dict] = []
        for m in missing:
            completions_out.append({
                "section": m,
                "generated_content": f"[{m}章节的占位内容 — 请在正式论文中补充实际内容。]",
                "confidence": 0.3,
            })

        parsed_json = {
            "summary": {
                "overall_score": 50.0 if missing else 70.0,
                "strengths": ["稿件结构基本完整"],
                "weaknesses": [f"缺少以下章节：{', '.join(missing)}"] if missing else ["暂无需要改进之处"],
                "recommendation": "major_revision" if missing else "minor_revision",
            },
            "ai_reviews": [{
                "section": "整体",
                "review_comment": f"稿件共 {parsed.word_count} 字，{len(parsed.sections)} 个章节。" + (
                    f"缺失章节：{', '.join(missing)}。" if missing else ""),
                "suggestion": "请补充缺失的论文章节并进行格式规范化处理。",
            }],
            "revisions": [],
            "completions": completions_out,
        }

    # 3. 组装报告（防御性解析：LLM 返回的数据可能包含非 dict 条目，需过滤）
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
    )

    # 4. 记录历史
    _history.append(HistoryRecord(
        id=report.id,
        file_name=parsed.file_name,
        timestamp=datetime.now(timezone.utc),
        summary={"score": report.summary.overall_score, "recommendation": report.summary.recommendation},
    ))

    return report


# ── FastAPI App ────────────────────────────────────────

@asynccontextmanager
async def _lifespan(app: FastAPI):
    yield

app = FastAPI(title="论文审稿系统", version="1.0.0", lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


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

    parsed = ParsedDocument(
        file_name=file.filename or "unknown",
        full_text=text,
        word_count=len(text.split()),
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
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
