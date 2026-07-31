import { useState, useCallback } from 'react';
import type { CompletionReport } from '../types';

export function useReview() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [progress, setProgress] = useState('');

  const review = useCallback(async (file: File, model?: string) => {
    setLoading(true);
    setError('');
    setProgress('正在解析论文内容...');

    try {
      const fd = new FormData();
      fd.append('file', file, file.name);
      if (model) fd.append('model', model);
      setProgress('正在执行规则检查...');
      const res = await fetch('/api/review', { method: 'POST', body: fd });
      if (!res.ok) {
        // 尝试解析错误响应中的详细消息
        try {
          const errData = await res.json();
          if (errData.error) {
            throw new Error(errData.error + (errData.messages ? '\n' + errData.messages.join('\n') : ''));
          }
        } catch {
          throw new Error(`审稿失败: ${res.status}`);
        }
        throw new Error(`审稿失败: ${res.status}`);
      }
      setProgress('正在执行 AI 审阅...');
      const data: CompletionReport = await res.json();
      setLoading(false);
      // 如果 LLM 失败了，返回 null 让前端显示错误而不是跳转到结果页
      if (data && data.llm_success === false) {
        const msgs = data.error_messages?.join('\n') || 'LLM 审稿服务不可用';
        setError(msgs);
        return null;
      }
      return data;
    } catch (e: any) {
      setError(e.message);
      setLoading(false);
      return null;
    }
  }, []);

  return { review, loading, error, progress };
}
