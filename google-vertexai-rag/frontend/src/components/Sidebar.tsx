import React from 'react';
import { useChatContext } from '../context/ChatContext';
import { MessageCircle, Plus, Clock, Trash2, MoreVertical } from 'lucide-react';

export default function Sidebar() {
  const { state, createNewConversation, selectConversation, deleteConversation } = useChatContext();

  const formatTime = (timestamp: number) => {
    const now = new Date();
    const date = new Date(timestamp);
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffHours < 1) {
      return '刚刚';
    } else if (diffHours < 24) {
      return `${diffHours} 小时前`;
    } else if (diffDays < 7) {
      return `${diffDays} 天前`;
    } else {
      return date.toLocaleDateString('zh-CN', {
        month: 'short',
        day: 'numeric',
      });
    }
  };

  const handleDeleteConversation = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (window.confirm('确定要删除这个对话吗？')) {
      deleteConversation(id);
    }
  };

  return (
    <div className="w-80 h-full bg-white border-r border-gray-200 flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">对话历史</h2>
          <button
            onClick={createNewConversation}
            className="p-2 text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded-lg transition-colors duration-200"
            title="新建对话"
          >
            <Plus className="w-5 h-5" />
          </button>
        </div>
        
        {/* Current conversation info */}
        {state.currentConversationId && (
          <div className="text-sm text-gray-600">
            当前对话: {state.conversations.find(c => c.id === state.currentConversationId)?.title || '新对话'}
          </div>
        )}
      </div>

      {/* Conversation List */}
      <div className="flex-1 overflow-y-auto p-4">
        {state.conversations.length === 0 ? (
          <div className="text-center py-8">
            <MessageCircle className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500 text-sm">暂无对话历史</p>
            <p className="text-gray-400 text-xs mt-1">点击右上角 + 号开始新对话</p>
          </div>
        ) : (
          <div className="space-y-2">
            {state.conversations.map((conversation) => (
              <div
                key={conversation.id}
                onClick={() => selectConversation(conversation.id)}
                className={`
                  group cursor-pointer rounded-lg p-3 border transition-all duration-200
                  ${state.currentConversationId === conversation.id 
                    ? 'bg-white shadow-md border border-blue-200 ring-1 ring-blue-100' 
                    : 'hover:bg-gray-50'
                  }
                `}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center space-x-2 mb-2">
                      <h3 className="font-semibold text-gray-900 truncate text-sm">
                        {conversation.title}
                      </h3>
                      {state.currentConversationId === conversation.id && (
                        <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                      )}
                    </div>
                    
                    <div className="flex items-center space-x-3 mb-2">
                      <div className="flex items-center space-x-1">
                        <Clock className="w-3 h-3 text-gray-400" />
                        <span className="text-xs text-gray-500">
                          {formatTime(conversation.updatedAt)}
                        </span>
                      </div>
                      {conversation.messages.length > 0 && (
                        <div className="flex items-center space-x-1">
                          <MessageCircle className="w-3 h-3 text-gray-400" />
                          <span className="text-xs text-gray-500">
                            {conversation.messages.length} 条消息
                          </span>
                        </div>
                      )}
                    </div>
                    
                    {conversation.messages.length > 0 && (
                      <div className="text-xs text-gray-500 truncate bg-gray-50 px-2 py-1 rounded">
                        {conversation.messages[conversation.messages.length - 1].content}
                      </div>
                    )}
                  </div>
                  
                  <div className="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        // 这里可以添加更多操作
                      }}
                      className="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors duration-200"
                      title="更多操作"
                    >
                      <MoreVertical className="w-3 h-3" />
                    </button>
                    <button
                      onClick={(e) => handleDeleteConversation(e, conversation.id)}
                      className="p-1 rounded hover:bg-red-100 text-red-400 hover:text-red-600 transition-colors duration-200"
                      title="删除对话"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 底部状态栏 */}
      <div className="p-4 border-t border-gray-200 bg-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <span className="text-xs text-gray-600">AI助手在线</span>
          </div>
          <div className="text-xs text-gray-500">
            Powered by Vertex AI
          </div>
        </div>
      </div>
    </div>
  );
} 