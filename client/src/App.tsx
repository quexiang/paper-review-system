import React, { useState } from 'react';
import UploadPage from './pages/UploadPage';
import ResultPage from './pages/ReviewResultPage';
import HistoryPage from './pages/HistoryPage';
import type { CompletionReport, HistoryRecord } from './types';

type Page = 'upload' | 'result' | 'history';

function App() {
  const [page, setPage] = useState<Page>('upload');
  const [report, setReport] = useState<CompletionReport | null>(null);
  const [history, setHistory] = useState<HistoryRecord[]>([]);

  const showResult = (r: CompletionReport) => {
    setReport(r);
    setPage('result');
  };

  const loadHistory = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/history');
      if (res.ok) {
        const data = await res.json();
        setHistory(data);
      }
    } catch {}
    setPage('history');
  };

  const goUpload = () => setPage('upload');

  return (
    <div className="app-container">
      <header className="header">
        <h1>📝 学术论文审稿系统</h1>
        <p>智能规则检查 + AI 语义审阅 + 自动补全建议</p>
        <nav className="header-nav">
          <button className={page === 'upload' ? 'active' : ''} onClick={goUpload}>📤 提交稿件</button>
          {report && (
            <button className={page === 'result' ? 'active' : ''} onClick={() => setPage('result')}>
              🔍 审稿结果
            </button>
          )}
          <button className={page === 'history' ? 'active' : ''} onClick={loadHistory}>📋 历史记录</button>
        </nav>
      </header>

      <main className="main-content">
        {page === 'upload' && <UploadPage onSubmitted={showResult} />}
        {page === 'result' && report && <ResultPage report={report} />}
        {page === 'history' && <HistoryPage records={history} />}
      </main>
    </div>
  );
}

export default App;
