"""数据模型定义 - FastAPI schemas and domain types"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── 枚举类型 ──────────────────────────────────────────────


class RuleCategory(str, Enum):
    section = "section"        # 章节完整性
    format = "format"          # 格式规范
    citation = "citation"      # 引用检查
    grammar = "grammar"        # 语法/拼写


class Severity(str, Enum):
    error = "error"            # 错误 - 必须修复
    warning = "warning"        # 警告 - 建议修复
    info = "info"              # 提示 - 仅供参考


class RevisionType(str, Enum):
    insertion = "insertion"
    deletion = "deletion"
    modification = "modification"


class ReviewStatus(str, Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"


# ── 规则检查报告 ──────────────────────────────────────────


class RuleReport(BaseModel):
    category: RuleCategory
    severity: Severity
    title: str
    description: str
    location: Optional[str] = None
    suggestion: Optional[str] = None


# ── AI审阅结果 ────────────────────────────────────────────


class AIReviewItem(BaseModel):
    section: str               # 对应论文章节
    review_comment: str        # 审阅意见
    original_text: Optional[str] = None   # 原文片段（用于标注位置）
    suggestion: Optional[str] = None      # 修改建议


# ── 自动补全项 ────────────────────────────────────────────


class CompletionItem(BaseModel):
    section: str               # 缺失章节名称
    generated_content: str     # AI生成的内容草稿
    confidence: float = Field(ge=0.0, le=1.0)


# ── 修订痕迹 ──────────────────────────────────────────────


class Revision(BaseModel):
    revision_type: RevisionType
    original_text: Optional[str] = None   # 被删除/修改的内容
    new_text: str                           # 新增/修改后的内容
    location: str                           # 位置描述（章节名+段落编号）
    rationale: Optional[str] = None         # 修改理由


# ── 总体摘要 ──────────────────────────────────────────────


class ReviewSummary(BaseModel):
    overall_score: float = Field(ge=0.0, le=100.0)
    strengths: list[str] = []
    weaknesses: list[str] = []
    recommendation: str        # accept / minor_revision / major_revision / reject


# ── 稿件解析结果 ──────────────────────────────────────────


class SectionInfo(BaseModel):
    title: str
    level: int                 # 标题层级 (1=一级标题)
    content: str
    start_offset: int = 0
    end_offset: int = 0


class ParsedDocument(BaseModel):
    """解析后的论文内容"""
    file_name: str
    sections: list[SectionInfo] = []
    full_text: str = ""
    word_count: int = 0
    metadata: dict[str, Any] = {}


# ── API 请求/响应 ────────────────────────────────────────


class ReviewRequest(BaseModel):
    file_name: str
    parsed_text: str
    metadata: dict[str, Any] = {}


class CompletionReport(BaseModel):
    """审稿完成后的完整报告"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    file_name: str
    status: ReviewStatus = ReviewStatus.completed
    summary: ReviewSummary
    rules: list[RuleReport] = []
    ai_reviews: list[AIReviewItem] = []
    revisions: list[Revision] = []
    completions: list[CompletionItem] = []


# ── 历史记录 ──────────────────────────────────────────────


class HistoryRecord(BaseModel):
    id: str
    file_name: str
    timestamp: datetime
    summary: dict[str, Any]
