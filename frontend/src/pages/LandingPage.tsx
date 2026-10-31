import React from 'react';
import {
  Layers,
  Search,
  ShieldCheck,
  Zap,
  ArrowRight,
  Database,
  FileCheck2,
  Cpu,
  Lock,
  GitBranch,
  Mic,
  BarChart3,
  Sparkles,
  CheckCircle2,
  ChevronRight,
  Workflow,
  Table,
} from 'lucide-react';
import { Navbar } from '../components/layout/Navbar';
import { Hero3DCanvas } from '../components/3d/Hero3DCanvas';

interface LandingPageProps {
  onNavigateAuth: (mode: 'login' | 'register') => void;
  onNavigateApp: () => void;
  isAuthenticated: boolean;
}

export const LandingPage: React.FC<LandingPageProps> = ({
  onNavigateAuth,
  onNavigateApp,
  isAuthenticated,
}) => {
  const scrollToFeatures = () => {
    document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-cyan-500/30 selection:text-cyan-200">
      <Navbar
        onNavigateAuth={onNavigateAuth}
        onNavigateApp={onNavigateApp}
        isAuthenticated={isAuthenticated}
      />

      <main className="flex-1">
        {/* 3D Cinematic Hero Section */}
        <section className="relative pt-12 pb-20 overflow-hidden">
          {/* Futuristic Ambient Lighting & Grid */}
          <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e293b15_1px,transparent_1px),linear-gradient(to_bottom,#1e293b15_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)] pointer-events-none" />
          <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[900px] h-[450px] bg-cyan-500/10 blur-[140px] rounded-full pointer-events-none -z-10" />
          <div className="absolute top-1/3 left-1/3 w-[600px] h-[300px] bg-violet-500/10 blur-[130px] rounded-full pointer-events-none -z-10" />

          <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 text-center space-y-6">
            {/* Top Pill */}
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-semibold bg-slate-900/90 text-cyan-400 border border-cyan-500/30 shadow-lg shadow-cyan-500/10 backdrop-blur-md">
              <span className="flex h-2 w-2 rounded-full bg-cyan-400 animate-pulse" />
              Hybrid Dense + Sparse Document Intelligence Platform
            </div>

            {/* Main Headline */}
            <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight text-white leading-[1.12]">
              Your Documents.{' '}
              <span className="bg-gradient-to-r from-cyan-400 via-blue-500 to-violet-500 bg-clip-text text-transparent">
                One Intelligent Workspace.
              </span>
            </h1>

            {/* Subtitle */}
            <p className="max-w-3xl mx-auto text-base sm:text-lg text-slate-400 leading-relaxed font-normal">
              Transform documents into knowledge with intelligent AI-powered search, analysis,
              and conversations. Built on exact record-level retrieval, hybrid neural reranking,
              and speech-driven interaction.
            </p>

            {/* CTA Buttons */}
            <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3.5">
              {isAuthenticated ? (
                <button
                  onClick={onNavigateApp}
                  className="w-full sm:w-auto px-8 py-3.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-semibold text-sm shadow-xl shadow-cyan-500/25 flex items-center justify-center gap-2 transition-all hover:scale-105"
                >
                  Enter Workspace <ArrowRight className="w-4 h-4" />
                </button>
              ) : (
                <>
                  <button
                    onClick={() => onNavigateAuth('register')}
                    className="w-full sm:w-auto px-8 py-3.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-semibold text-sm shadow-xl shadow-cyan-500/25 flex items-center justify-center gap-2 transition-all hover:scale-105"
                  >
                    Get Started <ArrowRight className="w-4 h-4" />
                  </button>
                  <button
                    onClick={scrollToFeatures}
                    className="w-full sm:w-auto px-8 py-3.5 rounded-xl border border-slate-800 bg-slate-900/60 hover:bg-slate-800 text-slate-200 font-medium text-sm transition-all hover:border-slate-700 backdrop-blur-md"
                  >
                    Explore Features
                  </button>
                </>
              )}
            </div>

            {/* Interactive 3D Canvas Showcase */}
            <div className="pt-6">
              <Hero3DCanvas />
            </div>

            {/* Metric Strip */}
            <div className="pt-8 grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl mx-auto border-t border-slate-800/80">
              <div className="p-4 rounded-xl glass-panel">
                <div className="text-2xl sm:text-3xl font-extrabold text-cyan-400">100%</div>
                <div className="text-xs text-slate-400 mt-0.5">Source Grounded</div>
              </div>
              <div className="p-4 rounded-xl glass-panel">
                <div className="text-2xl sm:text-3xl font-extrabold text-blue-400">Exact ID</div>
                <div className="text-xs text-slate-400 mt-0.5">Deterministic Lookup</div>
              </div>
              <div className="p-4 rounded-xl glass-panel">
                <div className="text-2xl sm:text-3xl font-extrabold text-violet-400">RRF + Neural</div>
                <div className="text-xs text-slate-400 mt-0.5">Two-Stage Ranking</div>
              </div>
              <div className="p-4 rounded-xl glass-panel">
                <div className="text-2xl sm:text-3xl font-extrabold text-emerald-400">Voice AI</div>
                <div className="text-xs text-slate-400 mt-0.5">Speech Interaction</div>
              </div>
            </div>
          </div>
        </section>

        {/* Product Preview Section */}
        <section className="py-16 bg-slate-900/50 border-y border-slate-800/60">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
            <div className="text-center space-y-2">
              <h2 className="text-xs uppercase tracking-wider text-cyan-400 font-semibold">
                Interactive Workspace Preview
              </h2>
              <p className="text-2xl sm:text-3xl font-bold text-white">
                Engineered for verifiable enterprise answers
              </p>
            </div>

            {/* Mocked Live Window */}
            <div className="rounded-2xl border border-slate-800 bg-slate-950/90 shadow-2xl overflow-hidden glass-panel">
              {/* Window Header */}
              <div className="px-4 py-3 bg-slate-900/80 border-b border-slate-800/80 flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <div className="w-3 h-3 rounded-full bg-rose-500/80" />
                  <div className="w-3 h-3 rounded-full bg-amber-500/80" />
                  <div className="w-3 h-3 rounded-full bg-emerald-500/80" />
                  <span className="text-xs text-slate-400 font-mono ml-2">hybridrag.workspace/chat</span>
                </div>
                <div className="flex items-center gap-2 text-xs text-cyan-400 font-medium">
                  <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
                  Deterministic Structured Layer Active
                </div>
              </div>

              {/* Chat View Simulator */}
              <div className="p-6 space-y-6">
                {/* User Message */}
                <div className="flex items-start justify-end gap-3">
                  <div className="p-3.5 rounded-2xl bg-cyan-600/20 text-cyan-100 border border-cyan-500/30 text-sm max-w-lg">
                    Show me the history and complete profile of EMP002.
                  </div>
                  <div className="w-8 h-8 rounded-lg bg-cyan-500/20 text-cyan-300 flex items-center justify-center font-bold text-xs">
                    U
                  </div>
                </div>

                {/* Assistant Message with Table */}
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-cyan-500 to-blue-600 text-white flex items-center justify-center">
                    <Sparkles className="w-4 h-4" />
                  </div>
                  <div className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800 text-sm max-w-3xl space-y-3">
                    <div className="font-semibold text-slate-100 flex items-center gap-2">
                      <span>Employee Profile: EMP002 – Harsh Verma</span>
                      <span className="text-[10px] bg-cyan-500/20 text-cyan-300 px-2 py-0.5 rounded-full border border-cyan-500/30">
                        [1] Page 1
                      </span>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs border-collapse">
                        <thead>
                          <tr className="border-b border-slate-800 text-slate-400 font-mono">
                            <th className="py-2 px-3">Field</th>
                            <th className="py-2 px-3">Details</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/60 text-slate-300">
                          <tr><td className="py-1.5 px-3 font-medium text-slate-400">Employee ID</td><td className="py-1.5 px-3 font-semibold text-cyan-300">EMP002</td></tr>
                          <tr><td className="py-1.5 px-3 font-medium text-slate-400">Name</td><td className="py-1.5 px-3">Harsh Verma</td></tr>
                          <tr><td className="py-1.5 px-3 font-medium text-slate-400">Department</td><td className="py-1.5 px-3">Cybersecurity</td></tr>
                          <tr><td className="py-1.5 px-3 font-medium text-slate-400">Experience</td><td className="py-1.5 px-3">15 years</td></tr>
                          <tr><td className="py-1.5 px-3 font-medium text-slate-400">Projects Completed</td><td className="py-1.5 px-3">37</td></tr>
                          <tr><td className="py-1.5 px-3 font-medium text-slate-400">Salary</td><td className="py-1.5 px-3 text-emerald-400">₹3,927,316</td></tr>
                        </tbody>
                      </table>
                    </div>

                    <div className="text-[11px] text-slate-400 italic pt-1">
                      Verified against Employee_Database_100_Employees.pdf, Page 1.
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Feature Showcase Section */}
        <section id="features" className="py-24">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 space-y-12">
            <div className="text-center space-y-3">
              <h2 className="text-xs uppercase tracking-wider text-cyan-400 font-semibold">
                Enterprise Capabilities
              </h2>
              <p className="text-3xl sm:text-4xl font-extrabold text-white">
                Everything required for intelligent document automation
              </p>
              <p className="text-slate-400 max-w-2xl mx-auto text-sm sm:text-base">
                Combines classical retrieval strength with modern generative AI and strict structured data determinism.
              </p>
            </div>

            {/* 6 Feature Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {/* Feature 1 */}
              <div className="p-6 rounded-2xl glass-panel glass-card-hover border border-slate-800 space-y-3">
                <div className="w-11 h-11 rounded-xl bg-cyan-500/10 text-cyan-400 flex items-center justify-center border border-cyan-500/20">
                  <Search className="w-5 h-5" />
                </div>
                <h3 className="text-lg font-bold text-white">Intelligent Document Search</h3>
                <p className="text-sm text-slate-400 leading-relaxed">
                  Dual-retriever architecture coupling FAISS dense vector embeddings with BM25Okapi sparse lexical scoring via Reciprocal Rank Fusion.
                </p>
              </div>

              {/* Feature 2 */}
              <div className="p-6 rounded-2xl glass-panel glass-card-hover border border-slate-800 space-y-3">
                <div className="w-11 h-11 rounded-xl bg-blue-500/10 text-blue-400 flex items-center justify-center border border-blue-500/20">
                  <Sparkles className="w-5 h-5" />
                </div>
                <h3 className="text-lg font-bold text-white">AI-Powered Document Q&A</h3>
                <p className="text-sm text-slate-400 leading-relaxed">
                  Ask natural language questions regardless of phrasing. Query understanding maps intent to profiles, comparisons, rankings, or explanations.
                </p>
              </div>

              {/* Feature 3 */}
              <div className="p-6 rounded-2xl glass-panel glass-card-hover border border-slate-800 space-y-3">
                <div className="w-11 h-11 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center border border-emerald-500/20">
                  <ShieldCheck className="w-5 h-5" />
                </div>
                <h3 className="text-lg font-bold text-white">Source-Based Answers</h3>
                <p className="text-sm text-slate-400 leading-relaxed">
                  Every fact is supported by citations linked directly to verified PDF pages. Unverified claims and hallucinations are rejected.
                </p>
              </div>

              {/* Feature 4 */}
              <div className="p-6 rounded-2xl glass-panel glass-card-hover border border-slate-800 space-y-3">
                <div className="w-11 h-11 rounded-xl bg-violet-500/10 text-violet-400 flex items-center justify-center border border-violet-500/20">
                  <Table className="w-5 h-5" />
                </div>
                <h3 className="text-lg font-bold text-white">Structured Data Analysis</h3>
                <p className="text-sm text-slate-400 leading-relaxed">
                  Deep PDF tabular extraction preserves columns and rows. Exact ID lookup guarantees that employee fields never mix across records.
                </p>
              </div>

              {/* Feature 5 */}
              <div className="p-6 rounded-2xl glass-panel glass-card-hover border border-slate-800 space-y-3">
                <div className="w-11 h-11 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center border border-indigo-500/20">
                  <Workflow className="w-5 h-5" />
                </div>
                <h3 className="text-lg font-bold text-white">Multi-Document Intelligence</h3>
                <p className="text-sm text-slate-400 leading-relaxed">
                  Query across all documents in your isolated workspace. Cross-document synthesis detects conflicting records and discloses them transparently.
                </p>
              </div>

              {/* Feature 6 */}
              <div className="p-6 rounded-2xl glass-panel glass-card-hover border border-slate-800 space-y-3">
                <div className="w-11 h-11 rounded-xl bg-rose-500/10 text-rose-400 flex items-center justify-center border border-rose-500/20">
                  <Mic className="w-5 h-5" />
                </div>
                <h3 className="text-lg font-bold text-white">Voice Interaction</h3>
                <p className="text-sm text-slate-400 leading-relaxed">
                  Speak questions naturally with built-in speech recognition, live audio waveform visualizers, and seamless text transcription.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* How It Works Section */}
        <section className="py-20 bg-slate-900/40 border-t border-slate-800/60">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 space-y-12">
            <div className="text-center space-y-3">
              <h2 className="text-xs uppercase tracking-wider text-cyan-400 font-semibold">
                Architecture & Workflow
              </h2>
              <p className="text-3xl font-bold text-white">How HybridRAG Works</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <div className="p-6 rounded-2xl bg-slate-950/80 border border-slate-800 relative space-y-3">
                <div className="text-4xl font-extrabold text-cyan-500/30">01</div>
                <h4 className="text-lg font-bold text-white">Deep Ingestion & Structuring</h4>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Extracts text, headings, and tabular rows from uploaded PDFs and CSVs. Stores isolated record entities for deterministic lookups.
                </p>
              </div>

              <div className="p-6 rounded-2xl bg-slate-950/80 border border-slate-800 relative space-y-3">
                <div className="text-4xl font-extrabold text-blue-500/30">02</div>
                <h4 className="text-lg font-bold text-white">Hybrid Neural Retrieval</h4>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Executes dense vector cosine similarity and BM25 term frequency concurrently. RRF and CrossEncoder rerankers select authoritative context.
                </p>
              </div>

              <div className="p-6 rounded-2xl bg-slate-950/80 border border-slate-800 relative space-y-3">
                <div className="text-4xl font-extrabold text-violet-500/30">03</div>
                <h4 className="text-lg font-bold text-white">Dynamic Formatted Synthesis</h4>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Automatically chooses the optimal representation: two-column profile tables, side-by-side comparisons, sorted rankings, or concise summaries.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Benefits Section */}
        <section className="py-20">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="p-8 sm:p-12 rounded-3xl bg-gradient-to-r from-cyan-950/60 via-slate-900 to-violet-950/60 border border-cyan-500/30 shadow-2xl flex flex-col md:flex-row items-center justify-between gap-8">
              <div className="space-y-3 max-w-xl">
                <h3 className="text-2xl sm:text-3xl font-extrabold text-white">
                  Ready to experience intelligent document retrieval?
                </h3>
                <p className="text-sm text-slate-300">
                  Join enterprise researchers, compliance officers, and engineers who trust HybridRAG for verifiable document intelligence.
                </p>
              </div>
              <div>
                <button
                  onClick={() => (isAuthenticated ? onNavigateApp() : onNavigateAuth('register'))}
                  className="px-8 py-4 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-bold text-sm shadow-xl shadow-cyan-500/25 transition-all hover:scale-105 flex items-center gap-2"
                >
                  {isAuthenticated ? 'Open Dashboard' : 'Create Free Account'} <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 bg-slate-950 py-10 text-xs text-slate-500">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-lg bg-cyan-500/20 text-cyan-400 flex items-center justify-center font-bold text-xs border border-cyan-500/40">
              H
            </div>
            <span className="font-semibold text-slate-300">HybridRAG</span>
            <span>— Enterprise Document Intelligence</span>
          </div>

          <div className="flex items-center gap-6">
            <span>FastAPI + PyTorch</span>
            <span>FAISS + BM25</span>
            <span className="flex items-center gap-1.5 text-emerald-400">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /> All Systems Operational
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
};
