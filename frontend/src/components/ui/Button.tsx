import React from 'react';

interface ButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: 'primary' | 'secondary' | 'danger';
  className?: string;
}

export default function Button({
  children,
  onClick,
  disabled = false,
  variant = 'primary',
  className = '',
}: ButtonProps) {
  const baseStyles = 'px-4 py-2 rounded-lg font-semibold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed hover:scale-105 active:scale-95';
  
  const variantStyles = {
    primary: 'bg-purple-600 hover:bg-purple-700 text-white shadow-lg shadow-purple-500/30',
    secondary: 'bg-gray-700 hover:bg-gray-600 text-white',
    danger: 'bg-red-600 hover:bg-red-700 text-white shadow-lg shadow-red-500/30',
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`${baseStyles} ${variantStyles[variant]} ${className}`}
    >
      {children}
    </button>
  );
}
