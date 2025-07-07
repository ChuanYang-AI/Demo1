import React from 'react';
import { UploadedFile } from '../types/index';
import { FileText, Loader2, CheckCircle, XCircle, Trash2 } from 'lucide-react';

interface UploadProgressProps {
  file: UploadedFile;
  onRemove: (id: string) => void;
}

export const UploadProgress: React.FC<UploadProgressProps> = ({ file, onRemove }) => {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'uploading':
        return 'text-blue-600';
      case 'processing':
        return 'text-yellow-600';
      case 'completed':
        return 'text-green-600';
      case 'error':
        return 'text-red-600';
      default:
        return 'text-gray-600';
    }
  };

  const getProgressValue = () => {
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

  const getStatusText = () => {
    switch (file.status) {
      case 'uploading':
        return `上传中 ${file.uploadProgress || 0}%`;
      case 'processing':
        return `处理中 ${file.processingProgress || 0}%`;
      case 'completed':
        return `已完成 - ${file.chunks || 0} 个文本块`;
      case 'error':
        return `错误: ${file.error || '未知错误'}`;
      default:
        return '等待中';
    }
  };

  return (
    <div className="flex items-center justify-between p-3 border border-gray-200 rounded-lg bg-white">
      <div className="flex items-center space-x-3 flex-1">
        <div className="flex-shrink-0">
          {file.status === 'uploading' && (
            <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />
          )}
          {file.status === 'processing' && (
            <Loader2 className="w-5 h-5 text-yellow-600 animate-spin" />
          )}
          {file.status === 'completed' && (
            <CheckCircle className="w-5 h-5 text-green-600" />
          )}
          {file.status === 'error' && (
            <XCircle className="w-5 h-5 text-red-600" />
          )}
          {!file.status && (
            <FileText className="w-5 h-5 text-gray-600" />
          )}
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-gray-900 truncate">
              {file.name}
            </p>
            <span className={`text-xs font-medium ${getStatusColor(file.status || 'pending')}`}>
              {getStatusText()}
            </span>
          </div>
          
          <div className="mt-1">
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className={`h-2 rounded-full transition-all duration-300 ${
                  file.status === 'error' ? 'bg-red-500' : 
                  file.status === 'completed' ? 'bg-green-500' : 
                  'bg-blue-500'
                }`}
                style={{ width: `${getProgressValue()}%` }}
              />
            </div>
          </div>
          
          <div className="flex items-center justify-between text-xs text-gray-500 mt-1">
            <span>{(file.size / 1024 / 1024).toFixed(1)} MB</span>
            <span>{getProgressValue()}%</span>
          </div>
        </div>
      </div>
      
      <button
        onClick={() => onRemove(file.id)}
        className="ml-3 p-1 rounded-full hover:bg-gray-100 text-gray-400 hover:text-red-600 transition-colors"
        title="删除文件"
      >
        <Trash2 className="w-4 h-4" />
      </button>
    </div>
  );
};

export default UploadProgress; 