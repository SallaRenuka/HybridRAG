import React, { useState, useEffect } from 'react';
import {
  Files,
  Upload,
  Trash2,
  ExternalLink,
  Search,
  CheckCircle2,
  RefreshCw,
  HardDrive,
  FileText,
  AlertTriangle,
  LayoutGrid,
  List,
  Sparkles,
  Layers,
  Clock,
  Database,
} from 'lucide-react';
import { DocumentRecord } from '../types';
import { documentsApi } from '../api/client';
import { FileDropzone } from '../components/documents/FileDropzone';
import { Tilt3DCard } from '../components/3d/Tilt3DCard';

export const DocumentsPage: React.FC = () => {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [viewMode, setViewMode] = useState<'grid' | 'table'>('grid');
  const [isLoading, setIsLoading] = useState(true);
  const [isReindexing, setIsReindexing] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const fetchDocuments = async () => {
    setIsLoading(true);
    try {
      const data = await documentsApi.list();
      setDocuments(data);
    } catch (err) {
      console.error('Failed to load documents:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  const handleDelete = async (docId: number) => {
    if (!window.confirm('Are you sure you want to permanently delete this document and update your vector index?')) {
      return;
    }
    setDeletingId(docId);
    try {
      await documentsApi.delete(docId);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
    } catch (err) {
      console.error('Failed to delete document:', err);
      alert('Error deleting document.');
    } finally {
      setDeletingId(null);
    }
  };

  const handleReindex = async () => {
    setIsReindexing(true);
    try {
      const res = await documentsApi.reindex();
      alert(`Reindexing complete! ${res.chunks_indexed} chunks synchronized across FAISS & BM25.`);
      await fetchDocuments();
    } catch (err) {
      console.error('Reindexing error:', err);
      alert('Reindexing failed.');
    } finally {
      setIsReindexing(false);
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const filteredDocs = documents.filter((d) =>
    d.filename.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="p-6 sm:p-8 space-y-8 max-w-7xl mx-auto font-sans">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border border-cyan-500/20 mb-2">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse" />
            3D Document Management
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white">
            Document Repository
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
            Manage files, inspect chunk distributions, and monitor vector indexing pipelines.
          </p>
        </div>

        <div className="flex items-center space-x-2.5">
          <button
            onClick={handleReindex}
            disabled={isReindexing}
            className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800 text-xs font-semibold text-slate-700 dark:text-slate-200 transition-colors shadow-sm disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-cyan-500 ${isReindexing ? 'animate-spin' : ''}`} />
            {isReindexing ? 'Reindexing...' : 'Re-index Workspace'}
          </button>
          <button
            onClick={() => setShowUploadModal(true)}
            className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white text-xs font-semibold shadow-md shadow-cyan-500/25 transition-all hover:scale-105"
          >
            <Upload className="w-3.5 h-3.5" /> Upload Document
          </button>
        </div>
      </div>

      {/* Filter & View Switcher Bar */}
      <div className="flex items-center justify-between gap-4 glass-panel p-3.5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search documents by name..."
            className="w-full pl-10 pr-4 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-xs text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-cyan-500"
          />
        </div>

        <div className="flex items-center gap-3">
          <div className="text-xs text-slate-500 dark:text-slate-400 font-medium px-2">
            {filteredDocs.length} of {documents.length} documents
          </div>

          <div className="flex items-center border border-slate-200 dark:border-slate-800 rounded-xl p-1 bg-slate-50 dark:bg-slate-950">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-1.5 rounded-lg text-xs transition-colors ${
                viewMode === 'grid'
                  ? 'bg-white dark:bg-slate-800 text-cyan-500 shadow-xs'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="3D Grid View"
            >
              <LayoutGrid className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setViewMode('table')}
              className={`p-1.5 rounded-lg text-xs transition-colors ${
                viewMode === 'table'
                  ? 'bg-white dark:bg-slate-800 text-cyan-500 shadow-xs'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Table View"
            >
              <List className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Grid View: Interactive 3D Document Cards */}
      {viewMode === 'grid' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredDocs.map((doc) => {
            const fileUrl = documentsApi.getFileUrl(doc.id);
            const isIndexed = doc.chunk_count > 0;

            return (
              <Tilt3DCard key={doc.id} glowColor="rgba(6, 182, 212, 0.25)">
                <div className="p-6 space-y-4">
                  {/* Card Header & 3D Document Illustration */}
                  <div className="flex items-start justify-between gap-3">
                    <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-cyan-500/20 via-blue-500/10 to-violet-500/20 text-cyan-400 flex items-center justify-center border border-cyan-500/30 shadow-md">
                      <FileText className="w-6 h-6" />
                    </div>

                    {isIndexed ? (
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-[11px] font-semibold border border-emerald-500/20">
                        <CheckCircle2 className="w-3 h-3" /> Indexed
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-amber-500/10 text-amber-600 dark:text-amber-400 text-[11px] font-semibold border border-amber-500/20">
                        <AlertTriangle className="w-3 h-3" /> Scanned
                      </span>
                    )}
                  </div>

                  {/* Title & Metadata */}
                  <div className="space-y-1">
                    <h3
                      className="text-sm font-bold text-slate-900 dark:text-white truncate"
                      title={doc.filename}
                    >
                      {doc.filename}
                    </h3>
                    <p className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-2">
                      <span>{formatBytes(doc.file_size_bytes)}</span>
                      <span>•</span>
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {new Date(doc.created_at).toLocaleDateString()}
                      </span>
                    </p>
                  </div>

                  {/* Pipeline Processing States */}
                  <div className="pt-2 border-t border-slate-200/60 dark:border-slate-800/60">
                    <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-2">
                      Pipeline Stages
                    </div>
                    <div className="grid grid-cols-4 gap-1 text-[10px] text-center font-medium">
                      <div className="py-1 px-1 rounded bg-cyan-500/10 text-cyan-400">Uploaded</div>
                      <div className="py-1 px-1 rounded bg-blue-500/10 text-blue-400">Extracted</div>
                      <div className="py-1 px-1 rounded bg-violet-500/10 text-violet-400">
                        {doc.chunk_count} Chunks
                      </div>
                      <div
                        className={`py-1 px-1 rounded ${
                          isIndexed
                            ? 'bg-emerald-500/10 text-emerald-400'
                            : 'bg-amber-500/10 text-amber-400'
                        }`}
                      >
                        {isIndexed ? 'Embedded' : 'Pending'}
                      </div>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="pt-2 flex items-center justify-between gap-2 border-t border-slate-200/60 dark:border-slate-800/60">
                    <a
                      href={fileUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-semibold text-slate-700 dark:text-slate-200 transition-colors"
                    >
                      <ExternalLink className="w-3.5 h-3.5" /> Inspect PDF
                    </a>
                    <button
                      onClick={() => handleDelete(doc.id)}
                      disabled={deletingId === doc.id}
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-red-200 dark:border-red-900/40 hover:bg-red-50 dark:hover:bg-red-950/30 text-xs font-semibold text-red-600 dark:text-red-400 transition-colors disabled:opacity-50"
                    >
                      <Trash2 className="w-3.5 h-3.5" /> Delete
                    </button>
                  </div>
                </div>
              </Tilt3DCard>
            );
          })}
        </div>
      )}

      {/* Table View */}
      {viewMode === 'table' && (
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 glass-panel shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-950/70 text-slate-400 uppercase tracking-wider text-[10px]">
                  <th className="py-3.5 px-4 font-semibold">Document Name</th>
                  <th className="py-3.5 px-4 font-semibold">File Size</th>
                  <th className="py-3.5 px-4 font-semibold">Indexed Chunks</th>
                  <th className="py-3.5 px-4 font-semibold">Upload Date</th>
                  <th className="py-3.5 px-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 text-slate-700 dark:text-slate-300">
                {filteredDocs.map((doc) => {
                  const fileUrl = documentsApi.getFileUrl(doc.id);
                  return (
                    <tr key={doc.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                      <td className="py-3.5 px-4 font-medium flex items-center gap-2.5 truncate max-w-sm">
                        <div className="w-7 h-7 rounded-lg bg-cyan-500/10 text-cyan-500 flex items-center justify-center flex-shrink-0">
                          <FileText className="w-4 h-4" />
                        </div>
                        <span className="truncate">{doc.filename}</span>
                      </td>
                      <td className="py-3.5 px-4 text-slate-500">{formatBytes(doc.file_size_bytes)}</td>
                      <td className="py-3.5 px-4">
                        {doc.chunk_count > 0 ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-[11px] font-semibold">
                            <CheckCircle2 className="w-3 h-3" /> {doc.chunk_count} chunks
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-600 dark:text-amber-400 text-[11px] font-semibold">
                            <AlertTriangle className="w-3 h-3" /> Scanned
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-slate-400">
                        {new Date(doc.created_at).toLocaleDateString()}
                      </td>
                      <td className="py-3.5 px-4 text-right space-x-2">
                        <a
                          href={fileUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-[11px] font-medium text-slate-700 dark:text-slate-200 transition-colors"
                        >
                          <ExternalLink className="w-3 h-3" /> View
                        </a>
                        <button
                          onClick={() => handleDelete(doc.id)}
                          disabled={deletingId === doc.id}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-red-200 dark:border-red-900/40 hover:bg-red-50 dark:hover:bg-red-950/30 text-[11px] font-medium text-red-600 dark:text-red-400 transition-colors disabled:opacity-50"
                        >
                          <Trash2 className="w-3 h-3" /> Delete
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Empty State */}
      {filteredDocs.length === 0 && !isLoading && (
        <div className="py-20 text-center space-y-4 glass-panel rounded-3xl border border-slate-200 dark:border-slate-800">
          <div className="w-16 h-16 rounded-3xl bg-cyan-500/10 text-cyan-400 flex items-center justify-center mx-auto border border-cyan-500/20 shadow-lg">
            <Files className="w-8 h-8" />
          </div>
          <h3 className="text-base font-bold text-slate-900 dark:text-white">
            No documents found
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 max-w-sm mx-auto">
            Upload your PDFs, textbooks, or tabular employee records to index them into HybridRAG.
          </p>
          <button
            onClick={() => setShowUploadModal(true)}
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-semibold text-xs shadow-md shadow-cyan-500/25 transition-all"
          >
            Upload Now
          </button>
        </div>
      )}

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-md p-4">
          <div className="w-full max-w-lg glass-panel p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <Upload className="w-4 h-4 text-cyan-500" /> Upload Document
              </h3>
              <button
                onClick={() => setShowUploadModal(false)}
                className="text-xs text-slate-400 hover:text-white p-1"
              >
                ✕
              </button>
            </div>

            <FileDropzone
              onUploadComplete={() => {
                setShowUploadModal(false);
                fetchDocuments();
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
};
