import React, { useState, useRef, useEffect } from 'react';
import { useChatContext } from '../context/ChatContext';
import { Message } from '../types/index';
import { Send, Loader2, FileText, Paperclip, Upload, Star } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';

interface ChatAreaProps {
  onFileUpload: (file: File) => void;
}

export default function ChatArea({ onFileUpload }: ChatAreaProps) {
  const { state, sendMessage } = useChatContext();
  const [inputMessage, setInputMessage] = useState('');
  const [isDragOver, setIsDragOver] = useState(false);
  const [dragCounter, setDragCounter] = useState(0);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const currentConversation = state.conversations.find(
    conv => conv.id === state.currentConversationId
  );

  useEffect(() => {
    // 自动滚动到底部
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [currentConversation?.messages]);

  useEffect(() => {
    // 自动调整textarea高度
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
    }
  }, [inputMessage]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputMessage.trim() || state.isLoading) return;

    const message = inputMessage.trim();
    setInputMessage('');
    await sendMessage(message);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage(e as any);
    }
  };

  const formatTime = (timestamp: number) => {
    return new Date(timestamp).toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };



  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      onFileUpload(file);
    }
    // Reset input
    e.target.value = '';
  };

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    setDragCounter(prev => prev + 1);
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setDragCounter(prev => prev - 1);
    if (dragCounter === 1) {
      setIsDragOver(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    setDragCounter(0);
    
    const files = Array.from(e.dataTransfer.files);
    const validFile = files.find(file => 
      file.type.includes('pdf') || 
      file.type.includes('word') || 
      file.type.includes('document')
    );
    
    if (validFile) {
      onFileUpload(validFile);
    }
  };

  const getConfidenceColor = (score: number) => {
    if (score >= 0.8) return 'text-green-600 bg-green-50';
    if (score >= 0.6) return 'text-yellow-600 bg-yellow-50';
    return 'text-red-600 bg-red-50';
  };

  const getConfidenceText = (score: number) => {
    if (score >= 0.8) return '高相关';
    if (score >= 0.6) return '中等相关';
    return '低相关';
  };

  const renderMessage = (message: Message) => {
    const isUser = message.role === 'user';

  return (
      <div key={message.id} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
        <div className={`max-w-[85%] ${isUser ? 'ml-12' : 'mr-12'}`}>
          {/* 消息气泡 */}
            <div
              className={`
              rounded-2xl px-4 py-3 shadow-sm
              ${isUser 
                  ? 'bg-blue-500 text-white' 
                  : 'bg-white text-gray-800 border border-gray-200'
                }
              `}
            >
              <div className="break-words">
                {message.isLoading ? (
                  <div className="flex items-center space-x-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>正在思考中...</span>
                  </div>
                ) : isUser ? (
                  <div className="whitespace-pre-wrap">{message.content}</div>
                ) : (
                  <div className="markdown-content">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      rehypePlugins={[rehypeRaw]}
                      components={{
                      // 自定义组件样式
                      h1: ({ children }) => <h1 className="text-xl font-bold mb-2">{children}</h1>,
                      h2: ({ children }) => <h2 className="text-lg font-bold mb-2">{children}</h2>,
                      h3: ({ children }) => <h3 className="text-base font-bold mb-1">{children}</h3>,
                      p: ({ children }) => <p className="mb-2 leading-relaxed">{children}</p>,
                      ul: ({ children }) => <ul className="list-disc ml-4 mb-2 space-y-1">{children}</ul>,
                      ol: ({ children }) => <ol className="list-decimal ml-4 mb-2 space-y-1">{children}</ol>,
                      li: ({ children }) => <li className="leading-relaxed">{children}</li>,
                      strong: ({ children }) => <strong className="font-semibold text-gray-900">{children}</strong>,
                      em: ({ children }) => <em className="italic">{children}</em>,
                      code: ({ children, className }) => {
                        const isInline = !className;
                        return isInline ? (
                          <code className="bg-gray-100 text-gray-800 px-1 py-0.5 rounded text-sm font-mono">
                            {children}
                          </code>
                        ) : (
                          <code className="block bg-gray-100 text-gray-800 p-2 rounded text-sm font-mono overflow-x-auto">
                            {children}
                          </code>
                        );
                      },
                      pre: ({ children }) => <pre className="bg-gray-100 p-2 rounded overflow-x-auto mb-2">{children}</pre>,
                      blockquote: ({ children }) => (
                        <blockquote className="border-l-4 border-gray-300 pl-4 italic text-gray-600 mb-2">
                          {children}
                        </blockquote>
                      ),
                      a: ({ children, href }) => (
                        <a 
                          href={href} 
                          target="_blank" 
                          rel="noopener noreferrer" 
                          className="text-blue-600 hover:text-blue-800 underline"
                        >
                          {children}
                        </a>
                      ),
                      table: ({ children }) => (
                        <table className="border-collapse border border-gray-300 mb-2">
                          {children}
                        </table>
                      ),
                      th: ({ children }) => (
                        <th className="border border-gray-300 px-2 py-1 bg-gray-100 font-semibold">
                          {children}
                        </th>
                      ),
                      td: ({ children }) => (
                        <td className="border border-gray-300 px-2 py-1">
                          {children}
                        </td>
                      ),
                    }}
                  >
                    {message.content}
                  </ReactMarkdown>
                </div>
                )}
              </div>
            
            {/* 时间戳和答案来源标识 */}
            <div className={`text-xs mt-2 flex items-center justify-between ${isUser ? 'text-blue-100' : 'text-gray-500'}`}>
              <div>
                {formatTime(message.timestamp)}
                {message.processingTime && (
                  <span className="ml-2">• 处理时间: {message.processingTime.toFixed(1)}s</span>
                )}
              </div>
              
              {/* 答案来源标识 - 只在AI回答中显示 */}
              {!isUser && message.answerSource && (
                <div className="flex items-center space-x-2">
                  {message.answerSource === 'rag' && (
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                      📖 文档检索
                    </span>
                  )}
                  {message.answerSource === 'knowledge' && (
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                      🧠 基础知识
                    </span>
                  )}
                  {message.answerSource === 'error' && (
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">
                      ❌ 错误
                    </span>
                  )}
                  {message.confidence !== undefined && (
                    <span className="text-xs text-gray-500">
                      相似度: {(message.confidence * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* 文档引用区域 - 只显示在AI回答中 */}
          {!isUser && message.sources && Array.isArray(message.sources) && message.sources.length > 0 && (
            <div className="mt-3 space-y-2">
              <div className="flex items-center text-sm text-gray-600">
                <FileText className="w-4 h-4 mr-2" />
                <span>参考文档 ({message.sources.length})</span>
              </div>

              {message.sources.map((source, index) => (
                <div
                  key={source?.id || `source_${index}`}
                  className="bg-gray-50 border border-gray-200 rounded-lg p-3 hover:bg-gray-100 transition-colors"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-2">
                        <span className="text-xs font-medium text-gray-500">#{index + 1}</span>
                        <span className="text-sm font-medium text-gray-700">
                          {source?.fileName || '法律知识问答.docx'}
                        </span>
                        {source?.chunkIndex !== undefined && (
                          <span className="text-xs text-gray-500">块{source.chunkIndex}</span>
                        )}
                      </div>
                      
                      <p className="text-sm text-gray-600 leading-relaxed">
                        {source?.content && source.content.length > 200 
                          ? source.content.substring(0, 200) + '...' 
                          : source?.content || '暂无内容'
                        }
                      </p>
                    </div>
                    
                    <div className="flex items-center space-x-2 ml-4">
                      {/* 相似度指标 */}
                      <div className="flex items-center space-x-1">
                        <Star className="w-3 h-3 text-yellow-500" />
                        <span className="text-xs font-medium text-gray-700">
                          {((source?.score || 0) * 100).toFixed(0)}%
                        </span>
                      </div>
                      
                      {/* 可信度标签 */}
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${getConfidenceColor(source?.score || 0)}`}>
                        {getConfidenceText(source?.score || 0)}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div 
      className="flex-1 flex flex-col h-full relative"
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {/* Drag Overlay */}
      {isDragOver && (
        <div className="absolute inset-0 bg-blue-50 bg-opacity-90 z-50 flex items-center justify-center border-2 border-dashed border-blue-300">
          <div className="text-center">
            <Upload className="w-12 h-12 text-blue-500 mx-auto mb-4" />
            <p className="text-lg font-medium text-blue-700">拖拽文件到此处上传</p>
            <p className="text-sm text-blue-600">支持 PDF、DOCX 格式</p>
            <p className="text-xs text-blue-500 mt-2">文件将在"文件管理"页面中管理</p>
          </div>
        </div>
      )}

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6 scrollbar-thin">
        {currentConversation?.messages.map((message: Message) => renderMessage(message))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 border-t border-gray-200 bg-white">
        <form onSubmit={handleSendMessage} className="flex items-end space-x-2">
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="请输入您的问题..."
              className="w-full px-4 py-3 pr-12 border border-gray-300 rounded-2xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none min-h-[48px] max-h-32"
              rows={1}
              disabled={state.isLoading}
            />
            <div className="absolute right-2 bottom-2 flex items-center space-x-1">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="p-2 text-gray-400 hover:text-gray-600 transition-colors duration-200"
                title="上传文件（将在文件管理页面中管理）"
              >
                <Paperclip className="w-4 h-4" />
              </button>
              <span className="text-xs text-gray-400">
                {inputMessage.length}/500
              </span>
            </div>
          </div>
          <button
            type="submit"
            disabled={!inputMessage.trim() || state.isLoading}
            className="p-3 bg-blue-500 text-white rounded-2xl hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors duration-200"
            title="发送"
          >
            {state.isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </form>
      </div>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.doc,.docx"
        onChange={handleFileSelect}
        className="hidden"
      />
    </div>
  );
} 