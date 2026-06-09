const BASE = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000';

export async function submitReview(file: File) {
  const fd = new FormData();
  fd.append('file', file, file.name);
  const res = await fetch(`${BASE}/api/review`, { method: 'POST', body: fd });
  if (!res.ok) throw new Error(`审稿失败: ${res.status}`);
  return res.json();
}

export async function getHistory() {
  const r = await fetch(`${BASE}/api/history`);
  if (!r.ok) throw new Error('获取历史记录失败');
  return r.json();
}

export async function deleteHistory(id: string) {
  const r = await fetch(`${BASE}/api/history/${id}`, { method: 'DELETE' });
  return r.json();
}
