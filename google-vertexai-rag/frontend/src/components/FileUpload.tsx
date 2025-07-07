import React, { useRef, useState } from 'react';
import { useChatContext } from '../context/ChatContext';
import { UploadProgress } from './UploadProgress';

export const FileUpload: React.FC = () => {
  const { state, uploadFile, deleteUploadedFile } = useChatContext();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);

  const handleFileSelect = (files: FileList | null) => {
    if (files && files.length > 0) {
      const file = files[0];
      
      // 检查文件类型
      const allowedTypes = [
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/msword',
        'text/plain'
      ];
      
      if (!allowedTypes.includes(file.type)) {
        alert('只支持 PDF、Word 文档和文本文件');
        return;
      }
      
      // 检查文件大小 (10MB)
      if (file.size > 10 * 1024 * 1024) {
        alert('文件大小不能超过 10MB');
        return;
      }
      
      uploadFile(file);
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    handleFileSelect(e.dataTransfer.files);
  };

  const handleButtonClick = () => {
    fileInputRef.current?.click();
  };

  const removeFile = (id: string) => {
    deleteUploadedFile(id);
  };

  const hasActiveUploads = state.uploadedFiles.some(
    file => file.status === 'uploading' || file.status === 'processing'
  );

  return (
    <div className="space-y-4">
      {/* 上传区域 */}
      <div
        className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors ${
          dragActive
            ? 'border-blue-500 bg-blue-50'
            : 'border-gray-300 hover:border-gray-400'
        }`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <div className="flex flex-col items-center space-y-2">
          <svg
            className="w-8 h-8 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
            />
          </svg>
          <div className="text-sm text-gray-600">
            <button
              onClick={handleButtonClick}
              className="font-medium text-blue-600 hover:text-blue-500"
              disabled={hasActiveUploads}
            >
              点击上传文件
            </button>
            <span> 或拖拽文件到此处</span>
          </div>
          <p className="text-xs text-gray-500">
            支持 PDF、Word 文档和文本文件，最大 10MB
          </p>
        </div>
        
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          accept=".pdf,.docx,.doc,.txt"
          onChange={(e) => handleFileSelect(e.target.files)}
          disabled={hasActiveUploads}
        />
      </div>

      {/* 上传进度列表 */}
      {state.uploadedFiles.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-gray-700">上传文件</h3>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {state.uploadedFiles.map((file) => (
              <UploadProgress
                key={file.id}
                file={file}
                onRemove={removeFile}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default FileUpload; 
 
 
 