import React, { useState } from 'react';
import { ChatProvider, useChatContext } from './context/ChatContext';
import Sidebar from './components/Sidebar';
import WelcomeScreen from './components/WelcomeScreen';
import ChatArea from './components/ChatArea';
import FileManagement from './components/FileManagement';
import Logo from './components/Logo';
import { AlertCircle, X, Home, MessageCircle, FileText } from 'lucide-react';

type TabType = 'home' | 'chat' | 'files';

function AppContent() {
  const { state, sendMessage, uploadFile, clearError, createNewConversation } = useChatContext();
  const [activeTab, setActiveTab] = useState<TabType>('home');

  const handleSampleQuestion = async (question: string) => {
    console.log('处理示例问题:', question);
    
    // 首先切换到对话页面
    setActiveTab('chat');
    
    // Create new conversation if none exists
    if (!state.currentConversationId) {
      createNewConversation();
      // Wait a bit for the conversation to be created
      setTimeout(() => {
        sendMessage(question);
      }, 200);
    } else {
      await sendMessage(question);
    }
  };

  const handleFileUpload = async (file: File) => {
    try {
      await uploadFile(file);
    } catch (error) {
      console.error('File upload failed:', error);
    }
  };

  const currentConversation = state.conversations.find(
    conv => conv.id === state.currentConversationId
  );

  const tabs = [
    { id: 'home', label: '首页', icon: Home },
    { id: 'chat', label: '对话', icon: MessageCircle },
    { id: 'files', label: '文件管理', icon: FileText }
  ];

  const renderContent = () => {
    switch (activeTab) {
      case 'home':
        return <WelcomeScreen onSampleQuestion={handleSampleQuestion} />;
      case 'chat':
        return currentConversation ? (
          <ChatArea onFileUpload={handleFileUpload} />
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <h3 className="text-lg font-medium text-gray-900 mb-2">暂无对话</h3>
              <p className="text-gray-500 mb-4">点击新建对话开始聊天</p>
              <button
                onClick={() => {
                  createNewConversation();
                }}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                新建对话
              </button>
            </div>
          </div>
        );
      case 'files':
        return <FileManagement onFileUpload={handleFileUpload} />;
      default:
        return <WelcomeScreen onSampleQuestion={handleSampleQuestion} />;
    }
  };

  return (
    <div className="flex h-screen bg-gray-100">
      {/* Sidebar */}
      <Sidebar />

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header with Logo */}
        <div className="bg-white border-b border-gray-200 shadow-sm">
          <div className="flex items-center justify-between px-6 py-4">
            <Logo size="medium" showText={true} />
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                <span className="text-sm text-gray-600">AI助手在线</span>
              </div>
              <div className="text-xs text-gray-500">
                Powered by Vertex AI
              </div>
            </div>
          </div>
        </div>

        {/* Error Banner */}
        {state.error && (
          <div className="bg-red-50 border-l-4 border-red-400 p-4 flex items-center justify-between">
            <div className="flex items-center">
              <AlertCircle className="w-5 h-5 text-red-400 mr-2" />
              <span className="text-red-700">{state.error}</span>
            </div>
            <button
              onClick={clearError}
              className="text-red-400 hover:text-red-600 transition-colors duration-200"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        )}

        {/* Tab Navigation */}
        <div className="bg-white border-b border-gray-200 shadow-sm">
          <div className="flex items-center space-x-1 px-6 py-3">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as TabType)}
                  className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors duration-200 ${
                    activeTab === tab.id
                      ? 'bg-blue-100 text-blue-700 border border-blue-200'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span className="text-sm font-medium">{tab.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Tab Content */}
        {renderContent()}
      </div>
    </div>
  );
}

function App() {
  return (
    <ChatProvider>
      <AppContent />
    </ChatProvider>
  );
}

export default App; 