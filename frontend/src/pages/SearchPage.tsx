import React, { useState } from 'react';
import {
  Search,
  Sliders,
  FileText,
  ExternalLink,
  BookOpen,
  Layers,
  Sparkles,
  Loader2,
  CheckCircle2,
} from 'lucide-react';
import { SearchResultItem, DocumentRecord } from '../types';
import { searchApi, documentsApi } from '../api/client';
import { SourceDrawer } from '../components/chat/SourceDrawer';

export const SearchPage: React.FC = () => {
  const [query, setQuery] = useState('');
  const [topK, setTopK] = useState(5);
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [activeCitation, setActiveCitation] = useState<any>(null);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);

  React.useEffect(() => {
    documentsApi.list().then(setDocuments).catch(console.error);
  }, []);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isSearching) return;

    setIsSearching(true);
    setHasSearched(true);
    try {
      const res = await searchApi.search(query, topK);
      setResults(res.results);
    } catch (err) {
      console.error('Search failure:', err);
    } finally {
      setIsSearching(false);
    }
  };

  // Highlight matching terms in snippet
  const highlightMatches = (text: string, terms: string[]) => {
    if (!terms || terms.length === 0) return text;
    const regex = new RegExp(`(${terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'gi');
    const parts = text.split(regex);
    return parts.map((part, i) =>
      terms.some((term) => term.toLowerCase() === part.toLowerCase()) ? (
        <mark key={i} className="bg-amber-300/40 dark:bg-amber-400/30 text-slate-900 dark:text-white px-0.5 rounded">
          {part}
        </mark>
      ) : (
        part
      )
    );
  };

  return (
    <div className="p-6 sm:p-8 space-y-8 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
          Enterprise Hybrid Search
        </h1>
        <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
          Perform pure semantic (FAISS) + keyword (BM25) search with Reciprocal Rank Fusion across all documents without LLM generation.
        </p>
      </div>

      {/* Search Bar */}
      <form onSubmit={handleSearch} className="space-y-3">
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="w-5 h-5 text-slate-400 absolute left-4 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search across all technical PDFs, code, or manuals..."
              className="w-full pl-12 pr-4 py-3 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-brand-500 shadow-sm"
            />
          </div>
          <button
            type="submit"
            disabled={isSearching || !query.trim()}
            className="px-6 py-3 rounded-2xl bg-brand-600 hover:bg-brand-500 text-white font-semibold text-sm transition-all shadow-md shadow-brand-500/25 flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {isSearching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            Search
          </button>
        </div>

        <div className="flex items-center justify-between text-xs text-slate-500 px-2">
          <div className="flex items-center gap-2">
            <span>Result Limit:</span>
            <select
              value={topK}
              onChange={(e) => setTopK(parseInt(e.target.value, 10))}
              className="bg-slate-100 dark:bg-slate-800 border-none rounded px-2 py-1 text-xs text-slate-700 dark:text-slate-300"
            >
              <option value={3}>Top 3</option>
              <option value={5}>Top 5</option>
              <option value={10}>Top 10</option>
            </select>
          </div>
          <span>Reciprocal Rank Fusion (k=60) + Neural Cross-Encoder Rerank</span>
        </div>
      </form>

      {/* Results Stream */}
      <div className="space-y-4">
        {results.map((item, idx) => (
          <div
            key={`${item.chunk_id}-${idx}`}
            className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm space-y-3 hover:border-brand-500/50 transition-colors"
          >
            {/* Result Header */}
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <FileText className="w-4 h-4 text-brand-500" />
                <span className="font-semibold text-sm text-slate-900 dark:text-slate-100">
                  {item.source}
                </span>
                <span className="px-2 py-0.5 rounded-full bg-brand-500/10 text-brand-600 dark:text-brand-400 text-[10px] font-bold">
                  {item.page ? `Page ${item.page}` : 'Excerpt'}
                </span>
              </div>

              <div className="flex items-center space-x-2 text-[11px] text-slate-400 font-mono">
                <span>RRF: {item.rrf_score.toFixed(4)}</span>
                {item.rerank_score !== null && (
                  <span className="text-purple-500 font-semibold">
                    Score: {item.rerank_score.toFixed(2)}
                  </span>
                )}
              </div>
            </div>

            {/* Passage Text */}
            <p className="text-xs leading-relaxed text-slate-700 dark:text-slate-300 whitespace-pre-wrap font-sans">
              {highlightMatches(item.text, item.highlights)}
            </p>

            {/* Actions */}
            <div className="pt-2 flex items-center justify-between border-t border-slate-100 dark:border-slate-800/60 text-xs">
              <div className="flex items-center gap-1 text-[11px] text-slate-400">
                <span className="font-semibold text-slate-500">Matching tokens:</span>{' '}
                {item.highlights.join(', ') || 'semantic match'}
              </div>

              <button
                onClick={() =>
                  setActiveCitation({
                    id: idx + 1,
                    source: item.source,
                    chunk_id: item.chunk_id,
                    page: item.page,
                    text: item.text,
                  })
                }
                className="inline-flex items-center gap-1 font-semibold text-brand-600 dark:text-brand-400 hover:underline"
              >
                Inspect Page <BookOpen className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        ))}

        {hasSearched && results.length === 0 && !isSearching && (
          <div className="py-16 text-center text-slate-400 text-xs space-y-2">
            <Search className="w-8 h-8 mx-auto text-slate-300 dark:text-slate-700" />
            <p className="font-semibold text-slate-600 dark:text-slate-400">
              No matching passages found
            </p>
            <p className="text-[11px]">
              Try adjusting query keywords or verify documents have been indexed.
            </p>
          </div>
        )}
      </div>

      {/* Drawer */}
      <SourceDrawer
        citation={activeCitation}
        onClose={() => setActiveCitation(null)}
        documents={documents}
      />
    </div>
  );
};
