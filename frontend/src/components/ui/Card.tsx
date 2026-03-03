import React from 'react';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  hover?: boolean;
}

export default function Card({ children, className = '', hover = false }: CardProps) {
  const hoverStyles = hover ? 'hover:scale-[1.02] hover:shadow-[0_0_20px_rgba(217,119,6,0.3)] transition-all duration-300 cursor-pointer' : '';

  return (
    <div className={`rpg-card p-6 ${hoverStyles} ${className}`}>
      {children}
    </div>
  );
}
