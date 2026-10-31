import React, { useState } from 'react';
import { X, FileText, ExternalLink, BookOpen, Layers, CheckCircle2 } from 'lucide-react';
import { Citation, DocumentRecord } from '../../types';
import { documentsApi } from '../../api/client';

interface SourceDrawerProps {
  citation: Citation | null;
  onClose: () => void;
  documents: DocumentRecord[];
}

export const SourceDrawer: React.FC<SourceDrawerProps> = ({ citation, onClose, documents }) => {
  const [viewMode, setViewMode] = useState<'text' | 'pdf'>('text');

  if (!citation) return null;

  // Find corresponding document record to get ID for file endpoint
  const matchedDoc = documents.find(
    (d) => d.filename.toLowerCase() === citation.source.toLowerCase()
  );

  const fileUrl = matchedDoc ? documentsApi.getFileUrl(matchedDoc.id) : null;
  const pageParam = citation.page ? `#page=${citation.page}` : '';
  const fullPdfUrl = fileUrl ? `${fileUrl}${pageParam}` : null;

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-[500px] lg:w-[600px] bg-white dark:bg-slate-900 border-l border-slate-200 dark:border-slate-800 shadow-2xl flex flex-col transition-all animate-in slide-in-from-right duration-200">
      {/* Drawer Header */}
      <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-950/50">
        <div className="flex items-center space-x-2.5 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-brand-500/10 text-brand-600 dark:text-brand-400 flex items-center justify-center font-bold text-sm border border-brand-500/20">
            [{citation.id}]
          </div>
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 truncate">
              {citation.source}
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {citation.page ? `Page ${citation.page}` : 'Document Excerpt'} • Chunk: {citation.chunk_id.split('::').pop()}
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {fullPdfUrl && (
            <a
              href={fullPdfUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1.5 text-slate-500 hover:text-brand-600 dark:text-slate-400 dark:hover:text-brand-400 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              title="Open raw PDF in new tab"
            >
              <ExternalLink className="w-4 h-4" />
            </a>
          )}
          <button
            onClick={onClose}
            className="p-1.5 text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Tabs: Text Passage vs Embedded PDF */}
      <div className="flex border-b border-slate-200 dark:border-slate-800 bg-slate-100/60 dark:bg-slate-950/40 p-1">
        <button
          onClick={() => setViewMode('text')}
          className={`flex-1 py-1.5 px-3 rounded-md text-xs font-medium flex items-center justify-center gap-1.5 transition-colors ${
            viewMode === 'text'
              ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-sm'
              : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
          }`}
        >
          <FileText className="w-3.5 h-3.5" /> Passage Excerpt
        </button>
        {fullPdfUrl && (
          <button
            onClick={() => setViewMode('pdf')}
            className={`flex-1 py-1.5 px-3 rounded-md text-xs font-medium flex items-center justify-center gap-1.5 transition-colors ${
              viewMode === 'pdf'
                ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-sm'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            <BookOpen className="w-3.5 h-3.5" /> PDF Viewer (Page {citation.page || 1})
          </button>
        )}
      </div>

      {/* Drawer Body */}
      <div className="flex-1 overflow-y-auto p-5">
        {viewMode === 'text' ? (
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-xs font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-3 py-1.5 rounded-lg border border-emerald-500/20">
              <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
              Verified source evidence used by retrieval pipeline
            </div>

            <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 p-4 font-mono text-xs leading-relaxed text-slate-800 dark:text-slate-200 whitespace-pre-wrap select-text">
              {citation.text}
            </div>

            <div className="p-3 rounded-lg border border-slate-200/60 dark:border-slate-800/60 bg-slate-100/50 dark:bg-slate-900/50 space-y-2">
              <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider block">
                Metadata Verification
              </span>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-slate-400">File:</span>{' '}
                  <span className="font-medium text-slate-800 dark:text-slate-200">{citation.source}</span>
                </div>
                <div>
                  <span className="text-slate-400">Page:</span>{' '}
                  <span className="font-medium text-slate-800 dark:text-slate-200">
                    {citation.page !== null ? citation.page : 'N/A'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="h-full flex flex-col">
            {fullPdfUrl ? (
              <iframe
                src={fullPdfUrl}
                title="Source PDF Document Preview"
                className="w-full flex-1 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-100 dark:bg-slate-950"
              />
            ) : (
              <div className="p-8 text-center text-slate-400 text-xs">
                PDF preview not available for this document.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
