import React from 'react';
import Logo from './Logo';
import { 
  FileText, 
  MessageSquare, 
  ArrowRight,
  Sparkles,
  Zap
} from 'lucide-react';

interface WelcomeScreenProps {
  onSampleQuestion: (question: string) => void;
}

export default function WelcomeScreen({ onSampleQuestion }: WelcomeScreenProps) {
  const sampleQuestions = [
    "什么是定金？定金和订金有什么区别？",
    "盗窃罪的构成要件是什么？",
    "合同违约的法律后果有哪些？",
    "如何处理劳动争议？"
  ];

  const handleQuestionClick = (question: string) => {
    console.log('点击示例问题:', question);
    onSampleQuestion(question);
  };

  return (
    <div className="flex-1 flex items-center justify-center p-8 bg-gradient-to-br from-blue-50 to-white">
      <div className="max-w-3xl w-full text-center">
        {/* Logo and Title */}
        <div className="mb-8">
          <div className="flex items-center justify-center mb-6">
            <Logo size="large" showText={false} />
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            AI智能问答助手
          </h1>
          <p className="text-lg text-gray-600">
            基于 Google Vertex AI 的企业级智能检索问答系统
          </p>
        </div>

        {/* Quick Features */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-100">
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mx-auto mb-4">
              <MessageSquare className="w-6 h-6 text-blue-600" />
            </div>
            <h3 className="font-semibold text-gray-900 mb-2">智能对话</h3>
            <p className="text-sm text-gray-600">与AI助手进行自然语言对话</p>
          </div>
          
          <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-100">
            <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center mx-auto mb-4">
              <FileText className="w-6 h-6 text-green-600" />
            </div>
            <h3 className="font-semibold text-gray-900 mb-2">文档管理</h3>
            <p className="text-sm text-gray-600">上传并管理您的文档资料</p>
          </div>
          
          <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-100">
            <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center mx-auto mb-4">
              <Zap className="w-6 h-6 text-purple-600" />
            </div>
            <h3 className="font-semibold text-gray-900 mb-2">实时检索</h3>
            <p className="text-sm text-gray-600">快速精准的语义搜索</p>
          </div>
        </div>

        {/* Sample Questions */}
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
          <div className="flex items-center justify-center mb-4">
            <Sparkles className="w-5 h-5 text-blue-500 mr-2" />
            <h2 className="text-xl font-semibold text-gray-900">
              试试这些问题
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {sampleQuestions.map((question, index) => (
              <button
                key={index}
                onClick={() => handleQuestionClick(question)}
                className="group text-left p-4 bg-gray-50 rounded-lg hover:bg-blue-50 hover:border-blue-200 border border-gray-200 transition-all duration-200"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-700 group-hover:text-blue-700">
                    {question}
                  </span>
                  <ArrowRight className="w-4 h-4 text-gray-400 group-hover:text-blue-500 group-hover:translate-x-1 transition-all duration-200" />
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Quick Actions */}
        <div className="mt-8 flex items-center justify-center space-x-4">
          <div className="text-sm text-gray-500">
            开始使用：
          </div>
          <button 
            onClick={() => handleQuestionClick("你好，我想了解一下法律知识")}
            className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <MessageSquare className="w-4 h-4 mr-2" />
            开始对话
          </button>
        </div>
      </div>
    </div>
  );
} 
