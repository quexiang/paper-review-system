import React from 'react';
import type { HistoryRecord } from '../types';

interface Props {
  records: HistoryRecord[];
  onLogout: () => void;
}

const REC_BADGE: Record<string, string> = {
  accept: 'badge-success', minor_revision: 'badge-warning', major_revision: 'badge-error', reject: 'badge-error'
};

const REC_TEXT: Record<string, string> = {
  accept: '接收', minor_revision: '小修', major_revision: '大修', reject: '拒稿'
};

function scoreClass(score: number): string {
  if (score >= 80) return 'score-high';
  if (score >= 60) return 'score-mid';
  return 'score-low';
}

function HistoryPage({ records, onLogout }: Props) {
  const [downloading, setDownloading] = React.useState<string | null>(null);
  const [downloadingOriginal, setDownloadingOriginal] = React.useState<string | null>(null);
  const [downloadingReport, setDownloadingReport] = React.useState<string | null>(null);
  const [downloadError, setDownloadError] = React.useState('');

  const getToken = () => localStorage.getItem('review_token');

  const requestWithAuth = async (url: string, options: RequestInit = {}) => {
    const token = getToken();
    return fetch(url, {
      ...options,
      headers: {
        ...options.headers,
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      },
    });
  };

  const handleDownloadReport = async (id: string) => {
    setDownloadingReport(id);
    setDownloadError('');
    try {
      const res = await requestWithAuth(`/api/download/${id}`);
      if (!res.ok) {
        if (res.status === 404) throw new Error('报告已过期，请重新提交审稿后再下载。');
        const errData = await res.json().catch(() => ({}));
        if (res.status === 401) { onLogout(); return; }
        throw new Error(`下载失败（HTTP ${res.status}），请稍后重试。`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const disposition = res.headers.get('Content-Disposition');
      let filename = '审稿报告.docx';
      if (disposition) {
        const match = disposition.match(/filename\*=UTF-8''(.+)/);
        if (match) filename = decodeURIComponent(match[1]);
      }
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setDownloadError(e.message || '下载失败，请重试');
    } finally {
      setDownloadingReport(null);
    }
  };

  const handleDownloadOriginal = async (id: string, fileName: string) => {
    setDownloadingOriginal(id);
    setDownloadError('');
    try {
      const res = await requestWithAuth(`/api/download-original/${id}`);
      if (!res.ok) {
        if (res.status === 401) { onLogout(); return; }
        if (res.status === 404) throw new Error('原始稿件不存在');
        throw new Error(`下载失败（HTTP ${res.status}）`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const disposition = res.headers.get('Content-Disposition');
      let filename = fileName.includes('.')
        ? fileName.split('.').slice(0, -1).join('.') + '-original.' + fileName.split('.').pop()!
        : fileName + '-original';
      if (disposition) {
        const match = disposition.match(/filename\*=UTF-8''(.+)/);
        if (match) filename = decodeURIComponent(match[1]);
      }
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setDownloadError(e.message || '下载失败，请重试');
    } finally {
      setDownloadingOriginal(null);
    }
  };

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div className="card-title">📋 审稿历史（最近 10 篇）</div>
        <button className="btn" onClick={onLogout}>退出登录</button>
      </div>
      {records.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">📋</div>
          <p>暂无历史记录 — 提交论文审稿后将在这里显示</p>
        </div>
      ) : (
        <>
          <div style={{ marginBottom: 12, fontSize: 13, color: 'var(--gray-500)' }}>
            共 {records.length} 篇 — 仅保留最近 10 篇
          </div>
          {records.map((r) => (
            <div key={r.id} className="history-item">
              <div>
                <div className="history-file">{r.file_name}</div>
                <div className="history-time">{new Date(r.timestamp).toLocaleString('zh-CN')}</div>
              </div>
              <div className="history-score-wrap">
                {r.llm_success === false ? (
                  <span className="badge badge-error">❌ LLM 审稿失败</span>
                ) : (
                  <>
                    <div className={`history-score ${scoreClass(r.summary.score)}`}>
                      {r.summary.score.toFixed(0)}
                    </div>
                    <span className={`badge ${REC_BADGE[r.summary.recommendation] ?? 'badge-info'}`}>
                      {REC_TEXT[r.summary.recommendation] ?? r.summary.recommendation}
                    </span>
                  </>
                )}
              </div>
              <div style={{ display: 'flex', alignItems: 'center' }}>
                <button
                  className="btn btn-download"
                  onClick={() => handleDownloadReport(r.id)}
                  disabled={downloadingReport === r.id || r.llm_success === false}
                  style={{ marginLeft: 8 }}
                >
                  {downloadingReport === r.id ? '⏳ 生成中...' : '📥 下载审稿报告'}
                </button>
                <button
                  className="btn btn-download"
                  onClick={() => handleDownloadOriginal(r.id, r.file_name)}
                  disabled={downloadingOriginal === r.id}
                  style={{ marginLeft: 4 }}
                >
                  {downloadingOriginal === r.id ? '⏳ 生成中...' : '📄 原始稿件'}
                </button>
              </div>
            </div>
          ))}
          {downloadError && (
            <p style={{ marginTop: 12, fontSize: 13, color: 'var(--danger)', background: 'var(--danger-bg)', padding: '8px 14px', borderRadius: 8 }}>
              ❌ {downloadError}
            </p>
          )}
        </>
      )}
    </div>
  );
}

export default HistoryPage;
