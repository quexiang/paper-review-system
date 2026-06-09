import React from 'react';
import type { HistoryRecord } from '../types';

interface Props {
  records: HistoryRecord[];
}

function getRecBadge(rec: string): string {
  const map: Record<string, string> = {
    accept: 'badge-success', minor_revision: 'badge-warning', major_revision: 'badge-error', reject: 'badge-error'
  };
  return map[rec] || 'badge-info';
}

function getRecText(rec: string): string {
  const map: Record<string, string> = {
    accept: '接收', minor_revision: '小修', major_revision: '大修', reject: '拒稿'
  };
  return map[rec] || rec;
}

function HistoryPage({ records }: Props) {
  return (
    <div className="card">
      <div className="card-title">📋 审稿历史</div>
      {records.length === 0 ? (
        <p style={{ color: 'var(--gray-600)' }}>暂无历史记录</p>
      ) : (
        records.map((r, i) => (
          <div key={r.id} className="history-item">
            <div>
              <div className="history-file">{r.file_name}</div>
              <div className="history-time">{new Date(r.timestamp).toLocaleString('zh-CN')}</div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ fontWeight: 700, fontSize: 20, color: r.summary.score >= 80 ? 'var(--success)' : r.summary.score >= 60 ? '#d97706' : 'var(--danger)' }}>
                {r.summary.score.toFixed(0)}
              </span>
              <span className={`badge ${getRecBadge(r.summary.recommendation)}`}>{getRecText(r.summary.recommendation)}</span>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

export default HistoryPage;
