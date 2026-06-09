import { useState, useCallback } from 'react';
import type { CompletionReport } from '../types';

export function useReview() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [progress, setProgress] = useState('');

  const review = useCallback(async (file: File) => {
    setLoading(true);
    setError('');
    setProgress('正在解析论文内容...');

    try {
      const fd = new FormData();
      fd.append('file', file, file.name);
      setProgress('正在执行规则检查...');
      const res = await fetch('http://localhost:8000/api/review', { method: 'POST', body: fd });
      if (!res.ok) throw new Error(`审稿失败: ${res.status}`);
      setProgress('正在执行 AI 审阅...');
      const data: CompletionReport = await res.json();
      setLoading(false);
      return data;
    } catch (e: any) {
      setError(e.message);
      setLoading(false);
      return null;
    }
  }, []);

  return { review, loading, error, progress };
}
