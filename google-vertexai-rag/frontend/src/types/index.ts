export interface Message {
  id: string;
  content: string;
  role: 'user' | 'assistant';
  timestamp: number;
  isLoading?: boolean;
  sources?: Array<{
    id: string;
    content: string;
    score: number;
    fileName?: string;
    chunkIndex?: number;
  }>;
  processingTime?: number;
  // 新增答案来源信息
  answerSource?: 'rag' | 'knowledge' | 'error';
  confidence?: number;
  useRag?: boolean;
  maxSimilarity?: number;
  qualityMetrics?: {
    relevanceScore: number;
    sourceCount: number;
    avgSimilarity: number;
  };
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
}

export interface UploadedFile {
  id: string;
  name: string;
  size: number;
  type: string;
  uploadedAt: number;
  processed: boolean;
  chunks?: number;
  uploadProgress?: number;
  processingProgress?: number;
  status?: 'pending' | 'uploading' | 'processing' | 'completed' | 'error';
  error?: string;
  // GCS存储信息
  gcsUri?: string;
  signedUrl?: string;
  downloadUrl?: string;
}

export interface ChatState {
  conversations: Conversation[];
  currentConversationId: string | null;
  uploadedFiles: UploadedFile[];
  isLoading: boolean;
  error: string | null;
}

export interface RAGResponse {
  answer: string;
  sources: Array<{
    id: string;
    content: string;
    score: number;
  }>;
  processingTime: number;
  answerSource?: 'rag' | 'knowledge' | 'error';
  confidence?: number;
  useRag?: boolean;
  maxSimilarity?: number;
  qualityMetrics?: {
    relevanceScore: number;
    sourceCount: number;
    avgSimilarity: number;
  };
}

export interface FileUploadResponse {
  success: boolean;
  fileId: string;
  fileName: string;
  chunks: number;
  message?: string;
  gcs_uri?: string;
  signed_url?: string;
}

export interface APIError {
  error: string;
  details?: string;
} 
