// 审稿系统 TypeScript 类型定义

export type RuleCategory = 'section' | 'format' | 'citation' | 'grammar';
export type Severity = 'error' | 'warning' | 'info';
export type RevisionType = 'insertion' | 'deletion' | 'modification';
export type ReviewStatus = 'pending' | 'completed' | 'failed';

export interface RuleReport {
  category: RuleCategory;
  severity: Severity;
  title: string;
  description: string;
  location?: string;
  suggestion?: string;
}

export interface AIReviewItem {
  section: string;
  review_comment: string;
  original_text?: string;
  suggestion?: string;
}

export interface CompletionItem {
  section: string;
  generated_content: string;
  confidence: number;
}

export interface Revision {
  revision_type: RevisionType;
  original_text?: string;
  new_text: string;
  location: string;
  rationale?: string;
}

export interface ReviewSummary {
  overall_score: number;
  strengths: string[];
  weaknesses: string[];
  recommendation: 'accept' | 'minor_revision' | 'major_revision' | 'reject';
}

export interface CoherenceIssue {
  location: string;
  issue_type: 'section_logic' | 'argument_logic' | 'sentence_coherence' | 'theme_mismatch';
  description: string;
  severity: 'error' | 'warning' | 'info';
  suggestion?: string;
}

export interface KnowledgeGraphNode {
  id: string;
  label: string;
  type: 'theory' | 'method' | 'concept' | 'result' | 'variable' | 'finding' | string;
  description: string;
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
}

export interface KnowledgeGraphEdge {
  source: string;
  target: string;
  label: string;
  type: 'supports' | 'uses' | 'contradicts' | 'related' | 'causes' | 'improves' | string;
}

export interface KnowledgeGraph {
  nodes: KnowledgeGraphNode[];
  edges: KnowledgeGraphEdge[];
  summary: string;
}

export interface LogicalReview {
  research_theme: string;
  research_framework: string;
  section_logic: string[];
  argument_logic: string[];
  coherence_issues: CoherenceIssue[];
  theme_consistency: string[];
  overall_assessment: string;
  knowledge_graph: KnowledgeGraph;
}

export interface CompletionReport {
  id: string;
  timestamp: Date;
  file_name: string;
  status: ReviewStatus;
  summary: ReviewSummary;
  rules: RuleReport[];
  ai_reviews: AIReviewItem[];
  revisions: Revision[];
  completions: CompletionItem[];
  logical_review?: LogicalReview | null;
  polished_paper?: string | null;
  literature_review?: string | null;
  llm_success?: boolean;
  error_messages?: string[];
}

export interface HistoryRecord {
  id: string;
  file_name: string;
  timestamp: Date;
  summary: { score: number; recommendation: string };
}
