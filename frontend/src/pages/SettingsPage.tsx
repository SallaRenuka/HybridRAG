import React from 'react';
import { User, Moon, Sun, Shield, Cpu, HardDrive, LogOut } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';

export const SettingsPage: React.FC = () => {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="p-6 sm:p-8 space-y-8 max-w-4xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
          Settings & Preferences
        </h1>
        <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
          Manage your account profile, workspace parameters, and interface themes.
        </p>
      </div>

      <div className="space-y-6">
        {/* Profile Card */}
        <div className="p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm space-y-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-brand-500/10 text-brand-600 dark:text-brand-400 flex items-center justify-center font-bold">
              <User className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
                Account Information
              </h3>
              <p className="text-xs text-slate-400">Authenticated workspace tenant</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs pt-2">
            <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200/60 dark:border-slate-800/60">
              <span className="text-slate-400 block mb-1">Email Address</span>
              <span className="font-semibold text-slate-900 dark:text-white">{user?.email || 'N/A'}</span>
            </div>
            <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200/60 dark:border-slate-800/60">
              <span className="text-slate-400 block mb-1">Workspace ID</span>
              <span className="font-semibold text-slate-900 dark:text-white">Tenant #{user?.id || 1}</span>
            </div>
          </div>
        </div>

        {/* Theme Preferences */}
        <div className="p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex items-center justify-between">
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-white flex items-center gap-2">
              {theme === 'dark' ? <Moon className="w-4 h-4 text-brand-400" /> : <Sun className="w-4 h-4 text-amber-500" />}
              Interface Appearance
            </h3>
            <p className="text-xs text-slate-400">
              Currently using {theme === 'dark' ? 'Dark' : 'Light'} mode.
            </p>
          </div>

          <button
            onClick={toggleTheme}
            className="px-4 py-2 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-semibold text-slate-800 dark:text-slate-200 transition-colors shadow-xs"
          >
            Switch to {theme === 'dark' ? 'Light' : 'Dark'} Mode
          </button>
        </div>

        {/* Pipeline Specs Summary */}
        <div className="p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm space-y-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400 flex items-center justify-center font-bold">
              <Cpu className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
                RAG Pipeline Configuration
              </h3>
              <p className="text-xs text-slate-400">Active models and ranking parameters</p>
            </div>
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-2 border-b border-slate-100 dark:border-slate-800/60">
              <span className="text-slate-400">Embedding Model:</span>
              <span className="font-mono text-slate-700 dark:text-slate-300">sentence-transformers/all-MiniLM-L6-v2</span>
            </div>
            <div className="flex justify-between py-2 border-b border-slate-100 dark:border-slate-800/60">
              <span className="text-slate-400">Reranker Model:</span>
              <span className="font-mono text-slate-700 dark:text-slate-300">cross-encoder/ms-marco-MiniLM-L-6-v2</span>
            </div>
            <div className="flex justify-between py-2 border-b border-slate-100 dark:border-slate-800/60">
              <span className="text-slate-400">Hybrid Fusion Algorithm:</span>
              <span className="font-mono text-slate-700 dark:text-slate-300">Reciprocal Rank Fusion (k=60)</span>
            </div>
            <div className="flex justify-between py-2">
              <span className="text-slate-400">Token Chunk Limit:</span>
              <span className="font-mono text-slate-700 dark:text-slate-300">&le; 256 tokens</span>
            </div>
          </div>
        </div>

        {/* Logout Action */}
        <div className="pt-2">
          <button
            onClick={logout}
            className="w-full sm:w-auto px-5 py-2.5 rounded-xl border border-red-200 dark:border-red-900/40 hover:bg-red-50 dark:hover:bg-red-950/30 text-xs font-semibold text-red-600 dark:text-red-400 flex items-center justify-center gap-2 transition-colors"
          >
            <LogOut className="w-4 h-4" /> Sign Out of Workspace
          </button>
        </div>
      </div>
    </div>
  );
};
