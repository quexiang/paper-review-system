import React, { useState, useRef, useCallback } from 'react';
import type { CompletionReport } from '../types';
import { useReview } from '../hooks/useReview';

interface ModelInfo {
  name: string;
  desc: string;
}

interface UploadPageProps {
  onSubmitted: (report: CompletionReport) => void;
  selectedModel: string;
  availableModels: ModelInfo[];
  onModelChange: (model: string) => void;
}

const SUPPORTED_TYPES = ['.pdf', '.docx', '.txt', '.md'];

function UploadPage({ onSubmitted, selectedModel, availableModels, onModelChange }: UploadPageProps) {
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const { review, loading, error, progress } = useReview();
  const fileRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) setFile(dropped);
  }, []);

  const handleSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) setFile(selected);
  };

  const handleSubmit = async () => {
    if (!file) return;
    const result = await review(file, selectedModel);
    if (result) onSubmitted(result);
  };

  const fileName = file ? file.name : '未选择文件';
  const fileSize = file ? (file.size / 1024).toFixed(1) + ' KB' : '';
  const ext = file?.name.split('.').pop()?.toLowerCase() || '';
  const isSupported = SUPPORTED_TYPES.includes('.' + ext);

  return (
    <div>
      {/* 上传区域 */}
      <div
        className={`upload-zone ${dragOver ? 'dragging' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileRef.current?.click()}
      >
        <div className="upload-zone-icon">📄</div>
        <h3>拖拽论文文件到此处，或点击选择</h3>
        <p>支持格式：PDF / DOCX / TXT / MD</p>
        {file && (
          <div style={{ marginTop: 16, padding: '8px 16px', background: '#eff6ff', borderRadius: 8, display: 'inline-block' }}>
            <strong>{fileName}</strong> ({fileSize})
            {!isSupported && <span style={{ color: 'var(--danger)', marginLeft: 8 }}>（不支持的格式）</span>}
          </div>
        )}
        <input ref={fileRef} type="file" className="file-input" accept={SUPPORTED_TYPES.join(',')} onChange={handleSelect} />
      </div>

      {/* 提交按钮 */}
      {file && (
        <div style={{ textAlign: 'center', marginTop: 24 }}>
          {/* 模型选择器 */}
          <label className="model-label">
            🤖 大模型：<select
              value={selectedModel}
              onChange={(e) => onModelChange(e.target.value)}
              className="model-select"
            >
              {availableModels.map(m => (
                <option key={m.name} value={m.name}>{m.desc}</option>
              ))}
            </select>
          </label>

          <button className="btn btn-primary" onClick={handleSubmit} disabled={!isSupported || loading}>
            {loading ? '⏳ 审稿中...' : '🔍 开始审阅'}
          </button>
        </div>
      )}

      {/* 加载状态 */}
      {loading && (
        <div style={{ marginTop: 32 }}>
          <div className="loading-overlay">
            <div className="spinner" />
            <div className="loading-text">{progress}</div>
          </div>
        </div>
      )}

      {/* 错误信息 */}
      {error && (
        <div className="card" style={{ background: '#fef2f2', border: '1px solid #fecaca' }}>
          <div className="rule-title" style={{ color: 'var(--danger)' }}>❌ {error}</div>
        </div>
      )}

      {/* 使用说明 */}
      {!loading && (
        <div className="card" style={{ marginTop: 32, background: 'linear-gradient(135deg, #f0f9ff, #f0fdf4)' }}>
          <div className="card-title">📖 使用说明</div>
          <div style={{ fontSize: 14, color: 'var(--gray-600)', lineHeight: 2 }}>
            <p><strong>1. 上传论文：</strong>支持 PDF、Word DOCX、TXT、Markdown 格式</p>
            <p><strong>2. 规则检查：</strong>系统自动检测章节完整性、格式规范、引用匹配等</p>
            <p><strong>3. AI 审阅：</strong>大模型对论文进行语义级深度审阅，提供修改建议</p>
            <p><strong>4. 自动补全：</strong>对缺失章节生成内容草稿，以审阅模式展示</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default UploadPage;
