import React, { useState } from 'react';
import type { CompletionReport } from '../types';
import * as d3 from 'd3';

interface Props {
  report: CompletionReport;
}

/* ── 辅助函数 ──────────────────────────────────────────── */

function scoreClass(score: number): string {
  if (score >= 80) return 'score-high';
  if (score >= 60) return 'score-mid';
  return 'score-low';
}

/** 双语内容：用明确分隔符区分英文和中文，前端加语言标签 */
const CN_SEPARATOR = '--- 中文翻译 ---';

function formatBilingual(text: string): React.ReactNode {
  if (!text) return text;
  const sepIdx = text.indexOf(CN_SEPARATOR);
  if (sepIdx === -1) return text;
  const english = text.slice(0, sepIdx).trim();
  const chinese = text.slice(sepIdx + CN_SEPARATOR.length).trim();
  if (!english || !chinese) return text;
  return (
    <>
      {english}
      <br />
      <span style={{ color: 'var(--primary)', fontWeight: 700 }}>🇨🇳 中文：</span>
      {chinese}
    </>
  );
}

const REC_CLASS: Record<string, string> = {
  accept: 'rec-accept', minor_revision: 'rec-minor', major_revision: 'rec-major', reject: 'rec-reject'
};

const REC_TEXT: Record<string, string> = {
  accept: '✅ 建议接收', minor_revision: '🔧 小修后接收', major_revision: '📝 大修后复审', reject: '❌ 不建议接收'
};

/** 从双语内容中提取英文原始值，用于推荐文本映射 */
function extractRecommendation(raw: string): string {
  const idx = raw.indexOf(CN_SEPARATOR);
  if (idx !== -1) return raw.slice(0, idx).trim();
  return raw;
}

const BADGE_CLASS: Record<string, string> = {
  error: 'badge-error', warning: 'badge-warning', info: 'badge-info'
};

const REV_EMOJI: Record<string, string> = {
  insertion: '➕ 新增', deletion: '❌ 删除', modification: '🔄 修改'
};

const ISSUE_SEV_CLASS: Record<string, string> = {
  error: 'rule-error', warning: 'rule-warning', info: 'rule-info'
};

const ISSUE_SEV_LABEL: Record<string, string> = {
  error: '❌ 严重', warning: '⚠️ 一般', info: 'ℹ️ 提示'
};

const ISSUE_TYPE_LABEL: Record<string, string> = {
  section_logic: '章节逻辑',
  argument_logic: '论点论据逻辑',
  sentence_coherence: '语句连贯性',
  theme_mismatch: '主题不符'
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
  // 挂载时检查 LLM 是否成功，失败则显示错误而非部分结果
  const [_hasError, setHasError] = useState(report.llm_success === false);

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
        // 尝试解析 LLM 失败的详细错误
        try {
          const errData = await res.json();
          if (errData.error) {
            throw new Error(errData.error);
          }
        } catch {
          // JSON 解析失败，使用默认错误
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
    { label: '📊 总评',           key: 'summary',     count: 0 },
    { label: '🔍 逻辑审查',       key: 'logical',     count: report.logical_review?.coherence_issues.length ?? 0 },
    { label: '🕸️ 知识图谱',        key: 'knowledge',  count: report.logical_review?.knowledge_graph?.nodes?.length ?? 0 },
    { label: '🤖 AI 审阅',       key: 'ai',          count: report.ai_reviews.length },
    { label: '✍️ 修订痕迹',      key: 'revisions',   count: report.revisions.length },
    { label: '📝 自动补全',       key: 'completions', count: report.completions.length },
    { label: '✨ 论文润色',       key: 'polished',    count: report.polished_paper ? 1 : 0 },
    { label: '📖 文献综述',       key: 'lit_review',  count: report.literature_review ? 1 : 0 },
    { label: '📚 推荐期刊',        key: 'journals',    count: journals.length },
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
            <span>{report.rules.length} 条规则检查</span>
            <span>{report.logical_review?.coherence_issues.length ?? 0} 条逻辑问题</span>
            <span>{report.ai_reviews.length} 条 AI 审阅</span>
          </p>
          {(() => {
            const raw = extractRecommendation(report.summary.recommendation);
            const display = report.summary.recommendation.includes(CN_SEPARATOR)
              ? report.summary.recommendation
              : (REC_TEXT[raw] ?? report.summary.recommendation);
            return (
              <span className={`recommendation-badge ${REC_CLASS[raw] ?? ''}`}>
                {formatBilingual(display)}
              </span>
            );
          })()}
          {/* 只有 LLM 成功执行才允许下载 */}
          <button
            className="btn btn-download"
            onClick={handleDownload}
            disabled={downloading || report.llm_success === false}
            style={{ marginLeft: 12 }}
          >
            {downloading ? '⏳ 生成中...' : report.llm_success === false ? '❌ LLM 审稿失败，无法下载' : '📥 下载审稿报告'}
          </button>
          {downloadError && (
            <p style={{ marginTop: 10, fontSize: 13, color: 'var(--danger)', background: 'var(--danger-bg)', padding: '8px 14px', borderRadius: 8 }}>
              ❌ {downloadError}
            </p>
          )}
          {report.llm_success === false && report.error_messages?.length && (
            <div style={{ marginTop: 12, fontSize: 13, color: 'var(--danger)', background: 'var(--danger-bg)', padding: '10px 14px', borderRadius: 8 }}>
              <strong>❌ 审稿失败原因：</strong>
              <ul style={{ margin: '6px 0 0 0', paddingLeft: 20 }}>
                {report.error_messages.map((msg, i) => (
                  <li key={i}>{msg}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>

      {/* ── LLM 失败错误提示 ───────────────────── */}
      {_hasError && (
        <div className="card error-card" style={{ marginBottom: 24 }}>
          <div className="card-title" style={{ color: 'var(--danger)' }}>❌ 审稿失败</div>
          <p style={{ fontSize: 14, color: 'var(--gray-700)' }}>
            LLM 审稿服务异常，无法生成审稿报告。
            {report.error_messages?.length ? (
              <ul style={{ margin: '8px 0 0 0', paddingLeft: 20 }}>
                {report.error_messages.map((msg, i) => (
                  <li key={i}>{msg}</li>
                ))}
              </ul>
            ) : null}
          </p>
          <p style={{ fontSize: 13, color: 'var(--gray-500)', marginTop: 8 }}>
            请检查代理服务是否正常运行后，重新提交论文审稿。
          </p>
        </div>
      )}

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
                <div key={i} className="list-item strength">{formatBilingual(s)}</div>
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
                <div key={i} className="list-item weakness">{formatBilingual(w)}</div>
              ))
            )}
          </div>
        </>
      )}

      {/* ── Tab 1: 逻辑连贯性审查 ─────────────────── */}
      {activeTab === 1 && (
        <div className="card">
          <div className="card-title">🔍 逻辑连贯性审查</div>
          {!report.logical_review ? (
            <div className="empty-state">
              <div className="empty-state-icon">🔍</div>
              <p>暂无逻辑审查结果 — 可能是 LLM 未能生成逻辑连贯性审查</p>
            </div>
          ) : (
            <>
              {/* 研究主题分析 */}
              {report.logical_review.research_theme && (
                <div className="card" style={{ marginBottom: 16 }}>
                  <div className="card-title">📌 研究主题分析</div>
                  <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>{formatBilingual(report.logical_review.research_theme)}</div>
                </div>
              )}

              {/* 研究路线图 / 整体框架 */}
              {report.logical_review.research_framework && (
                <div className="card" style={{ marginBottom: 16 }}>
                  <div className="card-title">🗺️ 研究路线图 / 整体框架</div>
                  <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>{formatBilingual(report.logical_review.research_framework)}</div>
                </div>
              )}

              {/* 总体评价 */}
              {report.logical_review.overall_assessment && (
                <div className="card" style={{ marginBottom: 16 }}>
                  <div className="card-title">总体评价</div>
                  <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>{formatBilingual(report.logical_review.overall_assessment)}</div>
                </div>
              )}

              {/* 章节与段落逻辑 */}
              {report.logical_review.section_logic.length > 0 && (
                <div className="card" style={{ marginBottom: 16 }}>
                  <div className="card-title">📑 章节与段落逻辑</div>
                  {report.logical_review.section_logic.map((s, i) => (
                    <div key={i} className="list-item" style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>{formatBilingual(s)}</div>
                  ))}
                </div>
              )}

              {/* 论点与论据逻辑 */}
              {report.logical_review.argument_logic.length > 0 && (
                <div className="card" style={{ marginBottom: 16 }}>
                  <div className="card-title">⚖️ 论点与论据逻辑</div>
                  {report.logical_review.argument_logic.map((a, i) => (
                    <div key={i} className="list-item" style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>{formatBilingual(a)}</div>
                  ))}
                </div>
              )}

              {/* 逻辑问题检测 */}
              {report.logical_review.coherence_issues.length > 0 && (
                <div className="card" style={{ marginBottom: 16 }}>
                  <div className="card-title">⚠️ 检测到的逻辑问题</div>
                  {report.logical_review.coherence_issues.map((ci, i) => (
                    <div key={i} className={`rule-item ${ISSUE_SEV_CLASS[ci.severity] ?? 'rule-info'}`}>
                      <div className="rule-title">
                        <span className={`badge ${BADGE_CLASS[ci.severity] ?? 'badge-info'}`}>{ISSUE_SEV_LABEL[ci.severity] ?? ci.severity}</span>
                        {' '}{ISSUE_TYPE_LABEL[ci.issue_type] ?? ci.issue_type}
                        {ci.location && <><span className="rev-location">📍{ci.location}</span></>}
                      </div>
                      <div className="rule-desc">{formatBilingual(ci.description)}</div>
                      {ci.suggestion && <div className="rule-suggestion">💡 {formatBilingual(ci.suggestion)}</div>}
                    </div>
                  ))}
                </div>
              )}

              {/* 主题一致性 */}
              {report.logical_review.theme_consistency.length > 0 && (
                <div className="card" style={{ marginBottom: 16 }}>
                  <div className="card-title">🎯 主题一致性评价</div>
                  {report.logical_review.theme_consistency.map((t, i) => (
                    <div key={i} className="list-item" style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>{formatBilingual(t)}</div>
                  ))}
                </div>
              )}

              {(!report.logical_review.research_theme || report.logical_review.research_theme === '') &&
               (!report.logical_review.research_framework || report.logical_review.research_framework === '') &&
               report.logical_review.overall_assessment === '' &&
               report.logical_review.section_logic.length === 0 &&
               report.logical_review.argument_logic.length === 0 &&
               report.logical_review.coherence_issues.length === 0 &&
               report.logical_review.theme_consistency.length === 0 && (
                <div className="empty-state">
                  <p>逻辑连贯性审查已生成，但未发现具体问题</p>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ── Tab 2: 知识图谱 ────────────────────────── */}
      {activeTab === 2 && (
        <div className="card">
          <div className="card-title">🕸️ 知识图谱</div>
          {!report.logical_review?.knowledge_graph?.nodes?.length ? (
            <div className="empty-state">
              <div className="empty-state-icon">🕸️</div>
              <p>暂无知识图谱 — LLM 未能提取知识结构</p>
            </div>
          ) : (
            <>
              {report.logical_review?.knowledge_graph?.summary && (
                <div style={{ marginBottom: 16 }}>
                  <div style={{ fontWeight: 700, marginBottom: 8 }}>📋 图谱结构：</div>
                  <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>{formatBilingual(report.logical_review.knowledge_graph.summary)}</div>
                </div>
              )}
              <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
                {(['theory', 'method', 'concept', 'result', 'variable', 'finding'] as const).map(type => {
                  const kg = report.logical_review?.knowledge_graph;
                  const count = kg?.nodes.filter(n => n.type === type).length ?? 0;
                  if (count === 0) return null;
                  const typeNames: Record<string, string> = { theory: '理论', method: '方法', concept: '概念', result: '结果', variable: '变量', finding: '发现' };
                  return (
                    <span key={type} className="badge badge-info">{typeNames[type]}：{count}</span>
                  );
                }).filter(Boolean)}
              </div>
              <div style={{ width: '100%', height: 500, border: '1px solid var(--gray-200)', borderRadius: 8, overflow: 'hidden' }}>
                <KnowledgeGraphVisualization
                  nodes={report.logical_review?.knowledge_graph?.nodes ?? []}
                  edges={report.logical_review?.knowledge_graph?.edges ?? []}
                />
              </div>
            </>
          )}
        </div>
      )}

      {/* ── Tab 3: AI 审阅 ─────────────────────────── */}
      {activeTab === 3 && (
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
                <div className="review-comment" style={{ whiteSpace: 'pre-wrap' }}>
                  {formatBilingual(r.review_comment)}
                </div>
                {r.original_text && (
                  <div className="review-original">
                    <strong>原文片段</strong>
                    <span style={{ whiteSpace: 'pre-wrap', fontSize: 13 }}>{r.original_text.slice(0, 300)}</span>
                  </div>
                )}
                {r.suggestion && (
                  <div className="review-suggestion">
                    💡 {formatBilingual(r.suggestion)}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* ── Tab 3: 修订痕迹 ────────────────────────── */}
      {activeTab === 4 && (
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
      {activeTab === 5 && (
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
                <div className="completion-content">{formatBilingual(c.generated_content)}</div>
              </div>
            ))
          )}
        </div>
      )}

      {/* ── Tab 6: 论文润色 ──────────────────────── */}
      {activeTab === 6 && (
        <div className="card">
          <div className="card-title">✨ 论文润色（SCI 级学术文稿）</div>

          {/* 🆕 人工审核提示 */}
          <div style={{
            background: 'var(--warning-bg)',
            border: '1px solid var(--warning-border)',
            borderRadius: 8,
            padding: '12px 16px',
            marginBottom: 16,
            fontSize: 13,
            color: '#92400e',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}>
            <span style={{ fontSize: 18 }}>⚠️</span>
            <span>
              <strong>审核提醒：</strong>
              润色内容由 AI 自动生成，建议您快速浏览全文，检查是否存在异常重复词、截断或不连贯之处，再进行下载使用。
            </span>
          </div>

          {!report.polished_paper ? (
            <div className="empty-state">
              <div className="empty-state-icon">✨</div>
              <p>暂无润色结果 — 可能是 LLM 未能生成润色内容</p>
            </div>
          ) : (
            <div className="polished-text" style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>
              {formatBilingual(report.polished_paper)}
            </div>
          )}
        </div>
      )}

      {/* ── Tab 6: 文献综述 ──────────────────────── */}
      {activeTab === 7 && (
        <div className="card">
          <div className="card-title">📖 文献综述</div>
          {!report.literature_review ? (
            <div className="empty-state">
              <div className="empty-state-icon">📖</div>
              <p>暂无文献综述结果 — 可能是 LLM 未能生成综述内容</p>
            </div>
          ) : (
            <div className="lit-review-text" style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>
              {formatBilingual(report.literature_review)}
            </div>
          )}
        </div>
      )}

      {/* ── Tab 7: 推荐期刊 ────────────────────────── */}
      {activeTab === 8 && (
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

/* ── 知识图谱可视化组件 ─────────────────────────────────── */

import { useEffect, useRef } from 'react';
import type { KnowledgeGraphNode, KnowledgeGraphEdge } from '../types';

const NODE_COLORS: Record<string, string> = {
  theory: '#6366f1',
  method: '#06b6d4',
  concept: '#8b5cf6',
  result: '#f59e0b',
  variable: '#10b981',
  finding: '#ef4444',
};

function KnowledgeGraphVisualization({
  nodes,
  edges,
}: {
  nodes: KnowledgeGraphNode[];
  edges: KnowledgeGraphEdge[];
}) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || !nodes.length) return;

    const svg = d3.select(svgRef.current);
    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;

    // Clear previous
    svg.selectAll('*').remove();

    const simulation = d3.forceSimulation<KnowledgeGraphNode>(nodes)
      .force('link', d3.forceLink<KnowledgeGraphNode, KnowledgeGraphEdge>(edges).id(d => d.id).distance(120))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(40));

    const linkGroup = svg.append('g').attr('class', 'links');
    const link = linkGroup.selectAll('line')
      .data(edges)
      .join('line')
      .attr('stroke', '#cbd5e1')
      .attr('stroke-width', 1.5);

    const linkLabel = linkGroup.selectAll('text')
      .data(edges)
      .join('text')
      .attr('font-size', 9)
      .attr('fill', '#94a3b8')
      .text(d => d.label);

    const nodeGroup = svg.append('g').attr('class', 'nodes');
    const node = nodeGroup.selectAll('g')
      .data(nodes)
      .join('g');

    const drag = d3.drag<any, KnowledgeGraphNode>()
      .on('start', (_event, d) => {
        if (!_event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on('drag', (_event, d) => {
        d.fx = _event.x;
        d.fy = _event.y;
      });

    node.call(drag);

    node.append('circle')
      .attr('r', 22)
      .attr('fill', d => NODE_COLORS[d.type] || '#94a3b8')
      .attr('stroke', '#fff')
      .attr('stroke-width', 2);

    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .attr('fill', '#fff')
      .attr('font-size', 10)
      .attr('font-weight', 700)
      .text(d => d.label.slice(0, 4));

    node.append('title').text(d => d.label);

    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', 35)
      .attr('font-size', 9)
      .attr('fill', '#475569')
      .text(d => d.label);

    simulation.on('tick', () => {
      link
        .attr('x1', (d: KnowledgeGraphEdge) => ((d.source as unknown as KnowledgeGraphNode).x ?? 0))
        .attr('y1', (d: KnowledgeGraphEdge) => ((d.source as unknown as KnowledgeGraphNode).y ?? 0))
        .attr('x2', (d: KnowledgeGraphEdge) => ((d.target as unknown as KnowledgeGraphNode).x ?? 0))
        .attr('y2', (d: KnowledgeGraphEdge) => ((d.target as unknown as KnowledgeGraphNode).y ?? 0));

      linkLabel
        .attr('x', (d: KnowledgeGraphEdge) => (((d.source as unknown as KnowledgeGraphNode).x ?? 0) + ((d.target as unknown as KnowledgeGraphNode).x ?? 0)) / 2)
        .attr('y', (d: KnowledgeGraphEdge) => (((d.source as unknown as KnowledgeGraphNode).y ?? 0) + ((d.target as unknown as KnowledgeGraphNode).y ?? 0)) / 2 - 4)
        .attr('text-anchor', 'middle');

      node.attr('transform', (d: KnowledgeGraphNode) => `translate(${d.x}, ${d.y})`);
    });

    // Add click to highlight connected nodes
    node.on('click', (_event: MouseEvent, d: KnowledgeGraphNode) => {
      const connected = new Set<string>();
      edges.forEach(e => {
        if (e.source === d.id) connected.add(e.target);
        if (e.target === d.id) connected.add(e.source);
      });
      connected.add(d.id);
      const connectedNodeIds = Array.from(connected);

      svg.selectAll('.nodes circle')
        .transition().duration(300)
        .attr('opacity', n => connectedNodeIds.includes((n as KnowledgeGraphNode).id) ? 1 : 0.15)
        .attr('r', n => connectedNodeIds.includes((n as KnowledgeGraphNode).id) ? ((n as KnowledgeGraphNode).id === d.id ? 28 : 22) : 10);

      svg.selectAll('.links line')
        .transition().duration(300)
        .attr('opacity', e => { const ed = e as unknown as KnowledgeGraphEdge; const src = ed.source as unknown as KnowledgeGraphNode; const tgt = ed.target as unknown as KnowledgeGraphNode; return (src.id === d.id || tgt.id === d.id) ? 1 : 0.1; })
        .attr('stroke', e => { const ed = e as unknown as KnowledgeGraphEdge; const src = ed.source as unknown as KnowledgeGraphNode; const tgt = ed.target as unknown as KnowledgeGraphNode; return (src.id === d.id || tgt.id === d.id) ? (NODE_COLORS[d.type] || '#94a3b8') : '#cbd5e1'; });

      svg.selectAll('.links text')
        .transition().duration(300)
        .attr('opacity', e => { const ed = e as unknown as KnowledgeGraphEdge; const src = ed.source as unknown as KnowledgeGraphNode; const tgt = ed.target as unknown as KnowledgeGraphNode; return (src.id === d.id || tgt.id === d.id) ? 1 : 0.1; });
    });

    return () => {
      simulation.stop();
      svg.selectAll('*').remove();
    };
  }, [nodes, edges]);

  return <svg ref={svgRef} style={{ width: '100%', height: '100%' }} />;
}
