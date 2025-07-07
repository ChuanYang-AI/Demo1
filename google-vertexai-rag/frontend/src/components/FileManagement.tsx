import React, { useState } from 'react';
import { useChatContext } from '../context/ChatContext';
import FilePreview from './FilePreview';
import FileUploadModal from './FileUploadModal';
import { 
  FileText, 
  Trash2, 
  Download, 
  Eye, 
  Clock, 
  CheckCircle, 
  AlertCircle,
  Loader2,
  Plus,
  Search,
  Filter,
  RefreshCw
} from 'lucide-react';

interface FileManagementProps {
  onFileUpload: (file: File) => void;
}

export default function FileManagement({ onFileUpload }: FileManagementProps) {
  const { state, deleteUploadedFile, syncFilesFromBackend } = useChatContext();
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState<'all' | 'pending' | 'uploading' | 'processing' | 'completed' | 'error'>('all');
  const [previewFile, setPreviewFile] = useState<{ id: string; name: string } | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);

  const handlePreview = (file: any) => {
    setPreviewFile({ id: file.id, name: file.name });
  };

  const handleClosePreview = () => {
    setPreviewFile(null);
  };

  const handleDownload = async (file: any) => {
    try {
      const response = await fetch(`http://localhost:8080/files/${file.id}/download`);
      if (!response.ok) {
        throw new Error('Failed to get download URL');
      }
      
      const data = await response.json();
      
      // 打开下载链接
      window.open(data.download_url, '_blank');
    } catch (error) {
      console.error('Download failed:', error);
      alert('文件下载失败，请稍后重试');
    }
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await syncFilesFromBackend();
    } catch (error) {
      console.error('刷新文件状态失败:', error);
    } finally {
      setIsRefreshing(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatTime = (timestamp: number) => {
    return new Date(timestamp).toLocaleString('zh-CN');
  };

  const getStatusIcon = (status?: string) => {
    switch (status) {
      case 'uploading':
      case 'processing':
        return <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />;
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'error':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      case 'pending':
        return <Clock className="w-5 h-5 text-gray-500" />;
      default:
        return <FileText className="w-5 h-5 text-gray-400" />;
    }
  };



  const getProgressValue = (file: any) => {
    if (file.status === 'uploading') {
      return file.uploadProgress || 0;
    }
    if (file.status === 'processing') {
      return file.processingProgress || 0;
    }
    if (file.status === 'completed') {
      return 100;
    }
    return 0;
  };

  const getProgressColor = (status?: string) => {
    switch (status) {
      case 'uploading':
        return 'bg-blue-500';
      case 'processing':
        return 'bg-yellow-500';
      case 'completed':
        return 'bg-green-500';
      case 'error':
        return 'bg-red-500';
      case 'pending':
        return 'bg-gray-500';
      default:
        return 'bg-gray-500';
    }
  };

  // 过滤文件
  const filteredFiles = state.uploadedFiles.filter(file => {
    const matchesSearch = file.name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesFilter = filterStatus === 'all' || file.status === filterStatus;
    return matchesSearch && matchesFilter;
  });

  // 统计信息
  const stats = {
    total: state.uploadedFiles.length,
    uploading: state.uploadedFiles.filter(f => f.status === 'uploading').length,
    processing: state.uploadedFiles.filter(f => f.status === 'processing').length,
    completed: state.uploadedFiles.filter(f => f.status === 'completed').length,
    error: state.uploadedFiles.filter(f => f.status === 'error').length,
    pending: state.uploadedFiles.filter(f => f.status === 'pending').length,
  };

  // 计算总文档块数
  const totalChunks = state.uploadedFiles.reduce((sum, file) => sum + (file.chunks || 0), 0);

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-gray-50">
      {/* Page Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">文档管理</h1>
            <p className="text-sm text-gray-600 mt-1">智能文档管理与处理中心</p>
          </div>
          <div className="flex items-center space-x-3">
            <button
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="flex items-center space-x-2 px-3 py-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors duration-200"
              title="刷新文件状态"
            >
              <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
              <span className="text-sm">刷新</span>
            </button>
            <button
              onClick={() => setShowUploadModal(true)}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors duration-200 shadow-sm"
            >
              <Plus className="w-4 h-4" />
              <span>上传文档</span>
            </button>
          </div>
        </div>
      </div>

      {/* Compact Statistics Bar */}
      <div className="px-6 py-4 bg-white border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-6">
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
              <span className="text-sm text-gray-600">文档总数</span>
              <span className="text-lg font-semibold text-gray-900">{stats.total}</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 bg-green-500 rounded-full"></div>
              <span className="text-sm text-gray-600">已完成</span>
              <span className="text-lg font-semibold text-green-700">{stats.completed}</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>
              <span className="text-sm text-gray-600">处理中</span>
              <span className="text-lg font-semibold text-yellow-700">{stats.processing + stats.uploading}</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 bg-purple-500 rounded-full"></div>
              <span className="text-sm text-gray-600">文本块</span>
              <span className="text-lg font-semibold text-purple-700">{totalChunks}</span>
            </div>
          </div>
          <div className="text-sm text-gray-500">
            处理成功率: <span className="font-medium text-gray-700">
              {stats.total > 0 ? Math.round((stats.completed / stats.total) * 100) : 0}%
            </span>
          </div>
        </div>
      </div>

      {/* Filters and Search */}
      <div className="px-6 py-4 bg-white border-b border-gray-200">
        <div className="flex items-center space-x-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="搜索文档..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <div className="flex items-center space-x-2">
            <Filter className="w-4 h-4 text-gray-400" />
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value as any)}
              className="border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="all">全部状态</option>
              <option value="uploading">上传中</option>
              <option value="processing">处理中</option>
              <option value="completed">已完成</option>
              <option value="pending">等待处理</option>
              <option value="error">处理失败</option>
            </select>
          </div>
        </div>
      </div>

      {/* File List */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {filteredFiles.length === 0 ? (
          <div className="text-center py-12">
            <div className="w-24 h-24 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-6">
              <FileText className="w-12 h-12 text-gray-400" />
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              {searchTerm || filterStatus !== 'all' ? '没有找到匹配的文档' : '暂无文档'}
            </h3>
            <p className="text-gray-600 mb-6">
              {searchTerm || filterStatus !== 'all' 
                ? '尝试调整搜索条件或筛选器' 
                : '开始上传您的第一个文档，让AI帮您处理和分析'}
            </p>
            {!searchTerm && filterStatus === 'all' && (
              <button
                onClick={() => setShowUploadModal(true)}
                className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                <Plus className="w-4 h-4 mr-2" />
                上传文档
              </button>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {filteredFiles.map((file) => (
              <div key={file.id} className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex items-start justify-between">
                  <div className="flex items-start space-x-4 flex-1">
                    <div className="flex-shrink-0">
                      {getStatusIcon(file.status)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <h4 className="text-lg font-medium text-gray-900 truncate">{file.name}</h4>
                      <div className="flex items-center space-x-4 mt-1 text-sm text-gray-500">
                        <span>{formatFileSize(file.size)}</span>
                        <span>•</span>
                        <span className="flex items-center">
                          <Clock className="w-3 h-3 mr-1" />
                          {formatTime(file.uploadedAt)}
                        </span>
                      </div>
                      <div className="mt-2">
                        <div className="flex items-center space-x-3">
                          {/* Status Indicator */}
                          <div className="flex items-center space-x-1">
                            {getStatusIcon(file.status)}
                            <span className="text-xs text-gray-500">
                              {file.status === 'completed' ? '已完成' : 
                               file.status === 'processing' ? '处理中' : 
                               file.status === 'uploading' ? '上传中' :
                               file.status === 'error' ? '失败' : '等待'}
                            </span>
                          </div>
                          
                          {/* Chunks Info */}
                          {file.status === 'completed' && file.chunks && file.chunks > 0 && (
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700">
                              {file.chunks} 个文本块
                            </span>
                          )}
                          
                          {/* Progress for active uploads */}
                          {(file.status === 'uploading' || file.status === 'processing') && (
                            <span className="text-xs text-gray-500">
                              {getProgressValue(file)}%
                            </span>
                          )}
                        </div>
                        
                        {/* Compact Progress Bar */}
                        {(file.status === 'uploading' || file.status === 'processing') && (
                          <div className="mt-2">
                            <div className="w-full bg-gray-200 rounded-full h-1">
                              <div
                                className={`h-1 rounded-full transition-all duration-300 ${getProgressColor(file.status)}`}
                                style={{ width: `${getProgressValue(file)}%` }}
                              ></div>
                            </div>
                          </div>
                        )}
                        
                        {/* Error Message - Compact */}
                        {file.status === 'error' && file.error && (
                          <div className="mt-2 text-xs text-red-600">
                            错误: {file.error}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                  
                  {/* Action Buttons */}
                  <div className="flex items-center space-x-2 ml-4">
                    {file.status === 'completed' && (
                      <>
                        <button
                          onClick={() => handlePreview(file)}
                          className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                          title="查看详情"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDownload(file)}
                          className="p-2 text-gray-400 hover:text-green-600 hover:bg-green-50 rounded-lg transition-colors"
                          title="下载文件"
                        >
                          <Download className="w-4 h-4" />
                        </button>
                      </>
                    )}
                    {(file.status === 'completed' || file.status === 'error' || file.status === 'pending') && (
                      <button
                        onClick={() => deleteUploadedFile(file.id)}
                        className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                        title="删除文件"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Upload Modal */}
      <FileUploadModal
        isOpen={showUploadModal}
        onClose={() => setShowUploadModal(false)}
        onFileUpload={onFileUpload}
      />

      {/* Floating Action Button */}
      <button
        onClick={() => setShowUploadModal(true)}
        className="fixed bottom-8 right-8 w-14 h-14 bg-blue-600 hover:bg-blue-700 text-white rounded-full shadow-lg hover:shadow-xl transition-all duration-200 flex items-center justify-center z-40 group"
        title="快速上传文档"
      >
        <Plus className="w-6 h-6 group-hover:scale-110 transition-transform" />
      </button>

      {/* Preview Modal */}
      {previewFile && (
        <FilePreview
          fileId={previewFile.id}
          fileName={previewFile.name}
          onClose={handleClosePreview}
        />
      )}
    </div>
  );
} 