import React from 'react';
import type { HistoryRecord } from '../types';

interface Props {
  records: HistoryRecord[];
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

function HistoryPage({ records }: Props) {
  return (
    <div className="card">
      <div className="card-title">📋 审稿历史</div>
      {records.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">📋</div>
          <p>暂无历史记录 — 提交论文审稿后将在这里显示</p>
        </div>
      ) : (
        records.map((r) => (
          <div key={r.id} className="history-item">
            <div>
              <div className="history-file">{r.file_name}</div>
              <div className="history-time">{new Date(r.timestamp).toLocaleString('zh-CN')}</div>
            </div>
            <div className="history-score-wrap">
              <div className={`history-score ${scoreClass(r.summary.score)}`}>
                {r.summary.score.toFixed(0)}
              </div>
              <span className={`badge ${REC_BADGE[r.summary.recommendation] ?? 'badge-info'}`}>
                {REC_TEXT[r.summary.recommendation] ?? r.summary.recommendation}
              </span>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

export default HistoryPage;
