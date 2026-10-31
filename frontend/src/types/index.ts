export interface User {
  id: number;
  email: string;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  token_type: string;
  expires_in_hours: number;
}

export interface DocumentRecord {
  id: number;
  filename: string;
  file_size_bytes: number;
  chunk_count: number;
  created_at: string;
}

export interface Citation {
  id: number;
  source: string;
  chunk_id: string;
  page: number | null;
  text: string;
}

export interface QueryResponse {
  answer: string;
  generation_type: 'llm' | 'extractive_summary' | 'insufficient_information';
  citations: Citation[];
  note: string;
}

export interface ChatMessage {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  created_at: string;
}

export interface Conversation {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail {
  conversation_id: number;
  title: string;
  messages: ChatMessage[];
}

export interface SearchResultItem {
  chunk_id: string;
  source: string;
  page: number | null;
  text: string;
  rrf_score: number;
  rerank_score: number | null;
  highlights: string[];
}

export interface SearchResponse {
  query: string;
  total_results: number;
  results: SearchResultItem[];
}

export interface DashboardStats {
  total_documents: number;
  total_size_bytes: number;
  total_chunks: number;
  total_conversations: number;
  total_messages: number;
  total_pages_processed?: number;
  total_questions_asked?: number;
  structured_records_count?: number;
  department_distribution?: Record<string, number>;
  experience_distribution?: Record<string, number>;
  recent_documents: DocumentRecord[];
  recent_conversations: Conversation[];
}
