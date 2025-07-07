import React, { useState, useEffect } from 'react';
import { Database, MessageCircle, FileText, Clock, Trash2 } from 'lucide-react';
import { db } from '../utils/database';

interface DatabaseStatsProps {
  className?: string;
}

export default function DatabaseStats({ className = '' }: DatabaseStatsProps) {
  const [stats, setStats] = useState({
    conversations: 0,
    messages: 0,
    uploadedFiles: 0,
    dbSize: 'N/A'
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isExpanded, setIsExpanded] = useState(false);

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      setIsLoading(true);
      const dbStats = await db.getStats();
      setStats(dbStats);
    } catch (error) {
      console.error('加载数据库统计失败:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCleanup = async () => {
    if (window.confirm('确定要清理30天前的旧数据吗？此操作不可撤销。')) {
      try {
        await db.cleanupOldData(30);
        await loadStats(); // 重新加载统计
        alert('数据清理完成');
      } catch (error) {
        console.error('数据清理失败:', error);
        alert('数据清理失败，请稍后重试');
      }
    }
  };

  if (isLoading) {
    return (
      <div className={`bg-white rounded-lg border border-gray-200 p-4 ${className}`}>
        <div className="flex items-center space-x-2 mb-2">
          <Database className="w-4 h-4 text-gray-400 animate-pulse" />
          <span className="text-sm font-medium text-gray-600">加载中...</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`bg-white rounded-lg border border-gray-200 ${className}`}>
      <div 
        className="p-4 cursor-pointer hover:bg-gray-50 transition-colors duration-200"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Database className="w-4 h-4 text-blue-500" />
            <span className="text-sm font-medium text-gray-700">本地存储</span>
          </div>
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-1">
              <MessageCircle className="w-3 h-3 text-gray-400" />
              <span className="text-xs text-gray-600">{stats.conversations}</span>
            </div>
            <div className="flex items-center space-x-1">
              <FileText className="w-3 h-3 text-gray-400" />
              <span className="text-xs text-gray-600">{stats.uploadedFiles}</span>
            </div>
            <div className={`transform transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}>
              <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </div>
          </div>
        </div>
      </div>

      {isExpanded && (
        <div className="px-4 pb-4 border-t border-gray-100">
          <div className="grid grid-cols-2 gap-3 mt-3">
            <div className="bg-blue-50 rounded-lg p-3">
              <div className="flex items-center space-x-2 mb-1">
                <MessageCircle className="w-4 h-4 text-blue-500" />
                <span className="text-xs font-medium text-blue-700">对话记录</span>
              </div>
              <div className="text-lg font-bold text-blue-900">{stats.conversations}</div>
              <div className="text-xs text-blue-600">{stats.messages} 条消息</div>
            </div>

            <div className="bg-purple-50 rounded-lg p-3">
              <div className="flex items-center space-x-2 mb-1">
                <FileText className="w-4 h-4 text-purple-500" />
                <span className="text-xs font-medium text-purple-700">文件记录</span>
              </div>
              <div className="text-lg font-bold text-purple-900">{stats.uploadedFiles}</div>
              <div className="text-xs text-purple-600">包含状态信息</div>
            </div>
          </div>

          <div className="mt-3 pt-3 border-t border-gray-100">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Clock className="w-3 h-3 text-gray-400" />
                <span className="text-xs text-gray-600">数据持久化存储</span>
              </div>
              <button
                onClick={handleCleanup}
                className="flex items-center space-x-1 px-2 py-1 text-xs text-red-600 hover:text-red-700 hover:bg-red-50 rounded transition-colors duration-200"
                title="清理30天前的旧数据"
              >
                <Trash2 className="w-3 h-3" />
                <span>清理</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
} 
 
 
 