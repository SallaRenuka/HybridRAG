import React, { useEffect, useState } from 'react';
import {
  Files,
  Layers,
  MessageSquare,
  HardDrive,
  ArrowRight,
  Upload,
  Search,
  Clock,
  CheckCircle2,
  AlertCircle,
  FileText,
  BarChart2,
  PieChart,
  Sparkles,
  Database,
  BookOpen,
} from 'lucide-react';
import { DashboardStats } from '../types';
import { searchApi } from '../api/client';
import { Tilt3DCard } from '../components/3d/Tilt3DCard';
import { AnimatedCounter } from '../components/common/AnimatedCounter';

interface DashboardPageProps {
  onNavigateTab: (tab: 'chat' | 'documents' | 'search') => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ onNavigateTab }) => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchStats = async () => {
    try {
      const data = await searchApi.getStats();
      setStats(data);
    } catch (err) {
      console.error('Failed to load stats:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const totalPages = stats?.total_pages_processed ?? 0;
  const totalQuestions = stats?.total_questions_asked ?? stats?.total_messages ?? 0;

  return (
    <div className="p-6 sm:p-8 space-y-8 max-w-7xl mx-auto">
      {/* Welcome Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border border-cyan-500/20 mb-2">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse" />
            3D Enterprise Intelligence Dashboard
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white">
            Workspace Intelligence
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
            Real-time document index, verified tenant metrics, and neural analytics.
          </p>
        </div>

        <div className="flex items-center space-x-2.5">
          <button
            onClick={() => onNavigateTab('search')}
            className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800 text-xs font-semibold text-slate-700 dark:text-slate-200 transition-colors shadow-sm"
          >
            <Search className="w-3.5 h-3.5 text-cyan-500" /> Enterprise Search
          </button>
          <button
            onClick={() => onNavigateTab('chat')}
            className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white text-xs font-semibold shadow-md shadow-cyan-500/25 transition-all hover:scale-105"
          >
            <MessageSquare className="w-3.5 h-3.5" /> Open AI Chat
          </button>
        </div>
      </div>

      {/* Floating 3D Statistic Cards with Animated Counters */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* Metric 1: Total Documents */}
        <Tilt3DCard glowColor="rgba(6, 182, 212, 0.2)">
          <div className="p-5 flex items-center justify-between">
            <div className="space-y-1">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Total Documents
              </span>
              <div className="text-3xl font-extrabold text-slate-900 dark:text-white">
                <AnimatedCounter value={stats?.total_documents ?? 0} />
              </div>
              <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-medium flex items-center gap-1 pt-0.5">
                <CheckCircle2 className="w-3 h-3" /> Isolated tenant store
              </span>
            </div>
            <div className="w-12 h-12 rounded-2xl bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 flex items-center justify-center border border-cyan-500/20 shadow-sm">
              <Files className="w-6 h-6" />
            </div>
          </div>
        </Tilt3DCard>

        {/* Metric 2: Total Pages Processed */}
        <Tilt3DCard glowColor="rgba(59, 130, 246, 0.2)">
          <div className="p-5 flex items-center justify-between">
            <div className="space-y-1">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Pages Processed
              </span>
              <div className="text-3xl font-extrabold text-slate-900 dark:text-white">
                <AnimatedCounter value={totalPages} />
              </div>
              <span className="text-[11px] text-blue-600 dark:text-blue-400 font-medium flex items-center gap-1 pt-0.5">
                <BookOpen className="w-3 h-3" /> Page-level citations
              </span>
            </div>
            <div className="w-12 h-12 rounded-2xl bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center justify-center border border-blue-500/20 shadow-sm">
              <BookOpen className="w-6 h-6" />
            </div>
          </div>
        </Tilt3DCard>

        {/* Metric 3: Total Questions Asked */}
        <Tilt3DCard glowColor="rgba(139, 92, 246, 0.2)">
          <div className="p-5 flex items-center justify-between">
            <div className="space-y-1">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Questions Asked
              </span>
              <div className="text-3xl font-extrabold text-slate-900 dark:text-white">
                <AnimatedCounter value={totalQuestions} />
              </div>
              <span className="text-[11px] text-violet-600 dark:text-violet-400 font-medium flex items-center gap-1 pt-0.5">
                <Sparkles className="w-3 h-3" /> 100% grounded Q&A
              </span>
            </div>
            <div className="w-12 h-12 rounded-2xl bg-violet-500/10 text-violet-600 dark:text-violet-400 flex items-center justify-center border border-violet-500/20 shadow-sm">
              <MessageSquare className="w-6 h-6" />
            </div>
          </div>
        </Tilt3DCard>

        {/* Metric 4: Total Indexed Chunks */}
        <Tilt3DCard glowColor="rgba(16, 185, 129, 0.2)">
          <div className="p-5 flex items-center justify-between">
            <div className="space-y-1">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Indexed Chunks
              </span>
              <div className="text-3xl font-extrabold text-slate-900 dark:text-white">
                <AnimatedCounter value={stats?.total_chunks ?? 0} />
              </div>
              <span className="text-[11px] text-slate-500 dark:text-slate-400 font-medium flex items-center gap-1 pt-0.5">
                <HardDrive className="w-3 h-3" /> {formatBytes(stats?.total_size_bytes ?? 0)} stored
              </span>
            </div>
            <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center border border-emerald-500/20 shadow-sm">
              <Layers className="w-6 h-6" />
            </div>
          </div>
        </Tilt3DCard>
      </div>

      {/* Advanced Data Analytics Visualization */}
      {stats?.structured_records_count ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Department Breakdown Card */}
          <div className="lg:col-span-2 p-6 rounded-2xl glass-panel border border-slate-200 dark:border-slate-800 space-y-5">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                  <Database className="w-4 h-4 text-cyan-500" />
                  Structured Dataset Analytics ({stats.structured_records_count} Records)
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  Extracted and verified from uploaded tabular databases.
                </p>
              </div>
              <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-cyan-500/10 text-cyan-500 border border-cyan-500/20">
                Deterministic Engine
              </span>
            </div>

            {/* Department Horizontal Bars */}
            <div className="space-y-3 pt-2">
              {stats.department_distribution &&
                Object.entries(stats.department_distribution)
                  .sort((a, b) => b[1] - a[1])
                  .slice(0, 5)
                  .map(([dept, count]) => {
                    const pct = Math.round((count / (stats.structured_records_count || 100)) * 100);
                    return (
                      <div key={dept} className="space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-medium text-slate-700 dark:text-slate-300">{dept}</span>
                          <span className="text-slate-500 dark:text-slate-400 font-mono">
                            {count} employees ({pct}%)
                          </span>
                        </div>
                        <div className="w-full h-2 rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden">
                          <div
                            style={{ width: `${pct}%` }}
                            className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-blue-500"
                          />
                        </div>
                      </div>
                    );
                  })}
            </div>
          </div>

          {/* Experience Distribution KPI Card */}
          <div className="p-6 rounded-2xl glass-panel border border-slate-200 dark:border-slate-800 space-y-4">
            <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <BarChart2 className="w-4 h-4 text-violet-500" />
              Experience Cohorts
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Distribution across tenure brackets in the active database.
            </p>

            <div className="space-y-3 pt-2">
              {stats.experience_distribution &&
                Object.entries(stats.experience_distribution).map(([range, count]) => (
                  <div
                    key={range}
                    className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200/60 dark:border-slate-800/60"
                  >
                    <span className="text-xs font-semibold text-slate-700 dark:text-slate-200">
                      {range}
                    </span>
                    <span className="text-xs font-bold text-violet-500 font-mono">
                      {count} records
                    </span>
                  </div>
                ))}
            </div>
          </div>
        </div>
      ) : null}

      {/* Quick Actions & Recent Activity Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Documents */}
        <div className="p-6 rounded-2xl glass-panel border border-slate-200 dark:border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <Files className="w-4 h-4 text-cyan-500" /> Recent Documents
            </h3>
            <button
              onClick={() => onNavigateTab('documents')}
              className="text-xs text-cyan-600 dark:text-cyan-400 hover:underline flex items-center gap-1 font-medium"
            >
              Manage all <ArrowRight className="w-3 h-3" />
            </button>
          </div>

          <div className="divide-y divide-slate-100 dark:divide-slate-800/60">
            {stats?.recent_documents && stats.recent_documents.length > 0 ? (
              stats.recent_documents.map((doc) => (
                <div key={doc.id} className="py-3 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-cyan-500/10 text-cyan-500 flex items-center justify-center">
                      <FileText className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-slate-800 dark:text-slate-200 truncate max-w-[200px] sm:max-w-xs">
                        {doc.filename}
                      </div>
                      <div className="text-[11px] text-slate-500 dark:text-slate-400">
                        {formatBytes(doc.file_size_bytes)} · {doc.chunk_count} chunks indexed
                      </div>
                    </div>
                  </div>
                  <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-medium">
                    Indexed
                  </span>
                </div>
              ))
            ) : (
              <div className="py-6 text-center text-xs text-slate-500">
                No documents uploaded yet. Upload a document to start indexing.
              </div>
            )}
          </div>
        </div>

        {/* Recent Conversations */}
        <div className="p-6 rounded-2xl glass-panel border border-slate-200 dark:border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <MessageSquare className="w-4 h-4 text-violet-500" /> Recent Conversations
            </h3>
            <button
              onClick={() => onNavigateTab('chat')}
              className="text-xs text-violet-600 dark:text-violet-400 hover:underline flex items-center gap-1 font-medium"
            >
              Open chat <ArrowRight className="w-3 h-3" />
            </button>
          </div>

          <div className="divide-y divide-slate-100 dark:divide-slate-800/60">
            {stats?.recent_conversations && stats.recent_conversations.length > 0 ? (
              stats.recent_conversations.map((conv) => (
                <div
                  key={conv.id}
                  onClick={() => onNavigateTab('chat')}
                  className="py-3 flex items-center justify-between cursor-pointer group hover:bg-slate-50 dark:hover:bg-slate-900/40 rounded-xl px-2 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-violet-500/10 text-violet-500 flex items-center justify-center">
                      <MessageSquare className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-slate-800 dark:text-slate-200 group-hover:text-violet-400 transition-colors">
                        {conv.title}
                      </div>
                      <div className="text-[11px] text-slate-500 dark:text-slate-400 flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {new Date(conv.updated_at).toLocaleDateString()}
                      </div>
                    </div>
                  </div>
                  <ArrowRight className="w-4 h-4 text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
              ))
            ) : (
              <div className="py-6 text-center text-xs text-slate-500">
                No conversations yet. Start a new chat to ask questions.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
