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


class CoherenceIssue(BaseModel):
    """逻辑不连贯问题"""
    location: str              # 位置描述（章节名+段落位置）
    issue_type: str            # "section_logic" | "argument_logic" | "sentence_coherence" | "theme_mismatch"
    description: str           # 问题描述
    severity: str              # "error" | "warning" | "info"
    suggestion: Optional[str] = None  # 修改建议


class KnowledgeGraphNode(BaseModel):
    """知识图谱节点"""
    id: str                                        # 唯一标识
    label: str                                     # 显示名称
    type: str                                      # 节点类型: theory/method/concept/result/variable/finding
    description: str = ""                          # 节点简要描述


class KnowledgeGraphEdge(BaseModel):
    """知识图谱边"""
    source: str                                    # 源节点 id
    target: str                                    # 目标节点 id
    label: str = ""                                # 关系描述
    type: str = "related"                          # 关系类型: supports/uses/contradicts/related/causes/improves


class KnowledgeGraph(BaseModel):
    """知识图谱"""
    nodes: list[KnowledgeGraphNode] = []
    edges: list[KnowledgeGraphEdge] = []
    summary: str = ""                              # 图谱结构简要描述


class LogicalReview(BaseModel):
    """逻辑连贯性审查结果"""
    research_theme: str = ""                       # 论文研究主题分析
    research_framework: str = ""                   # 研究路线图 / 整体框架
    section_logic: list[str] = []                  # 章节/段落主题逻辑性审查意见
    argument_logic: list[str] = []                 # 论点论据逻辑性审查意见
    coherence_issues: list[CoherenceIssue] = []    # 检测到的逻辑不通顺问题
    theme_consistency: list[str] = []              # 与段落主题、论文主题一致性评价
    overall_assessment: str = ""                   # 总体逻辑性评价
    knowledge_graph: Optional[KnowledgeGraph] = None  # 知识图谱


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
    logical_review: Optional[LogicalReview] = None  # 逻辑连贯性审查结果
    polished_paper: Optional[str] = None            # 论文润色后全文
    literature_review: Optional[str] = None         # 文献综述全文
    llm_success: bool = True                        # LLM 是否成功执行
    error_messages: list[str] = []                  # LLM 失败时的错误信息


# ── 历史记录 ──────────────────────────────────────────────


class HistoryRecord(BaseModel):
    id: str
    file_name: str
    timestamp: datetime
    summary: dict[str, Any]
