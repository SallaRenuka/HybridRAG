import React, { useState, useEffect, useRef } from 'react';
import {
  Send,
  Plus,
  Trash2,
  FileText,
  Sparkles,
  Bot,
  User,
  Loader2,
  AlertCircle,
  ExternalLink,
  Sliders,
  CheckCircle2,
  Quote,
  Copy,
  Check,
  RotateCw,
  ThumbsUp,
  ThumbsDown,
  Volume2,
} from 'lucide-react';
import { Conversation, ChatMessage, Citation, DocumentRecord } from '../types';
import { chatApi, documentsApi } from '../api/client';
import { SourceDrawer } from '../components/chat/SourceDrawer';
import { useSpeechRecognition } from '../hooks/useSpeechRecognition';
import { VoiceInputButton } from '../components/chat/VoiceInputButton';

export const ChatPage: React.FC = () => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [topK, setTopK] = useState(5);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [feedbackMap, setFeedbackMap] = useState<Record<number, 'up' | 'down'>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Hook for voice input: places recognized speech into chat input without automatically sending
  const handleVoiceResult = (finalText: string) => {
    setInputMessage((prev) => {
      const trimmed = prev.trim();
      return trimmed ? `${trimmed} ${finalText}` : finalText;
    });
  };

  const speech = useSpeechRecognition(handleVoiceResult);

  // Load conversations & user documents on mount
  useEffect(() => {
    loadConversations();
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      const docs = await documentsApi.list();
      setDocuments(docs);
    } catch (err) {
      console.error('Failed to load documents:', err);
    }
  };

  const loadConversations = async () => {
    try {
      const convs = await chatApi.listConversations();
      setConversations(convs);
      if (convs.length > 0 && !activeConvId) {
        selectConversation(convs[0].id);
      }
    } catch (err) {
      console.error('Failed to load conversations:', err);
    }
  };

  const selectConversation = async (convId: number) => {
    setActiveConvId(convId);
    setIsLoadingMessages(true);
    try {
      const detail = await chatApi.getConversationHistory(convId);
      setMessages(detail.messages);
    } catch (err) {
      console.error('Failed to load history:', err);
    } finally {
      setIsLoadingMessages(false);
    }
  };

  const createNewChat = async () => {
    try {
      const newConv = await chatApi.createConversation('New Conversation');
      setConversations((prev) => [newConv, ...prev]);
      setActiveConvId(newConv.id);
      setMessages([]);
    } catch (err) {
      console.error('Failed to create new conversation:', err);
    }
  };

  const deleteConversation = async (convId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await chatApi.deleteConversation(convId);
      const remaining = conversations.filter((c) => c.id !== convId);
      setConversations(remaining);
      if (activeConvId === convId) {
        if (remaining.length > 0) {
          selectConversation(remaining[0].id);
        } else {
          setActiveConvId(null);
          setMessages([]);
        }
      }
    } catch (err) {
      console.error('Failed to delete conversation:', err);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isSending]);

  const handleCopy = (msgId: number, content: string) => {
    navigator.clipboard.writeText(content);
    setCopiedId(msgId);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleFeedback = (msgId: number, type: 'up' | 'down') => {
    setFeedbackMap((prev) => ({
      ...prev,
      [msgId]: prev[msgId] === type ? undefined! : type,
    }));
  };

  const handleRegenerate = async (lastUserText?: string) => {
    if (!lastUserText && messages.length > 0) {
      const lastUser = [...messages].reverse().find((m) => m.role === 'user');
      if (lastUser) lastUserText = lastUser.content;
    }
    if (!lastUserText || !activeConvId || isSending) return;

    setIsSending(true);
    try {
      const res = await chatApi.sendMessage(activeConvId, lastUserText, topK);
      const assistantMsg: ChatMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: res.answer,
        citations: res.citations,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      console.error('Regeneration error:', err);
    } finally {
      setIsSending(false);
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputMessage.trim() || isSending) return;

    // If recording voice, stop before sending
    if (speech.isListening) {
      speech.stopListening();
    }

    let targetConvId = activeConvId;
    if (!targetConvId) {
      try {
        const newConv = await chatApi.createConversation(inputMessage.slice(0, 30));
        setConversations((prev) => [newConv, ...prev]);
        setActiveConvId(newConv.id);
        targetConvId = newConv.id;
      } catch (err) {
        console.error('Failed to initialize conversation:', err);
        return;
      }
    }

    const userText = inputMessage.trim();
    setInputMessage('');
    const tempUserMsg: ChatMessage = {
      id: Date.now(),
      role: 'user',
      content: userText,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);
    setIsSending(true);

    try {
      const res = await chatApi.sendMessage(targetConvId, userText, topK);
      const assistantMsg: ChatMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: res.answer,
        citations: res.citations,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content:
          'Error processing query: ' +
          (err.response?.data?.detail || 'Could not retrieve answers from the document store.'),
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsSending(false);
    }
  };

  const renderInlineWithCitations = (text: string, citationMap: Map<number, Citation>) => {
    const parts = text.split(/(\[\d+\]|\*\*[^*]+\*\*)/g);
    return parts.map((part, index) => {
      const match = part.match(/^\[(\d+)\]$/);
      if (match) {
        const citId = parseInt(match[1], 10);
        const cit = citationMap.get(citId);
        return (
          <button
            key={index}
            onClick={() => cit && setActiveCitation(cit)}
            className="inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded text-[11px] font-bold bg-cyan-500/15 text-cyan-600 dark:text-cyan-400 hover:bg-cyan-500 hover:text-white border border-cyan-500/30 transition-all cursor-pointer shadow-xs"
            title={cit ? `${cit.source} (Page ${cit.page || 1}) - Click to inspect` : `Citation [${citId}]`}
          >
            [{citId}]
          </button>
        );
      }
      if (part.startsWith('**') && part.endsWith('**') && part.length >= 4) {
        return (
          <strong key={index} className="font-semibold text-slate-900 dark:text-white">
            {part.slice(2, -2)}
          </strong>
        );
      }
      return <span key={index}>{part}</span>;
    });
  };

  // Render citation tag buttons inline inside assistant response and format tables nicely
  const renderMessageContent = (msg: ChatMessage) => {
    if (msg.role === 'user') {
      return <p className="whitespace-pre-wrap">{msg.content}</p>;
    }

    const citationMap = new Map((msg.citations || []).map((c) => [c.id, c]));

    // Parse blocks: detect markdown tables, headings, and paragraphs
    const blocks: Array<{ type: 'heading' | 'table' | 'text'; content: string | string[][] }> = [];
    const lines = msg.content.split('\n');
    let currentTable: string[][] = [];
    let currentParagraph: string[] = [];

    const flushParagraph = () => {
      if (currentParagraph.length > 0) {
        blocks.push({ type: 'text', content: currentParagraph.join('\n') });
        currentParagraph = [];
      }
    };

    const flushTable = () => {
      if (currentTable.length > 0) {
        blocks.push({ type: 'table', content: currentTable });
        currentTable = [];
      }
    };

    for (const rawLine of lines) {
      const line = rawLine.trim();
      if (line.startsWith('|') && line.endsWith('|')) {
        flushParagraph();
        if (/^\|[\s\-:|]+\|$/.test(line)) {
          continue;
        }
        const cells = line
          .slice(1, -1)
          .split('|')
          .map((c) => c.trim());
        currentTable.push(cells);
      } else if (line.startsWith('#')) {
        flushParagraph();
        flushTable();
        blocks.push({ type: 'heading', content: line });
      } else {
        flushTable();
        if (line) {
          currentParagraph.push(rawLine);
        } else {
          flushParagraph();
        }
      }
    }
    flushParagraph();
    flushTable();

    return (
      <div className="space-y-3">
        {blocks.map((block, bIdx) => {
          if (block.type === 'heading') {
            const hText = (block.content as string).replace(/^#{1,4}\s+/, '');
            return (
              <h3 key={bIdx} className="font-bold text-sm text-slate-900 dark:text-white mt-2 mb-1">
                {renderInlineWithCitations(hText, citationMap)}
              </h3>
            );
          }

          if (block.type === 'table') {
            const tableData = block.content as string[][];
            if (tableData.length === 0) return null;
            const headerRow = tableData[0];
            const dataRows = tableData.slice(1);

            return (
              <div
                key={bIdx}
                className="overflow-x-auto my-3 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs"
              >
                <table className="w-full text-xs text-left border-collapse">
                  <thead className="bg-slate-100 dark:bg-slate-800/80 text-slate-700 dark:text-slate-300 font-semibold border-b border-slate-200 dark:border-slate-800">
                    <tr>
                      {headerRow.map((cell, cIdx) => (
                        <th
                          key={cIdx}
                          className="px-3.5 py-2.5 font-semibold text-slate-900 dark:text-slate-100"
                        >
                          {renderInlineWithCitations(cell, citationMap)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-800 bg-white dark:bg-slate-900/60">
                    {dataRows.map((row, rIdx) => (
                      <tr
                        key={rIdx}
                        className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors"
                      >
                        {row.map((cell, cIdx) => (
                          <td key={cIdx} className="px-3.5 py-2 text-slate-700 dark:text-slate-300">
                            {renderInlineWithCitations(cell, citationMap)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          }

          return (
            <div key={bIdx} className="leading-relaxed whitespace-pre-wrap">
              {renderInlineWithCitations(block.content as string, citationMap)}
            </div>
          );
        })}

        {/* Citation Sources Footnote List */}
        {msg.citations && msg.citations.length > 0 && (
          <div className="mt-4 pt-3 border-t border-slate-200 dark:border-slate-800">
            <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
              Verified Citations ({msg.citations.length})
            </div>
            <div className="flex flex-wrap gap-2">
              {msg.citations.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setActiveCitation(c)}
                  className="text-left px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 hover:border-cyan-500 text-xs transition-colors group flex items-center gap-1.5"
                >
                  <span className="font-bold text-cyan-600 dark:text-cyan-400">[{c.id}]</span>
                  <span className="text-slate-700 dark:text-slate-300 font-medium truncate max-w-[180px]">
                    {c.source}
                  </span>
                  <span className="text-[10px] text-slate-400 bg-slate-200 dark:bg-slate-800 px-1 rounded">
                    p.{c.page || 1}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Message Actions Strip */}
        <div className="flex items-center justify-between pt-2 mt-2 border-t border-slate-200/50 dark:border-slate-800/50 text-slate-400">
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => handleCopy(msg.id, msg.content)}
              title="Copy answer"
              className="p-1 rounded-md hover:bg-slate-200 dark:hover:bg-slate-800 hover:text-slate-600 dark:hover:text-slate-200 transition-colors flex items-center gap-1 text-[11px]"
            >
              {copiedId === msg.id ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-500" />
                  <span className="text-emerald-500 font-medium">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" />
                  <span>Copy</span>
                </>
              )}
            </button>
            <button
              onClick={() => handleRegenerate()}
              title="Regenerate answer"
              className="p-1 rounded-md hover:bg-slate-200 dark:hover:bg-slate-800 hover:text-slate-600 dark:hover:text-slate-200 transition-colors flex items-center gap-1 text-[11px]"
            >
              <RotateCw className="w-3.5 h-3.5" />
              <span>Retry</span>
            </button>
          </div>

          <div className="flex items-center gap-1">
            <button
              onClick={() => handleFeedback(msg.id, 'up')}
              className={`p-1 rounded-md hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors ${
                feedbackMap[msg.id] === 'up' ? 'text-emerald-500 font-bold' : ''
              }`}
            >
              <ThumbsUp className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => handleFeedback(msg.id, 'down')}
              className={`p-1 rounded-md hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors ${
                feedbackMap[msg.id] === 'down' ? 'text-rose-500 font-bold' : ''
              }`}
            >
              <ThumbsDown className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="h-screen flex flex-col sm:flex-row overflow-hidden bg-white dark:bg-slate-950 font-sans">
      {/* Left Chat Thread Sidebar */}
      <aside className="w-full sm:w-64 border-r border-slate-200 dark:border-slate-800 flex flex-col bg-slate-50/50 dark:bg-slate-950">
        <div className="p-3 border-b border-slate-200 dark:border-slate-800">
          <button
            onClick={createNewChat}
            className="w-full py-2.5 px-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-cyan-500 text-xs font-semibold text-slate-800 dark:text-slate-200 flex items-center justify-center gap-2 shadow-sm transition-all"
          >
            <Plus className="w-4 h-4 text-cyan-500" /> New Chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          <div className="px-2 py-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
            Conversations
          </div>
          {conversations.map((conv) => (
            <div
              key={conv.id}
              onClick={() => selectConversation(conv.id)}
              className={`group flex items-center justify-between px-3 py-2.5 rounded-xl text-xs font-medium cursor-pointer transition-colors ${
                activeConvId === conv.id
                  ? 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 font-semibold'
                  : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-900'
              }`}
            >
              <span className="truncate flex-1">{conv.title}</span>
              <button
                onClick={(e) => deleteConversation(conv.id, e)}
                title="Delete thread"
                className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-500 transition-opacity"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
          {conversations.length === 0 && (
            <p className="text-xs text-slate-400 px-3 py-4 text-center">No chat history yet.</p>
          )}
        </div>
      </aside>

      {/* Main Chat Stream */}
      <div className="flex-1 flex flex-col h-full overflow-hidden bg-white dark:bg-slate-900/40 relative">
        {/* Chat Header */}
        <div className="h-14 px-6 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-white/70 dark:bg-slate-950/70 backdrop-blur-sm z-10">
          <div className="flex items-center space-x-2.5">
            <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
            <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">
              Verified 3D Neural Assistant · Exact ID & Voice Active
            </span>
          </div>

          <div className="flex items-center space-x-3 text-xs text-slate-500">
            <div className="flex items-center gap-1.5">
              <Sliders className="w-3.5 h-3.5" />
              <span>Chunks:</span>
              <select
                value={topK}
                onChange={(e) => setTopK(parseInt(e.target.value, 10))}
                className="bg-slate-100 dark:bg-slate-800 border-none rounded px-2 py-1 text-xs text-slate-800 dark:text-slate-200 focus:outline-none"
              >
                <option value={1}>1 Chunk</option>
                <option value={3}>3 Chunks</option>
                <option value={5}>5 Chunks</option>
              </select>
            </div>
          </div>
        </div>

        {/* Message Stream */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
          {messages.length === 0 && !isLoadingMessages && (
            <div className="h-full flex flex-col items-center justify-center text-center max-w-md mx-auto space-y-4">
              {/* Floating 3D AI Assistant Core Visual */}
              <div className="relative w-20 h-20 rounded-3xl bg-gradient-to-tr from-cyan-500 via-blue-500 to-violet-600 p-0.5 shadow-2xl shadow-cyan-500/20 animate-float-slow">
                <div className="w-full h-full rounded-[22px] bg-slate-950 flex items-center justify-center">
                  <Bot className="w-9 h-9 text-cyan-400" />
                </div>
                <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-cyan-400 animate-ping opacity-75" />
              </div>

              <h3 className="font-bold text-lg text-slate-900 dark:text-white">
                Intelligent Document Assistant
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                Type or speak your question. HybridRAG performs exact record retrieval, mathematical calculations, and verified citations.
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full pt-2">
                {[
                  'Show me the history of EMP001',
                  'What is the experience of EMP002?',
                  'Who has the highest experience?',
                  'Top 10 employees by projects',
                ].map((sample) => (
                  <button
                    key={sample}
                    onClick={() => setInputMessage(sample)}
                    className="p-2.5 rounded-xl text-left text-xs bg-slate-50 dark:bg-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800/80 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 transition-colors"
                  >
                    "{sample}"
                  </button>
                ))}
              </div>
            </div>
          )}

          {isLoadingMessages && (
            <div className="flex items-center justify-center py-20 text-slate-400 text-xs">
              <Loader2 className="w-4 h-4 animate-spin mr-2" /> Loading conversation history...
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex items-start space-x-3 text-xs sm:text-sm ${
                msg.role === 'user' ? 'justify-end' : 'justify-start'
              }`}
            >
              {msg.role === 'assistant' && (
                <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 text-white flex items-center justify-center flex-shrink-0 mt-0.5 shadow-md shadow-cyan-500/20">
                  <Bot className="w-4 h-4" />
                </div>
              )}

              <div
                className={`max-w-2xl rounded-2xl p-4 shadow-sm ${
                  msg.role === 'user'
                    ? 'bg-gradient-to-r from-cyan-600 to-blue-600 text-white'
                    : 'glass-panel text-slate-900 dark:text-slate-100'
                }`}
              >
                {renderMessageContent(msg)}
              </div>

              {msg.role === 'user' && (
                <div className="w-8 h-8 rounded-xl bg-slate-200 dark:bg-slate-800 text-slate-800 dark:text-slate-200 flex items-center justify-center flex-shrink-0 mt-0.5 shadow-xs font-bold text-xs">
                  <User className="w-4 h-4" />
                </div>
              )}
            </div>
          ))}

          {isSending && (
            <div className="flex items-start space-x-3 text-sm">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 text-white flex items-center justify-center flex-shrink-0 mt-0.5 animate-pulse shadow-md shadow-cyan-500/20">
                <Bot className="w-4 h-4" />
              </div>
              <div className="p-4 rounded-2xl glass-panel text-xs text-slate-500 dark:text-slate-400 flex items-center space-x-2">
                <Loader2 className="w-4 h-4 animate-spin text-cyan-500" />
                <span>Searching vector index & verifying citations...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar with Voice Input */}
        <div className="p-4 border-t border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-950/80 backdrop-blur-md">
          <form onSubmit={handleSendMessage} className="max-w-4xl mx-auto flex items-center gap-2">
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              placeholder={speech.isListening ? 'Listening... speak your question...' : 'Ask a question or click the mic to speak...'}
              className="flex-1 px-4 py-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500 transition-all placeholder:text-slate-400"
            />

            {/* Voice Input Button */}
            <VoiceInputButton speech={speech} disabled={isSending} />

            <button
              type="submit"
              disabled={isSending || !inputMessage.trim()}
              className="px-5 py-3 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 disabled:opacity-40 text-white font-semibold text-sm transition-all shadow-md shadow-cyan-500/25 flex items-center justify-center"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>

      {/* Slide-over Source Citation Inspector */}
      <SourceDrawer
        citation={activeCitation}
        onClose={() => setActiveCitation(null)}
        documents={documents}
      />
    </div>
  );
};
