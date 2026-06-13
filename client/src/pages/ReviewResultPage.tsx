import React, { useState } from 'react';
import type { CompletionReport } from '../types';

interface Props {
  report: CompletionReport;
}

/* ── 辅助函数 ──────────────────────────────────────────── */

function scoreClass(score: number): string {
  if (score >= 80) return 'score-high';
  if (score >= 60) return 'score-mid';
  return 'score-low';
}

const REC_CLASS: Record<string, string> = {
  accept: 'rec-accept', minor_revision: 'rec-minor', major_revision: 'rec-major', reject: 'rec-reject'
};

const REC_TEXT: Record<string, string> = {
  accept: '✅ 建议接收', minor_revision: '🔧 小修后接收', major_revision: '📝 大修后复审', reject: '❌ 不建议接收'
};

const RULE_CLASS: Record<string, string> = {
  error: 'rule-error', warning: 'rule-warning', info: 'rule-info'
};

const BADGE_CLASS: Record<string, string> = {
  error: 'badge-error', warning: 'badge-warning', info: 'badge-info'
};

const RULE_LABEL: Record<string, string> = {
  section: '📑 章节', format: '📐 格式', citation: '📚 引用', grammar: '✏️ 语法'
};

const REV_EMOJI: Record<string, string> = {
  insertion: '➕ 新增', deletion: '❌ 删除', modification: '🔄 修改'
};

interface JournalRec {
  name: string;
  level: string;
  match: string;
  reason: string;
  if?: string;
  accept_rate?: string;
  review_cycle?: string;
}

function ReviewResultPage({ report }: Props) {
  const [activeTab, setActiveTab] = useState(0);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState('');
  const [journals, setJournals] = useState<JournalRec[]>([]);
  const [journalsLoading, setJournalsLoading] = useState(true);

  React.useEffect(() => {
    fetch(`/api/recommend-journals/${report.id}`)
      .then(r => r.json())
      .then(data => {
        if (Array.isArray(data)) setJournals(data);
      })
      .catch(() => {})
      .finally(() => setJournalsLoading(false));
  }, [report.id]);

  const handleDownload = async () => {
    setDownloading(true);
    setDownloadError('');
    try {
      const res = await fetch(`/api/download/${report.id}`);
      if (!res.ok) {
        if (res.status === 404) {
          throw new Error('审稿报告已过期（服务器重启后数据丢失），请重新提交论文审稿后再下载。');
        }
        throw new Error(`下载失败（HTTP ${res.status}），请稍后重试。`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      // 从服务器响应头提取文件名（含模型名和日期），客户端不再硬编码
      const disposition = res.headers.get('Content-Disposition');
      let filename = `${report.file_name.replace(/\.[^.]+$/, '')}-审稿报告.docx`;
      if (disposition) {
        const match = disposition.match(/filename\*=UTF-8''(.+)/);
        if (match) {
          filename = decodeURIComponent(match[1]);
        }
      }
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setDownloadError(e.message || '下载失败，请重试');
    } finally {
      setDownloading(false);
    }
  };

  const tabs = [
    { label: '📊 总评',        key: 'summary',    count: 0 },
    { label: '📋 规则检查',   key: 'rules',      count: report.rules.length },
    { label: '🤖 AI 审阅',    key: 'ai',          count: report.ai_reviews.length },
    { label: '✍️ 修订痕迹',  key: 'revisions',   count: report.revisions.length },
    { label: '📝 自动补全',   key: 'completions', count: report.completions.length },
    { label: '📚 推荐期刊',   key: 'journals',    count: journals.length },
  ];

  return (
    <div>
      {/* ── 分数卡片 ──────────────────────────────── */}
      <div className="card score-card">
        <div className="score-ring-wrap">
          <div
            className="score-ring"
            style={{
              background: `conic-gradient(var(--primary) ${report.summary.overall_score * 3.6}deg, var(--gray-100) 0deg)`
            }}
          >
            <div className={`score-ring-inner ${scoreClass(report.summary.overall_score)}`}>
              <span>{report.summary.overall_score.toFixed(0)}</span>
            </div>
          </div>
        </div>

        <div className="score-meta">
          <h3>{report.file_name}</h3>
          <p className="meta-info">
            <span>{new Date(report.timestamp).toLocaleString('zh-CN')}</span>
            <span>{report.rules.length} 条检查</span>
            <span>{report.ai_reviews.length} 条审阅</span>
          </p>
          <span className={`recommendation-badge ${REC_CLASS[report.summary.recommendation] ?? ''}`}>
            {REC_TEXT[report.summary.recommendation] ?? report.summary.recommendation}
          </span>
          <button
            className="btn btn-download"
            onClick={handleDownload}
            disabled={downloading}
            style={{ marginLeft: 12 }}
          >
            {downloading ? '⏳ 生成中...' : '📥 下载审稿报告'}
          </button>
          {downloadError && (
            <p style={{ marginTop: 10, fontSize: 13, color: 'var(--danger)', background: 'var(--danger-bg)', padding: '8px 14px', borderRadius: 8 }}>
              ❌ {downloadError}
            </p>
          )}
        </div>
      </div>

      {/* ── Tabs ──────────────────────────────────── */}
      <div className="tabs">
        {tabs.map((tab, i) => (
          <button
            key={tab.key}
            className={`tab ${activeTab === i ? 'active' : ''}`}
            onClick={() => setActiveTab(i)}
          >
            {tab.label}
            {tab.count > 0 && <span className="tab-badge">{tab.count}</span>}
          </button>
        ))}
      </div>

      {/* ── Tab 0: 总评 ───────────────────────────── */}
      {activeTab === 0 && (
        <>
          <div className="card">
            <div className="card-title">💪 论文优点</div>
            {report.summary.strengths.length === 0 ? (
              <div className="empty-state">
                <p>暂无评价</p>
              </div>
            ) : (
              report.summary.strengths.map((s, i) => (
                <div key={i} className="list-item strength">{s}</div>
              ))
            )}
          </div>
          <div className="card">
            <div className="card-title">⚠️ 需要改进</div>
            {report.summary.weaknesses.length === 0 ? (
              <div className="empty-state">
                <p>暂无明显需要改进之处</p>
              </div>
            ) : (
              report.summary.weaknesses.map((w, i) => (
                <div key={i} className="list-item weakness">{w}</div>
              ))
            )}
          </div>
        </>
      )}

      {/* ── Tab 1: 规则检查 ────────────────────────── */}
      {activeTab === 1 && (
        <div className="card">
          <div className="card-title">📋 规则检查结果</div>
          {report.rules.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">✅</div>
              <p>未发现规则检查问题</p>
            </div>
          ) : (
            report.rules.map((r, i) => (
              <div key={i} className={`rule-item ${RULE_CLASS[r.severity] ?? 'rule-info'}`}>
                <div className="rule-title">
                  <span className={`badge ${BADGE_CLASS[r.severity] ?? 'badge-info'}`}>{r.severity}</span>
                  {' '}{RULE_LABEL[r.category] ?? r.category} · {r.title}
                  {r.location && <> <span className="rev-location">📍{r.location}</span></>}
                </div>
                <div className="rule-desc">{r.description}</div>
                {r.suggestion && <div className="rule-suggestion">💡 {r.suggestion}</div>}
              </div>
            ))
          )}
        </div>
      )}

      {/* ── Tab 2: AI 审阅 ─────────────────────────── */}
      {activeTab === 2 && (
        <div className="card">
          <div className="card-title">🤖 AI 审阅意见</div>
          {report.ai_reviews.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">🤖</div>
              <p>暂无 AI 审阅意见 — 可能是 LLM 未能生成有效评审结果</p>
            </div>
          ) : (
            report.ai_reviews.map((r, i) => (
              <div key={i} className="review-item">
                <div className="review-section">📑 {r.section}</div>
                <div className="review-comment">{r.review_comment}</div>
                {r.original_text && (
                  <div className="review-original">
                    <strong>原文片段</strong>
                    {r.original_text.slice(0, 300)}
                  </div>
                )}
                {r.suggestion && (
                  <div className="review-suggestion">
                    💡 {r.suggestion}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* ── Tab 3: 修订痕迹 ────────────────────────── */}
      {activeTab === 3 && (
        <div className="card">
          <div className="card-title">✍️ 修订痕迹</div>
          {report.revisions.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">✍️</div>
              <p>暂无修订记录 — LLM 可能未生成修改建议</p>
            </div>
          ) : (
            report.revisions.map((r, i) => (
              <div key={i} className={`revision-block revision-${r.revision_type}`}>
                <div className="revision-label">
                  {REV_EMOJI[r.revision_type] ?? r.revision_type} — {r.location}
                </div>
                {r.original_text && (
                  <div className="rev-original">{r.original_text.slice(0, 500)}</div>
                )}
                <div className="rev-new">{r.new_text.slice(0, 500)}</div>
                {r.rationale && <div className="rev-rationale">📝 {r.rationale}</div>}
              </div>
            ))
          )}
        </div>
      )}

      {/* ── Tab 4: 自动补全 ────────────────────────── */}
      {activeTab === 4 && (
        <div className="card">
          <div className="card-title">📝 自动补全内容</div>
          {report.completions.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📝</div>
              <p>无需补全内容 — 论文章节完整或 LLM 未能生成补全</p>
            </div>
          ) : (
            report.completions.map((c, i) => (
              <div key={i} className="completion-card">
                <div className="completion-header">
                  <span className="completion-section">📑 {c.section}</span>
                  <span className={`badge ${c.confidence >= 0.7 ? 'badge-success' : c.confidence >= 0.5 ? 'badge-warning' : 'badge-error'}`}>
                    置信度 {(c.confidence * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="confidence-bar">
                  <div
                    className="confidence-fill"
                    style={{ width: `${c.confidence * 100}%` }}
                  />
                </div>
                <div className="completion-content">{c.generated_content}</div>
              </div>
            ))
          )}
        </div>
      )}

      {/* ── Tab 5: 推荐期刊 ────────────────────────── */}
      {activeTab === 5 && (
        <div className="card">
          <div className="card-title">📚 推荐投稿期刊（Top 10）</div>
          {journalsLoading ? (
            <div style={{ textAlign: 'center', padding: 20 }}>
              <div className="spinner" style={{ margin: '0 auto' }} />
              <p style={{ marginTop: 12, color: 'var(--gray-400)', fontSize: 13 }}>正在分析最佳投稿期刊...</p>
            </div>
          ) : journals.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📚</div>
              <p>暂无期刊推荐数据 — 可能是 LLM 未能生成推荐，请重新提交审稿</p>
            </div>
          ) : (
            journals.map((j, i) => (
              <div key={i} className="journal-recommendation-item">
                <div className="journal-header">
                  <span className="journal-rank">#{i + 1}</span>
                  <div className="journal-info">
                    <span className="journal-name">{j.name}</span>
                    <div className="journal-meta">
                      <span className={`badge ${j.level.includes('CCF-A') || j.level.includes('SCI Q1') ? 'badge-error' : 'badge-warning'}`}>{j.level}</span>
                      {j.if && <span className="journal-stat">IF {j.if}</span>}
                      {j.accept_rate && <span className="journal-stat">接受率 {j.accept_rate}</span>}
                      {j.review_cycle && <span className="journal-stat">⏱ {j.review_cycle}</span>}
                    </div>
                  </div>
                  <span className="journal-match">{j.match}</span>
                </div>
                <p className="journal-reason">{j.reason}</p>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

export default ReviewResultPage;
