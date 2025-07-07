import React from 'react';

interface LogoProps {
  size?: 'small' | 'medium' | 'large';
  showText?: boolean;
  className?: string;
}

export default function Logo({ size = 'medium', showText = false, className = '' }: LogoProps) {
  const sizeClasses = {
    small: 'h-8',
    medium: 'h-12',
    large: 'h-16'
  };

  const textSizeClasses = {
    small: 'text-lg',
    medium: 'text-xl',
    large: 'text-2xl'
  };

  return (
    <div className={`flex items-center space-x-3 ${className}`}>
      <img 
        src="/穿扬科技&&google.png" 
        alt="穿扬科技" 
        className={`${sizeClasses[size]} w-auto object-contain`}
      />
      {showText && (
        <span className={`font-bold text-gray-900 ${textSizeClasses[size]}`}>
          穿扬科技
        </span>
      )}
    </div>
  );
} 
 
 
 