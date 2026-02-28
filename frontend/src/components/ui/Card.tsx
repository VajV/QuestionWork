import React from 'react';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  hover?: boolean;
}

export default function Card({ children, className = '', hover = false }: CardProps) {
  const baseStyles = 'bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-xl p-4';
  const hoverStyles = hover ? 'hover:border-purple-500/50 hover:shadow-lg hover:shadow-purple-500/10 transition-all duration-300' : '';

  return (
    <div className={`${baseStyles} ${hoverStyles} ${className}`}>
      {children}
    </div>
  );
}
