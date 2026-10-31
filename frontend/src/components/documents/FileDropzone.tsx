import React, { useState, useRef } from 'react';
import { UploadCloud, File, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import { documentsApi } from '../../api/client';

interface FileDropzoneProps {
  onUploadComplete: () => void;
}

export const FileDropzone: React.FC<FileDropzoneProps> = ({ onUploadComplete }) => {
  const [isDragging, setIsDragging] = useState(false);
  const [uploadingFiles, setUploadingFiles] = useState<{ name: string; progress: number; status: 'uploading' | 'done' | 'error'; error?: string }[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;

    const fileList = Array.from(files);
    const newItems = fileList.map((f) => ({
      name: f.name,
      progress: 20,
      status: 'uploading' as const,
    }));
    setUploadingFiles((prev) => [...prev, ...newItems]);

    for (let i = 0; i < fileList.length; i++) {
      const file = fileList[i];
      try {
        await documentsApi.upload(file);
        setUploadingFiles((prev) =>
          prev.map((item) =>
            item.name === file.name ? { ...item, progress: 100, status: 'done' } : item
          )
        );
      } catch (err: any) {
        const errorMsg = err.response?.data?.detail || 'Upload failed';
        setUploadingFiles((prev) =>
          prev.map((item) =>
            item.name === file.name ? { ...item, status: 'error', error: errorMsg } : item
          )
        );
      }
    }

    onUploadComplete();
  };

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const onDragLeave = () => {
    setIsDragging(false);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  return (
    <div className="space-y-4">
      <div
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all ${
          isDragging
            ? 'border-brand-500 bg-brand-500/5 dark:bg-brand-500/10 scale-[1.01]'
            : 'border-slate-300 dark:border-slate-800 hover:border-brand-400 dark:hover:border-slate-700 bg-slate-50/50 dark:bg-slate-900/30'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.txt,.md,.py,.js,.ts,.json"
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
        <div className="flex flex-col items-center justify-center space-y-3">
          <div className="w-12 h-12 rounded-xl bg-brand-500/10 text-brand-600 dark:text-brand-400 flex items-center justify-center border border-brand-500/20 shadow-sm">
            <UploadCloud className="w-6 h-6" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">
              Click to upload or drag and drop PDFs
            </p>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Supports PDF, TXT, Markdown, Python, JSON (Up to 50MB per file)
            </p>
          </div>
          <span className="inline-flex text-[11px] font-medium text-slate-400 bg-slate-200/60 dark:bg-slate-800/60 px-2.5 py-1 rounded-full">
            Automatic chunking & vector indexing enabled
          </span>
        </div>
      </div>

      {/* Upload Progress List */}
      {uploadingFiles.length > 0 && (
        <div className="space-y-2">
          {uploadingFiles.map((item, idx) => (
            <div
              key={`${item.name}-${idx}`}
              className="flex items-center justify-between p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 text-xs"
            >
              <div className="flex items-center space-x-2.5 min-w-0">
                <File className="w-4 h-4 text-slate-400 flex-shrink-0" />
                <span className="font-medium text-slate-800 dark:text-slate-200 truncate max-w-xs">
                  {item.name}
                </span>
              </div>
              <div className="flex items-center space-x-2 flex-shrink-0">
                {item.status === 'uploading' && (
                  <span className="flex items-center text-brand-500">
                    <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> Indexing...
                  </span>
                )}
                {item.status === 'done' && (
                  <span className="flex items-center text-emerald-500 font-medium">
                    <CheckCircle2 className="w-4 h-4 mr-1" /> Indexed
                  </span>
                )}
                {item.status === 'error' && (
                  <span className="flex items-center text-rose-500 font-medium" title={item.error}>
                    <AlertCircle className="w-4 h-4 mr-1" /> {item.error || 'Failed'}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
