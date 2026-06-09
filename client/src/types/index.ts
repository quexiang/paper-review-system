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
}

export interface HistoryRecord {
  id: string;
  file_name: string;
  timestamp: Date;
  summary: { score: number; recommendation: string };
}
