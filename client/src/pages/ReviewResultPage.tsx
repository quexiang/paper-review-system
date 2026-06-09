import React, { useState } from 'react';
import type { CompletionReport } from '../types';

interface Props {
  report: CompletionReport;
}

function getScoreColor(score: number): string {
  if (score >= 80) return 'score-high';
  if (score >= 60) return 'score-mid';
  return 'score-low';
}

function getRecClass(rec: string): string {
  const map: Record<string, string> = {
    accept: 'rec-accept', minor_revision: 'rec-minor', major_revision: 'rec-major', reject: 'rec-reject'
  };
  return map[rec] || '';
}

function getRecText(rec: string): string {
  const map: Record<string, string> = {
    accept: '✅ 建议接收', minor_revision: '🔧 小修后接收', major_revision: '📝 大修后复审', reject: '❌ 不建议接收'
  };
  return map[rec] || rec;
}

function getRuleClass(sev: string): string {
  const map: Record<string, string> = { error: 'rule-error', warning: 'rule-warning', info: 'rule-info' };
  return map[sev] || 'rule-info';
}

function getBadgeClass(sev: string): string {
  const map: Record<string, string> = { error: 'badge-error', warning: 'badge-warning', info: 'badge-info' };
  return map[sev] || '';
}

function getRuleLabel(cat: string): string {
  const map: Record<string, string> = { section: '📑 章节', format: '📐 格式', citation: '📚 引用', grammar: '✏️ 语法' };
  return map[cat] || cat;
}

function ReviewResultPage({ report }: Props) {
  const [activeTab, setActiveTab] = useState(0);

  const tabs = [
    { label: '📊 总评', key: 'summary' },
    { label: '📋 规则检查', key: 'rules' },
    { label: '🤖 AI 审阅', key: 'ai' },
    { label: '✍️ 修订痕迹', key: 'revisions' },
    { label: '📝 自动补全', key: 'completions' },
  ];

  return (
    <div>
      {/* 文件信息 & 分数 */}
      <div className="card" style={{ display: 'flex', gap: 32, alignItems: 'center', flexWrap: 'wrap' }}>
        <div>
          <div className="score-ring" style={{ background: `conic-gradient(var(--primary) ${report.summary.overall_score * 3.6}deg, var(--gray-200) 0deg)` }}>
            <div style={{ width: 90, height: 90, borderRadius: '50%', background: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <span className={getScoreColor(report.summary.overall_score)}>{report.summary.overall_score.toFixed(0)}</span>
            </div>
          </div>
        </div>
        <div style={{ flex: 1, minWidth: 280 }}>
          <h3 style={{ marginBottom: 8 }}>{report.file_name}</h3>
          <p style={{ color: 'var(--gray-600)', fontSize: 14, marginBottom: 12 }}>
            {new Date(report.timestamp).toLocaleString('zh-CN')} · 共 {report.rules.length} 条规则检查项 · {report.ai_reviews.length} 条审阅意见
          </p>
          <span className={`recommendation-badge ${getRecClass(report.summary.recommendation)}`}>
            {getRecText(report.summary.recommendation)}
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs">
        {tabs.map((tab, i) => (
          <div key={tab.key} className={`tab ${activeTab === i ? 'active' : ''}`} onClick={() => setActiveTab(i)}>
            {tab.label}
          </div>
        ))}
      </div>

      {/* Tab 0: Summary */}
      {activeTab === 0 && (
        <>
          <div className="card">
            <div className="card-title">💪 论文优点</div>
            {report.summary.strengths.map((s, i) => (
              <div key={i} className="list-item strength">{s}</div>
            ))}
          </div>
          <div className="card">
            <div className="card-title">⚠️ 需要改进</div>
            {report.summary.weaknesses.map((w, i) => (
              <div key={i} className="list-item weakness">{w}</div>
            ))}
          </div>
        </>
      )}

      {/* Tab 1: Rule Reports */}
      {activeTab === 1 && (
        <div className="card">
          <div className="card-title">📋 规则检查结果</div>
          {report.rules.length === 0 ? (
            <p style={{ color: 'var(--gray-600)' }}>✅ 未发现规则检查问题</p>
          ) : (
            report.rules.map((r, i) => (
              <div key={i} className={`rule-item ${getRuleClass(r.severity)}`}>
                <div className="rule-title">
                  <span className={`badge ${getBadgeClass(r.severity)}`}>{r.severity}</span>
                  {' '}{getRuleLabel(r.category)} · {r.title}
                  {r.location && <span style={{ color: 'var(--gray-600)', fontSize: 12, marginLeft: 8 }}>📍{r.location}</span>}
                </div>
                <div className="rule-desc">{r.description}</div>
                {r.suggestion && <div className="rule-suggestion">💡 {r.suggestion}</div>}
              </div>
            ))
          )}
        </div>
      )}

      {/* Tab 2: AI Reviews */}
      {activeTab === 2 && (
        <div className="card">
          <div className="card-title">🤖 AI 审阅意见</div>
          {report.ai_reviews.length === 0 ? (
            <p style={{ color: 'var(--gray-600)' }}>暂无审阅意见</p>
          ) : (
            report.ai_reviews.map((r, i) => (
              <div key={i} className="review-item">
                <div className="review-section">📑 {r.section}</div>
                <div className="review-comment">{r.review_comment}</div>
                {r.original_text && (
                  <div style={{ marginTop: 8, padding: 8, background: '#f9fafb', borderRadius: 6, fontSize: 13, color: 'var(--gray-600)' }}>
                    <strong>原文片段：</strong>{r.original_text.slice(0, 300)}
                  </div>
                )}
                {r.suggestion && (
                  <div style={{ marginTop: 6, fontSize: 13, color: 'var(--primary)', fontStyle: 'italic' }}>💡 {r.suggestion}</div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* Tab 3: Revisions */}
      {activeTab === 3 && (
        <div className="card">
          <div className="card-title">✍️ 审阅模式 · 修订痕迹</div>
          {report.revisions.length === 0 ? (
            <p style={{ color: 'var(--gray-600)' }}>暂无修订记录</p>
          ) : (
            report.revisions.map((r, i) => (
              <div key={i} className={`revision-block revision-${r.revision_type}`}>
                <div style={{ fontSize: 12, color: 'var(--gray-600)', marginBottom: 4 }}>
                  {r.revision_type === 'insertion' ? '➕ 新增' : r.revision_type === 'deletion' ? '❌ 删除' : '🔄 修改'} — {r.location}
                </div>
                {r.original_text && (
                  <div style={{ color: 'var(--danger)', textDecoration: 'line-through', opacity: 0.7, marginBottom: r.revision_type === 'modification' ? 4 : 0 }}>
                    {r.original_text.slice(0, 500)}
                  </div>
                )}
                <div style={{ color: 'var(--success)', fontWeight: 600 }}>
                  {r.new_text.slice(0, 500)}
                </div>
                {r.rationale && (
                  <div style={{ fontSize: 12, color: 'var(--gray-600)', marginTop: 4, fontStyle: 'italic' }}>
                    📝 {r.rationale}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* Tab 4: Completions */}
      {activeTab === 4 && (
        <div className="card">
          <div className="card-title">📝 自动补全内容</div>
          {report.completions.length === 0 ? (
            <p style={{ color: 'var(--gray-600)' }}>无需补全内容</p>
          ) : (
            report.completions.map((c, i) => (
              <div key={i} className="completion-card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span className="completion-section">📑 {c.section}</span>
                  <span className={`badge ${c.confidence >= 0.7 ? 'badge-success' : c.confidence >= 0.5 ? 'badge-warning' : 'badge-error'}`}>
                    置信度 {(c.confidence * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="confidence-bar">
                  <div className="confidence-fill" style={{ width: `${c.confidence * 100}%` }} />
                </div>
                <div className="completion-content">{c.generated_content}</div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

export default ReviewResultPage;
