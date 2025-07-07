import axios from 'axios';
import { RAGResponse, FileUploadResponse, APIError } from '../types/index';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8080';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for logging
api.interceptors.request.use(
  (config) => {
    console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    console.error('API Request Error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    console.log(`API Response: ${response.status} ${response.config.url}`);
    return response;
  },
  (error) => {
    console.error('API Response Error:', error);
    if (error.response) {
      // Server responded with error status
      const apiError: APIError = {
        error: error.response.data?.error || 'Server error',
        details: error.response.data?.details || error.message,
      };
      return Promise.reject(apiError);
    } else if (error.request) {
      // Network error
      const apiError: APIError = {
        error: 'Network error',
        details: 'Unable to connect to server',
      };
      return Promise.reject(apiError);
    } else {
      // Other error
      const apiError: APIError = {
        error: 'Unknown error',
        details: error.message,
      };
      return Promise.reject(apiError);
    }
  }
);

export const chatAPI = {
  // Send message and get RAG response
  async sendMessage(message: string): Promise<RAGResponse> {
    try {
      const response = await api.post('/chat', { message }, {
        timeout: 180000, // 3 minutes for chat requests to handle vector search
      });
      return response.data;
    } catch (error) {
      // 如果是超时错误，提供更友好的错误信息
      if (error && typeof error === 'object' && 'code' in error && (error as any).code === 'ECONNABORTED') {
        throw new Error('请求超时，请稍后重试。系统可能正在处理大量数据。');
      }
      throw error;
    }
  },

  // Upload file for processing with progress callback
  async uploadFile(
    file: File, 
    onUploadProgress?: (progress: number) => void
  ): Promise<FileUploadResponse> {
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await api.post('/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 120000, // 2 minutes for file upload
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total && onUploadProgress) {
            const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            onUploadProgress(progress);
          }
        },
      });
      
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  // Get upload status
  async getUploadStatus(fileId: string): Promise<{
    file_id: string;
    status: string;
    progress: number;
    processed: boolean;
    chunks: number;
    error?: string;
    estimated_time_remaining?: number;
  }> {
    try {
      const response = await api.get(`/upload/${fileId}/status`);
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  // Get uploaded files list
  async getUploadedFiles(): Promise<any[]> {
    try {
      const response = await api.get('/files');
      return response.data.files || [];
    } catch (error) {
      throw error;
    }
  },

  // Health check
  async healthCheck(): Promise<{ status: string; timestamp: number }> {
    try {
      const response = await api.get('/health');
      return response.data;
    } catch (error) {
      throw error;
    }
  },
};

export default api; 