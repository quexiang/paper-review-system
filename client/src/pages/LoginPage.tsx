import React, { useState } from 'react';

interface Props {
  onLogin: (token: string) => void;
  onBack: () => void;
}

function LoginPage({ onLogin, onBack }: Props) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(data.detail || '登录失败');
      }
      const data = await res.json();
      localStorage.setItem('review_token', data.token);
      onLogin(data.token);
    } catch (e: any) {
      setError(e.message || '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 400, margin: '40px auto' }}>
      <div className="card">
        <div className="card-title">🔐 管理员登录</div>
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', marginBottom: 6, fontSize: 14, fontWeight: 600 }}>用户名</label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              style={{ width: '100%', padding: '10px 12px', border: '1px solid var(--gray-200)', borderRadius: 6, fontSize: 14 }}
              placeholder="请输入用户名"
            />
          </div>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', marginBottom: 6, fontSize: 14, fontWeight: 600 }}>密码</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              style={{ width: '100%', padding: '10px 12px', border: '1px solid var(--gray-200)', borderRadius: 6, fontSize: 14 }}
              placeholder="请输入密码"
            />
          </div>
          {error && (
            <p style={{ color: 'var(--danger)', background: 'var(--danger-bg)', padding: '8px 12px', borderRadius: 6, fontSize: 13, marginBottom: 12 }}>
              ❌ {error}
            </p>
          )}
          <div style={{ display: 'flex', gap: 8 }}>
            <button type="submit" className="btn btn-primary" disabled={loading} style={{ flex: 1 }}>
              {loading ? '登录中...' : '登录'}
            </button>
            <button type="button" className="btn" onClick={onBack}>返回</button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default LoginPage;
