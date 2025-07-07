import React, { useState, useEffect, useCallback } from 'react';
import { 
  X, 
  FileText, 
  Hash, 
  Search, 
  ChevronLeft, 
  ChevronRight,
  Copy,
  Download,
  Loader2,
  ChevronDown
} from 'lucide-react';

interface FilePreviewProps {
  fileId: string;
  fileName: string;
  onClose: () => void;
}

interface PreviewData {
  fileId: string;
  fileName: string;
  fileSize: number;
  uploadedAt: number;
  totalChunks: number;
  fullText: string;
  chunks: Array<{
    index: number;
    content: string;
    length: number;
  }>;
  metadata: {
    wordCount: number;
    charCount: number;
    type: string;
  };
  gcs_info?: {
    signed_url: string;
  };
}

export default function FilePreview({ fileId, fileName, onClose }: FilePreviewProps) {
  const [previewData, setPreviewData] = useState<PreviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'full' | 'chunks'>('full');
  const [searchTerm, setSearchTerm] = useState('');
  const [currentChunk, setCurrentChunk] = useState(0);
  const [showDownloadMenu, setShowDownloadMenu] = useState(false);

  const fetchPreviewData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await fetch(`http://localhost:8080/files/${fileId}/preview`);
      if (!response.ok) {
        throw new Error('Failed to fetch preview data');
      }
      
      const data = await response.json();
      setPreviewData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [fileId]);

  useEffect(() => {
    fetchPreviewData();
  }, [fetchPreviewData]);

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatTime = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleString('zh-CN');
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    // TODO: Add toast notification
  };

  const downloadText = () => {
    if (!previewData) return;
    
    const blob = new Blob([previewData.fullText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${previewData.fileName}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const downloadOriginalFile = async () => {
    if (!previewData) return;
    
    try {
      const response = await fetch(`http://localhost:8080/files/${previewData.fileId}/download`);
      if (!response.ok) {
        throw new Error('Failed to get download URL');
      }
      
      const data = await response.json();
      window.open(data.download_url, '_blank');
    } catch (error) {
      console.error('Download failed:', error);
      // Fallback to signed URL if available
      if (previewData.gcs_info?.signed_url) {
        window.open(previewData.gcs_info.signed_url, '_blank');
      } else {
        alert('文件下载失败，请稍后重试');
      }
    }
  };

  const highlightText = (text: string, searchTerm: string) => {
    if (!searchTerm) return text;
    
    const regex = new RegExp(`(${searchTerm})`, 'gi');
    return text.replace(regex, '<mark class="bg-yellow-200">$1</mark>');
  };

  const filteredChunks = previewData?.chunks.filter(chunk =>
    chunk.content.toLowerCase().includes(searchTerm.toLowerCase())
  ) || [];

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg p-8 flex items-center space-x-4">
          <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
          <span className="text-lg">加载文件预览...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg p-8 max-w-md">
          <div className="flex items-center space-x-3 mb-4">
            <div className="w-10 h-10 bg-red-100 rounded-full flex items-center justify-center">
              <X className="w-5 h-5 text-red-600" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900">预览失败</h3>
          </div>
          <p className="text-gray-600 mb-6">{error}</p>
          <button
            onClick={onClose}
            className="w-full px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
          >
            关闭
          </button>
        </div>
      </div>
    );
  }

  if (!previewData) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-6xl h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div className="flex items-center space-x-4">
            <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
              <FileText className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-gray-900">{previewData.fileName}</h2>
              <p className="text-sm text-gray-500">
                {formatFileSize(previewData.fileSize)} • {formatTime(previewData.uploadedAt)}
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-3">
            {/* Combined Download Button with Dropdown */}
            <div className="relative">
              <button
                onClick={() => setShowDownloadMenu(!showDownloadMenu)}
                className="flex items-center space-x-1 p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                title="下载选项"
              >
                <Download className="w-5 h-5" />
                <ChevronDown className="w-3 h-3" />
              </button>
              
              {showDownloadMenu && (
                <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-200 z-10">
                  <div className="py-1">
                    <button
                      onClick={() => {
                        downloadOriginalFile();
                        setShowDownloadMenu(false);
                      }}
                      className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center space-x-2"
                    >
                      <FileText className="w-4 h-4" />
                      <span>下载原始文件</span>
                    </button>
                    <button
                      onClick={() => {
                        downloadText();
                        setShowDownloadMenu(false);
                      }}
                      className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center space-x-2"
                    >
                      <Download className="w-4 h-4" />
                      <span>下载文本内容</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
            <button
              onClick={onClose}
              className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
              title="关闭预览"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
          <div className="grid grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-900">{previewData.totalChunks}</div>
              <div className="text-sm text-gray-500">文本块</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-900">{previewData.metadata.wordCount}</div>
              <div className="text-sm text-gray-500">词数</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-900">{previewData.metadata.charCount}</div>
              <div className="text-sm text-gray-500">字符数</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-900">
                {Math.round(previewData.metadata.charCount / previewData.totalChunks)}
              </div>
              <div className="text-sm text-gray-500">平均块长度</div>
            </div>
          </div>
        </div>

        {/* View Mode Toggle */}
        <div className="px-6 py-4 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="flex bg-gray-100 rounded-lg p-1">
                <button
                  onClick={() => setViewMode('full')}
                  className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${
                    viewMode === 'full'
                      ? 'bg-white text-gray-900 shadow-sm'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  完整文本
                </button>
                <button
                  onClick={() => setViewMode('chunks')}
                  className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${
                    viewMode === 'chunks'
                      ? 'bg-white text-gray-900 shadow-sm'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  分块查看
                </button>
              </div>
            </div>
            
            {/* Search */}
            <div className="flex items-center space-x-2">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="搜索内容..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              {searchTerm && (
                <span className="text-sm text-gray-500">
                  {viewMode === 'chunks' ? filteredChunks.length : '搜索结果'} 项
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden">
          {viewMode === 'full' ? (
            /* Full Text View */
            <div className="h-full overflow-y-auto p-6">
              <div className="bg-gray-50 rounded-lg p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-medium text-gray-900">完整文档内容</h3>
                  <button
                    onClick={() => copyToClipboard(previewData.fullText)}
                    className="flex items-center space-x-2 px-3 py-1 text-sm text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                  >
                    <Copy className="w-4 h-4" />
                    <span>复制</span>
                  </button>
                </div>
                <div 
                  className="prose max-w-none text-gray-800 leading-relaxed whitespace-pre-wrap"
                  dangerouslySetInnerHTML={{ 
                    __html: highlightText(previewData.fullText, searchTerm) 
                  }}
                />
              </div>
            </div>
          ) : (
            /* Chunks View */
            <div className="h-full overflow-y-auto p-6">
              {viewMode === 'chunks' && previewData.chunks.length > 0 && (
                <div className="mb-4 flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <span className="text-sm text-gray-600">
                      显示 {searchTerm ? filteredChunks.length : previewData.chunks.length} 个文本块
                    </span>
                  </div>
                  {!searchTerm && (
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => setCurrentChunk(Math.max(0, currentChunk - 1))}
                        disabled={currentChunk === 0}
                        className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <ChevronLeft className="w-4 h-4" />
                      </button>
                      <span className="text-sm text-gray-600">
                        {currentChunk + 1} / {previewData.chunks.length}
                      </span>
                      <button
                        onClick={() => setCurrentChunk(Math.min(previewData.chunks.length - 1, currentChunk + 1))}
                        disabled={currentChunk === previewData.chunks.length - 1}
                        className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                </div>
              )}
              
              <div className="space-y-4">
                {(searchTerm ? filteredChunks : [previewData.chunks[currentChunk]]).map((chunk, index) => (
                  <div key={chunk.index} className="bg-white rounded-lg border border-gray-200 p-6">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center space-x-3">
                        <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                          <Hash className="w-4 h-4 text-blue-600" />
                        </div>
                        <div>
                          <h4 className="font-medium text-gray-900">文本块 {chunk.index + 1}</h4>
                          <p className="text-sm text-gray-500">{chunk.length} 字符</p>
                        </div>
                      </div>
                      <button
                        onClick={() => copyToClipboard(chunk.content)}
                        className="flex items-center space-x-2 px-3 py-1 text-sm text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                      >
                        <Copy className="w-4 h-4" />
                        <span>复制</span>
                      </button>
                    </div>
                    <div 
                      className="prose max-w-none text-gray-800 leading-relaxed whitespace-pre-wrap"
                      dangerouslySetInnerHTML={{ 
                        __html: highlightText(chunk.content, searchTerm) 
                      }}
                    />
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
} 