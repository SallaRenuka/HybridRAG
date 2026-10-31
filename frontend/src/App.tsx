import React, { useState } from 'react';
import { useAuth } from './context/AuthContext';
import { LandingPage } from './pages/LandingPage';
import { LoginPage } from './pages/LoginPage';
import { Sidebar, NavTab } from './components/layout/Sidebar';
import { DashboardPage } from './pages/DashboardPage';
import { ChatPage } from './pages/ChatPage';
import { DocumentsPage } from './pages/DocumentsPage';
import { SearchPage } from './pages/SearchPage';
import { SettingsPage } from './pages/SettingsPage';
import { Loader2 } from 'lucide-react';

export const App: React.FC = () => {
  const { user, isLoading } = useAuth();
  const [view, setView] = useState<'landing' | 'auth' | 'app'>('landing');
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [activeTab, setActiveTab] = useState<NavTab>('dashboard');

  if (isLoading) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-white dark:bg-slate-950 text-slate-500">
        <Loader2 className="w-6 h-6 animate-spin text-brand-600" />
      </div>
    );
  }

  // If user is authenticated and clicks to enter workspace, switch to app view
  const handleOpenApp = () => {
    setView('app');
  };

  const handleOpenAuth = (mode: 'login' | 'register') => {
    setAuthMode(mode);
    setView('auth');
  };

  // 1. Landing View
  if (view === 'landing' || (!user && view === 'app')) {
    return (
      <LandingPage
        onNavigateAuth={handleOpenAuth}
        onNavigateApp={handleOpenApp}
        isAuthenticated={!!user}
      />
    );
  }

  // 2. Auth View
  if (view === 'auth') {
    return (
      <LoginPage
        initialMode={authMode}
        onReturnHome={() => setView('landing')}
        onSuccess={() => setView('app')}
      />
    );
  }

  // 3. Authenticated App View
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-white dark:bg-slate-950 font-sans">
      <Sidebar
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        onReturnLanding={() => setView('landing')}
      />

      <main className="flex-1 overflow-y-auto bg-slate-50/50 dark:bg-slate-950 transition-colors">
        {activeTab === 'dashboard' && <DashboardPage onNavigateTab={setActiveTab} />}
        {activeTab === 'chat' && <ChatPage />}
        {activeTab === 'documents' && <DocumentsPage />}
        {activeTab === 'search' && <SearchPage />}
        {activeTab === 'settings' && <SettingsPage />}
      </main>
    </div>
  );
};

export default App;
