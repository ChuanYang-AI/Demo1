import React from 'react';
import Logo from './Logo';
import { Brain, Zap, Shield, Globe } from 'lucide-react';

export default function Header() {
  return (
    <header className="bg-white border-b border-gray-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo和品牌信息 */}
          <div className="flex items-center">
            <Logo size="medium" showText={true} />
          </div>
          
          {/* 产品信息 */}
          <div className="hidden md:flex items-center space-x-8">
            <div className="flex items-center space-x-2 text-sm text-gray-600">
              <Brain className="w-4 h-4 text-blue-500" />
              <span>AI智能问答</span>
            </div>
            <div className="flex items-center space-x-2 text-sm text-gray-600">
              <Zap className="w-4 h-4 text-yellow-500" />
              <span>实时检索</span>
            </div>
            <div className="flex items-center space-x-2 text-sm text-gray-600">
              <Shield className="w-4 h-4 text-green-500" />
              <span>企业级安全</span>
            </div>
            <div className="flex items-center space-x-2 text-sm text-gray-600">
              <Globe className="w-4 h-4 text-purple-500" />
              <span>云端部署</span>
            </div>
          </div>
          
          {/* 系统状态 */}
          <div className="flex items-center space-x-4">
            <div className="w-2 h-2 bg-green-500 rounded-full" title="系统运行正常"></div>
          </div>
        </div>
      </div>
    </header>
  );
} 
 
 
 