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
        <span className="upload-zone-icon">📄</span>
        <h3>拖拽论文文件到此处，或点击选择</h3>
        <p>支持 PDF / DOCX / TXT / Markdown 格式</p>
        {file && (
          <div className={`file-chip ${!isSupported ? 'unsupported' : ''}`}>
            {isSupported ? '📎' : '⚠️'} {fileName} ({fileSize})
            {!isSupported && ' — 不支持的格式'}
          </div>
        )}
        <input ref={fileRef} type="file" className="file-input" accept={SUPPORTED_TYPES.join(',')} onChange={handleSelect} />
      </div>

      {/* 提交区域 */}
      {file && (
        <div className="submit-area">
          <div className="model-selector">
            <label>🤖 审稿模型</label>
            <select
              value={selectedModel}
              onChange={(e) => onModelChange(e.target.value)}
              className="model-select"
            >
              {availableModels.map(m => (
                <option key={m.name} value={m.name}>{m.desc}</option>
              ))}
            </select>
          </div>

          <button className="btn btn-primary" onClick={handleSubmit} disabled={!isSupported || loading}>
            {loading ? '⏳ 审稿中...' : '🔍 开始审阅'}
          </button>
        </div>
      )}

      {/* 加载状态 */}
      {loading && (
        <div className="loading-overlay">
          <div className="spinner" />
          <div className="loading-text">{progress}</div>
        </div>
      )}

      {/* 错误信息 */}
      {error && (
        <div className="card error-card" style={{ marginTop: 24 }}>
          <div className="card-title" style={{ color: 'var(--danger)' }}>❌ 审稿失败</div>
          <p style={{ fontSize: 14, color: 'var(--gray-700)' }}>{error}</p>
        </div>
      )}

      {/* 使用说明 */}
      {!loading && (
        <div className="card guide-card" style={{ marginTop: 32 }}>
          <div className="card-title">📖 使用说明</div>
          <div className="guide-list">
            <p><strong>1. 上传论文：</strong>支持 PDF、Word DOCX、TXT、Markdown 格式</p>
            <p><strong>2. 选择模型：</strong>挑选适合的大模型进行审稿，不同模型视角各异</p>
            <p><strong>3. 规则检查：</strong>系统自动检测章节完整性、格式规范、引用匹配等</p>
            <p><strong>4. AI 审阅：</strong>大模型对论文进行语义级深度审阅，提供修改建议</p>
            <p><strong>5. 自动补全：</strong>对缺失章节生成内容草稿，以审阅模式展示</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default UploadPage;
