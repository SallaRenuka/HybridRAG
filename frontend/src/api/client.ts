import axios from 'axios';
import {
  User,
  AuthTokens,
  DocumentRecord,
  QueryResponse,
  Conversation,
  ConversationDetail,
  SearchResponse,
  DashboardStats,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Attach Authorization header if access token exists
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('hybridrag_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Auth API
export const authApi = {
  login: async (email: string, password: string): Promise<AuthTokens> => {
    const res = await apiClient.post<AuthTokens>('/auth/login', { email, password });
    return res.data;
  },
  register: async (email: string, password: string): Promise<User> => {
    const res = await apiClient.post<User>('/auth/register', { email, password });
    return res.data;
  },
  getMe: async (): Promise<User> => {
    const res = await apiClient.get<User>('/auth/me');
    return res.data;
  },
  logout: async (): Promise<void> => {
    try {
      await apiClient.post('/auth/logout');
    } catch {
      // Ignore logout errors if token already invalidated
    } finally {
      localStorage.removeItem('hybridrag_token');
    }
  },
};

// Documents API
export const documentsApi = {
  list: async (): Promise<DocumentRecord[]> => {
    const res = await apiClient.get<DocumentRecord[]>('/documents');
    return res.data;
  },
  upload: async (file: File): Promise<{ status: string; document_id: number; filename: string; chunk_count: number }> => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await apiClient.post('/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return res.data;
  },
  delete: async (documentId: number): Promise<{ status: string; message: string }> => {
    const res = await apiClient.delete(`/documents/${documentId}`);
    return res.data;
  },
  getFileUrl: (documentId: number): string => {
    return `${API_BASE_URL}/documents/${documentId}/file`;
  },
  reindex: async (): Promise<{ status: string; chunks_indexed: number }> => {
    const res = await apiClient.post('/ingest');
    return res.data;
  },
};

// Chat API
export const chatApi = {
  listConversations: async (): Promise<Conversation[]> => {
    const res = await apiClient.get<Conversation[]>('/chat/conversations');
    return res.data;
  },
  createConversation: async (title: string = 'New Conversation'): Promise<Conversation> => {
    const res = await apiClient.post<Conversation>('/chat/conversations', { title });
    return res.data;
  },
  getConversationHistory: async (conversationId: number): Promise<ConversationDetail> => {
    const res = await apiClient.get<ConversationDetail>(`/chat/conversations/${conversationId}`);
    return res.data;
  },
  deleteConversation: async (conversationId: number): Promise<{ status: string }> => {
    const res = await apiClient.delete(`/chat/conversations/${conversationId}`);
    return res.data;
  },
  sendMessage: async (conversationId: number, message: string, topK: number = 3): Promise<QueryResponse> => {
    const res = await apiClient.post<QueryResponse>(`/chat/conversations/${conversationId}/messages`, {
      message,
      top_k: topK,
    });
    return res.data;
  },
};

// Enterprise Search & Dashboard Stats API
export const searchApi = {
  search: async (query: string, topK: number = 5): Promise<SearchResponse> => {
    const res = await apiClient.post<SearchResponse>('/search', { query, top_k: topK });
    return res.data;
  },
  getStats: async (): Promise<DashboardStats> => {
    const res = await apiClient.get<DashboardStats>('/dashboard/stats');
    return res.data;
  },
};
