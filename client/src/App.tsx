import React, { useState } from 'react';
import UploadPage from './pages/UploadPage';
import ResultPage from './pages/ReviewResultPage';
import HistoryPage from './pages/HistoryPage';
import LoginPage from './pages/LoginPage';
import type { CompletionReport, HistoryRecord } from './types';

type Page = 'upload' | 'result' | 'history' | 'login';

interface ModelInfo {
  name: string;
  desc: string;
}

function App() {
  const [page, setPage] = useState<Page>('upload');
  const [report, setReport] = useState<CompletionReport | null>(null);
  const [history, setHistory] = useState<HistoryRecord[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([]);
  const [checkingModels, setCheckingModels] = useState(false);
  const [authToken, setAuthToken] = useState<string | null>(
    typeof window !== 'undefined' ? localStorage.getItem('review_token') : null
  );
  // 每次切换到提交页面时重新探测代理可用性
  const [modelsVersion, setModelsVersion] = useState(0);

  const handleLogin = (token: string) => {
    setAuthToken(token);
    setPage('history');
  };

  const handleLogout = () => {
    setAuthToken(null);
    localStorage.removeItem('review_token');
    setPage('upload');
  };

  // 加载可用模型列表（每次切换到提交页面时重新探测代理可用性）
  React.useEffect(() => {
    setCheckingModels(true);
    fetch(`/api/models?force=${modelsVersion}`)
      .then(r => r.json())
      .then(data => {
        setAvailableModels(data);
        if (data.length > 0) setSelectedModel(data[0].name);
      })
      .catch(() => {})
      .finally(() => setCheckingModels(false));
  }, [modelsVersion]);

  const showResult = (r: CompletionReport) => {
    setReport(r);
    setPage('result');
  };

  const loadHistory = async () => {
    if (!authToken) {
      setPage('login');
      return;
    }
    try {
      const res = await fetch('/api/history', {
        headers: { 'Authorization': `Bearer ${authToken}` },
      });
      if (!res.ok) {
        if (res.status === 401) {
          handleLogout();
          setPage('login');
          return;
        }
        throw new Error('加载历史记录失败');
      }
      const data = await res.json();
      setHistory(data);
    } catch {}
    setPage('history');
  };

  const goUpload = () => {
    setModelsVersion(v => v + 1); // 每次进入提交页面重新探测代理
    setPage('upload');
  };

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
          <button className={page === 'history' ? 'active' : ''} onClick={loadHistory}>
            📋 历史记录
          </button>
          {page === 'login' && (
            <button className="btn" onClick={() => setPage('upload')}>← 返回</button>
          )}
        </nav>
      </header>

      <main className="main-content">
        {page === 'upload' && (
          <UploadPage
            onSubmitted={showResult}
            selectedModel={selectedModel}
            availableModels={availableModels}
            onModelChange={setSelectedModel}
            checkingModels={checkingModels}
          />
        )}
        {page === 'result' && report && <ResultPage report={report} />}
        {page === 'history' && authToken && <HistoryPage records={history} onLogout={handleLogout} />}
        {page === 'login' && <LoginPage onLogin={handleLogin} onBack={goUpload} />}
      </main>
    </div>
  );
}

export default App;
